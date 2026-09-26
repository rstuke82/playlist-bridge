"""Persistent, server-scoped inventories. Successful snapshots replace atomically."""
import hashlib
import json
import time
from . import jobs

def identity(client):
    return hashlib.sha256(repr((client.base_url,client.music_library_key,sorted(client.headers.items()))).encode()).hexdigest()

def snapshot(repo, service, key):
    value=repo.load('inventory').get(service,{})
    return value if value.get('identity')==key else {}

def publish(repo, service, key, rows, started, **extra):
    value={'identity':key,'rows':rows,'checked_at':time.time(),'seconds':round(time.monotonic()-started,2),'count':len(rows),**extra}
    from .lidarr import state_put
    state_put(repo,'inventory',service,value)
    return value

def scan(service):
    from .api import job_store,_config,_health_plex
    from .lidarr import Client,config as lidarr_config
    from .lidarr_requests import server_id
    from .lidarr_downloads import queue,snapshot as refresh_requests
    repo=job_store().repository;started=time.monotonic()
    jobs.progress(f'Scanning {service} library inventory')
    if service=='plex':
        client=_health_plex(_config(read_only=True,namespaces=[]));key=identity(client)
        previous=snapshot(repo,service,key)
        rows=client.search_library('') # no cache scope: always fresh and strict
        jobs.progress(f'Saving {len(rows)} Plex tracks')
        result=publish(repo,service,key,rows,started,machine_identifier=client.machine_identifier)
        from .library_cache import invalidate
        invalidate()
        queue_changed_matches(repo,previous,rows)
    else:
        cfg=lidarr_config(repo)
        from .availability import preferences
        if not preferences(repo).refresh_lidarr:return {'summary':'Lidarr inventory scans are disabled in Settings.'}
        if not cfg.get('enabled'):return {'summary':'Lidarr integration is disabled; no inventory changed.'}
        key=server_id(cfg);client=Client(cfg)
        artists=client.call('GET','artist');albums=client.call('GET','album');downloads=queue(client)
        if not isinstance(artists,list) or not isinstance(albums,list):raise ValueError('Invalid Lidarr catalog; previous inventory retained')
        artist_lookup={a.get('id'):a for a in artists}
        rows=[{'id':a.get('id'),'album_id':a.get('foreignAlbumId'),'title':a.get('title',''),'artist':artist_lookup.get(a.get('artistId'),{}).get('artistName',a.get('artist',{}).get('artistName','')),'artist_id':a.get('artistId'),'monitored':a.get('monitored',False),'statistics':a.get('statistics',{}),'releases':[{k:r.get(k) for k in ('id','foreignReleaseId','title','releaseDate','country','format','label','catalogNumber','trackCount','monitored')} for r in a.get('releases',[])],'anyReleaseOk':a.get('anyReleaseOk')} for a in albums]
        jobs.progress(f'Saving {len(rows)} Lidarr albums and {len(artists)} artists')
        result=publish(repo,service,key,rows,started,artists=[{'id':a.get('id'),'name':a.get('artistName'),'mbid':a.get('foreignArtistId'),'monitored':a.get('monitored')} for a in artists],queue=downloads)
        refresh_requests(repo,cfg,force=True)
    reconciliation=reconcile()
    from .accounts import member_stores,as_user,actor
    if not actor() or actor().get('admin'):
        for user,member_store in member_stores():
            with as_user(user):
                if service=='plex':
                    # Shared accounts can have narrower music visibility. Never
                    # reuse the owner's inventory as proof of user availability.
                    try:
                        member_client=_health_plex(_config(read_only=True,namespaces=[]))
                        previous_member=snapshot(member_store.repository,'plex',identity(member_client))
                        member_rows=member_client.search_library('')
                        publish(member_store.repository,'plex',identity(member_client),member_rows,time.monotonic(),machine_identifier=member_client.machine_identifier)
                        queue_changed_matches(member_store.repository,previous_member,member_rows)
                    except Exception:
                        jobs.output('A user library scan failed; its previous snapshot was retained.')
                        continue
                reconcile()
    return {'summary':f"Scanned {result['count']} {service} items; inventories linked to Bridge tracks.",'count':result['count'],'seconds':result['seconds'],'reconciliation':reconciliation}

def current(repo,config):
    from .accounts import actor, as_user, root_repository
    from .api import _health_plex
    from .lidarr import config as lidarr_config
    from .lidarr_requests import server_id
    from types import SimpleNamespace
    settings=config.config.get('plex',{})
    client=SimpleNamespace(base_url=settings.get('url','').rstrip('/'),music_library_key=str(settings.get('music_library_key','')).strip(),headers={'X-Plex-Token':settings.get('token',''),'Accept':'application/json'})
    plex=snapshot(repo,'plex',identity(client))
    shared=root_repository() if actor() and not actor().get('admin') else repo
    return plex,snapshot(shared,'lidarr',server_id(lidarr_config(shared)))

