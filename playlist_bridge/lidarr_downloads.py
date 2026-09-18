"""Read-only download snapshots and explicit, identity-checked queue actions."""
import threading
import time
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field
from .lidarr_requests import server_id, save

_lock = threading.Lock()
_last = {}
_catalog = {}

def queue(client):
    rows = []
    for page in range(1, 101):
        result = client.call('GET', 'queue', params={'page':page, 'pageSize':250, 'includeAlbum':'true'}, quiet=True)
        batch = result.get('records', [])
        rows.extend(batch)
        if len(rows) >= result.get('totalRecords',len(rows)) or not batch:
            return rows
    raise HTTPException(502, 'Lidarr queue exceeded the supported size; no queue action was taken.')

def describe(item):
    status = str(item.get('status','')).lower()
    state = str(item.get('trackedDownloadState','')).lower()
    severity = str(item.get('trackedDownloadStatus','')).lower()
    messages = [str(m) for group in item.get('statusMessages',[]) for m in ([group.get('title','')]+group.get('messages',[])) if m]
    if state in ('importfailed','failedpending') or severity in ('warning','error'):
        label = 'Import blocked' if status=='completed' or 'import' in state else 'Blocked'
    elif status in ('failed','warning'):
        label = 'Failed'
    elif state=='imported':
        label = 'Imported into Lidarr'
    elif status=='completed' or state in ('importpending','importing'):
        label = 'Importing'
    elif status=='downloading':
        label = 'Downloading'
    else:
        label = status.capitalize() or 'Waiting for download'
    size, left = item.get('size'), item.get('sizeleft')
    percent = round(max(0,min(100,(1-left/size)*100)),1) if isinstance(size,(int,float)) and size>0 and isinstance(left,(int,float)) else None
    return {'queue_id':item['id'],'download_id':item.get('downloadId',''),'title':item.get('title',''), 'status':label,'percent':percent,'remaining':left,'error':'; '.join(messages)}

def snapshot(repo, cfg):
    from .lidarr import Client
    from .api import _record_log
    server = server_id(cfg)
    records = {k:v for k,v in repo.load('lidarr_requests').items() if v.get('server')==server and v.get('lidarr_id')}
    if not cfg.get('enabled') or not records or time.monotonic()-_last.get(server,0)<15 or not _lock.acquire(False):
        return
    try:
        _last[server]=time.monotonic()
        client=Client(cfg)
        items=queue(client)
        # One catalog read supplies imported-file counts for all requested albums.
        cached=_catalog.get(server)
        if not cached or time.monotonic()-cached[0]>60:
            cached=(time.monotonic(),{a['id']:a for a in client.call('GET','album',quiet=True)})
            _catalog.clear()
            _catalog[server]=cached
        albums=cached[1]
        for key,record in records.items():
            matches=[describe(q) for q in items if q.get('albumId')==record['lidarr_id']]
            if record.get('status')=='search_pending' and record.get('search_command_id'):
                cmd=client.call('GET',f"command/{record['search_command_id']}",quiet=True)
                command_status=str(cmd.get('status','')).lower()
                if command_status in ('completed','failed','aborted','cancelled','orphaned'):
                    record['status']='search_completed' if command_status=='completed' else 'search_failed'
                    failure='' if command_status=='completed' else str(cmd.get('exception') or cmd.get('message') or command_status)
                    from .diagnostics import redact
                    failure=redact(failure.replace(client.key,'[REDACTED]'))
                    save(repo,key,status=record['status'],error=failure)
                    _record_log('INFO' if not failure else 'ERROR','Lidarr search',f"{record.get('title','')}: command {record['search_command_id']} {command_status} {failure}")
            album=albums.get(record['lidarr_id'])
            stats=(album or {}).get('statistics') or {}
            imported=stats.get('trackCount',0)>0 and stats.get('trackFileCount',0)>=stats['trackCount']
            status=matches[0]['status'] if matches else 'Imported into Lidarr' if imported else 'Not found in Lidarr' if album is None else 'Searching' if record.get('status')=='search_pending' else 'Search failed' if record.get('status')=='search_failed' else 'Cancelled' if record.get('download_status')=='Cancelled' else 'Waiting for download'
            if status!=record.get('download_status'):
                _record_log('INFO','Lidarr download',f"{record.get('artist','')} — {record.get('title','')}: {status}")
            from .diagnostics import redact
            for q in matches:
                q['error']=redact(q['error'].replace(client.key,'[REDACTED]'))
            errors='; '.join(q['error'] for q in matches if q['error'])
            if errors and errors!=record.get('download_error'):
                _record_log('ERROR','Lidarr download',f"{record.get('title','')}: {errors}")
            save(repo,key,download_status=status,downloads=matches,download_error=errors,download_checked_at=time.time(),download_poll_error='',lidarr_url=cfg['url'].rstrip('/')+'/album/'+key)
    except (HTTPException,ValueError,KeyError,TypeError) as exc:
        for key in records:
            save(repo,key,download_poll_error=str(getattr(exc,'detail',exc)))
    finally:
        _lock.release()

