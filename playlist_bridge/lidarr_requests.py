"""Persistent album request tracking, shared across source playlists."""
import hashlib
import json
import time
from fastapi import HTTPException
from . import jobs


def server_id(cfg):
    return hashlib.sha256(cfg['url'].rstrip('/').encode()).hexdigest()


def save(repo, album, **changes):
    with repo.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT value FROM state WHERE namespace='lidarr_requests' AND key=?", (album,)).fetchone()
        if not row:
            return
        value = json.loads(row[0])
        value.update(changes, updated_at=time.time())
        db.execute("UPDATE state SET value=? WHERE namespace='lidarr_requests' AND key=?", (json.dumps(value), album))


def active(db, job_id):
    row = db.execute('SELECT status FROM jobs WHERE id=?', (job_id or '',)).fetchone()
    return bool(row and row[0] in ('queued','running','cancelling'))


def register(app):
    from .lidarr import repository, enabled
    @app.get('/api/lidarr/requests')
    def list_requests():
        repo = repository()
        from .lidarr import config
        server = server_id(config(repo))
        rows = []
        with repo.connect() as db:
            for key,value in repo.load('lidarr_requests').items():
                if value.get('server') != server:
                    continue
                value = dict(value, key=key, active=active(db,value.get('job_id')))
                if not value['active'] and value['status'] in ('queued','adding'):
                    value['status'] = 'add_failed'
                rows.append(value)
        return rows

    @app.post('/api/lidarr/requests/{album}/retry-search', status_code=202)
    def retry(album: str):
        from .api import job_store
        repo = repository()
        cfg = enabled(repo)
        with repo.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT value FROM state WHERE namespace='lidarr_requests' AND key=?", (album,)).fetchone()
            if not row:
                raise HTTPException(404, 'Album request not found.')
            value = json.loads(row[0])
            if value.get('server') != server_id(cfg) or not value.get('lidarr_id'):
                raise HTTPException(409, 'No confirmed album on this Lidarr server. Check Lidarr before retrying.')
            if value.get('status') == 'search_unknown':
                raise HTTPException(409, 'The search submission timed out without a command ID. Inspect Lidarr before submitting another search.')
            if active(db,value.get('job_id')):
                return job_store().get(value['job_id'])
            payload = {'album_id':album,'server':value['server']}
            jid = job_store().enqueue('lidarr_search',payload,db=db)
            value.update(job_id=jid,status='search_pending',error='',updated_at=time.time())
            db.execute("UPDATE state SET value=? WHERE namespace='lidarr_requests' AND key=?", (json.dumps(value),album))
        return job_store().get(jid)