def reconcile():
    """Link saved/manual selections or unique exact identities; never mutate matches."""
    from .api import job_store,_config,_playlist_key
    from .legacy import Matcher,Syncer
    from .lidarr_requests import save,server_id
    from .lidarr import config as lidarr_config
    repo=job_store().repository;config=_config(read_only=True);syncer=Syncer(config)
    plex,lidarr=current(repo,config)
    normalize=Matcher._normalize_match_text
    def trackkey(t):return (normalize(t.get('title','')),normalize(t.get('artist','')),normalize(t.get('album','')))
    by_id={str(t['plex_id']):t for t in plex.get('rows',[])};exact={}
    for t in plex.get('rows',[]):exact.setdefault(trackkey(t),[]).append(t['plex_id'])
    albums={}
    for a in lidarr.get('rows',[]):albums.setdefault((normalize(a['artist']),normalize(a['title'])),[]).append(a)
    links={};count=0
    for p in config.config.get('playlists',[]):
        key=_playlist_key(p);source=config.source_snapshots.get(key,[])
        if not isinstance(source,list):source=[]
        source=source+config.missing.get(key,[])
        for t in source:
            count+=1
            if count==1 or count%100==0:jobs.progress(f'Linking source tracks to library inventories · {count} checked')
            search=f"{t.get('title','')}|{t.get('artist','')}";saved=config.mapping.get(key,{}).get(search)
            ids=exact.get(trackkey(t),[])
            manual=syncer._get_match_provenance(key,search)=='manual'
            match=str(saved) if saved and str(saved) in by_id else (str(ids[0]) if len(ids)==1 and not manual else None)
            candidates=albums.get((normalize(t.get('artist','')),normalize(t.get('album',''))),[])
            album=candidates[0] if len(candidates)==1 else None
            link_id=hashlib.sha256(json.dumps([key,t],sort_keys=True).encode()).hexdigest()
            links[link_id]={'playlist_key':key,'source':t,'plex_id':match,'lidarr_album_id':album.get('album_id') if album else None,'available':bool(match),'ignored':bool(syncer._find_ignored_track_key(key,t))}
    # One replaced snapshot removes obsolete links after removals/rescans.
    repo.save({'inventory_links':{'current':{'rows':list(links.values()),'checked_at':time.time(),'plex_identity':plex.get('identity'),'lidarr_identity':lidarr.get('identity')}}})
    cfg=lidarr_config(repo)
    for key,r in repo.load('lidarr_requests').items():
        if r.get('server')!=server_id(cfg):continue
        statuses=[]
        for source in r.get('sources',[]):
            matches=[v for v in links.values() if normalize(v['source'].get('title',''))==normalize(source.get('title','')) and normalize(v['source'].get('artist',''))==normalize(source.get('artist',''))]
            statuses.append({**source,'available':bool(matches) and any(m['available'] for m in matches)})
        save(repo,key,plex_tracks=statuses,plex_available=bool(statuses) and all(t['available'] for t in statuses),plex_checked_at=plex.get('checked_at'))
    return {'linked_tracks':len(links),'available':sum(v['available'] for v in links.values())}

def register(app):
    @app.get('/api/inventory/status')
    def status():
        from .api import job_store,_config
        repo=job_store().repository
        try:plex,lidarr=current(repo,_config(read_only=True,namespaces=[]))
        except Exception:plex,lidarr={},{}
        return {s:{k:v for k,v in value.items() if k not in ('rows','artists','queue','identity')} for s,value in [('plex',plex),('lidarr',lidarr)]}


def queue_changed_matches(repo,previous,rows):
    from .availability import preferences
    if not preferences(repo).retry_missing or not any(repo.load('missing').values()):return
    def signature(t):return tuple(str(t.get(k,'')) for k in ('plex_id','title','artist','album'))
    old={signature(t) for t in previous.get('rows',[])}
    added=sum(signature(t) not in old for t in rows)
    if not added:return
    store=jobs.Store(repo)
    if any(j['action']=='retry_missing' and j['status'] in ('queued','running','cancelling') for j in store.list()):return
    jid=store.enqueue('retry_missing',{'reason':'Plex inventory changed','changed_tracks':added})
    jobs.output(f'Plex inventory has {added} new or changed tracks; queued missing-match reconciliation ({jid})')