class Action(BaseModel):
    action: Literal['cancel','replace','search']
    queue_id: int | None = Field(default=None,ge=1)
    download_id: str = Field(default='',max_length=300)
    confirmed: bool = False

def perform(repo,cfg,album,request):
    from .lidarr import Client
    from .lidarr_requests import active
    from .api import _record_log
    if not _lock.acquire(False):
        raise HTTPException(409,'Lidarr status or another action is updating. Try again shortly.')
    try:
        record=repo.load('lidarr_requests').get(album)
        if not record or record.get('server')!=server_id(cfg) or not record.get('lidarr_id'):
            raise HTTPException(404,'Confirmed album request not found on this Lidarr server.')
        with repo.connect() as db:
            if active(db,record.get('job_id')):
                raise HTTPException(409,'This album already has an active job.')
        client=Client(cfg)
        actual=client.call('GET',f"album/{record['lidarr_id']}")
        if actual.get('foreignAlbumId')!=album:
            raise HTTPException(409,'Album identity changed. Refresh before acting.')
        items=queue(client)
        matching=[q for q in items if q.get('albumId')==record['lidarr_id']]
        if request.action=='search':
            if matching:
                raise HTTPException(409,'A download is already queued. Review it before searching again.')
            if record.get('status')=='search_unknown':
                raise HTTPException(409,'Previous search submission is unconfirmed. Inspect Lidarr first.')
            if record.get('search_command_id'):
                command=client.call('GET',f"command/{record['search_command_id']}")
                if str(command.get('status','')).lower() in ('queued','started','running'):
                    raise HTTPException(409,'A search is already running in Lidarr.')
            # Persist uncertainty before the write; never blindly repeat a timed-out submission.
            save(repo,album,status='search_unknown')
            command=client.call('POST','command',json={'name':'AlbumSearch','albumIds':[record['lidarr_id']]})
            save(repo,album,status='search_pending',search_command_id=command['id'],error='',download_status='Searching')
            message='Album search submitted'
        else:
            if not request.confirmed:
                raise HTTPException(422,'Confirm removal of this album download first.')
            target=next((q for q in matching if q['id']==request.queue_id and q.get('downloadId')==request.download_id and request.download_id),None)
            if not target:
                raise HTTPException(409,'The selected download changed or finished. Refresh before acting.')
            if any(q.get('downloadId')==request.download_id and q.get('albumId')!=record['lidarr_id'] for q in items):
                raise HTTPException(409,'This download contains other albums. Manage it directly in Lidarr.')
            if describe(target)['status']=='Imported into Lidarr':
                raise HTTPException(409,'This download is already imported. Manage it directly in Lidarr.')
            client.call('DELETE',f"queue/{request.queue_id}",params={'removeFromClient':'true','blocklist':str(request.action=='replace').lower(),'skipRedownload':str(request.action=='cancel').lower(),'changeCategory':'false'})
            message='Download removed and blocklisted; replacement requested from Lidarr' if request.action=='replace' else 'Download cancelled; no immediate replacement requested'
            save(repo,album,downloads=[],download_status='Waiting for download' if request.action=='replace' else 'Cancelled',download_error='')
        _record_log('INFO','Lidarr download',f"{record.get('title','')}: {message}")
        _last.pop(server_id(cfg),None)
        return {'message':message}
    finally:
        _lock.release()

def register(app):
    from .lidarr import repository, enabled
    @app.post('/api/lidarr/requests/{album}/download-action')
    def action(album:str, request:Action):
        return perform(repository(),enabled(repository()),album,request)
