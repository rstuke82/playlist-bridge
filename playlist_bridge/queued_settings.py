"""Latest-value-wins playlist setting changes, applied by the durable worker."""
import json
import uuid
from fastapi import HTTPException

def enqueue(keys,changes):
    from .api import job_store,_config,_playlist_key
    config=_config(read_only=True,namespaces=[])
    existing={_playlist_key(p) for p in config.config.get('playlists',[])}
    if not keys or not set(keys)<=existing:raise HTTPException(409,'Playlist registrations changed. Refresh and try again.')
    changes={k:v for k,v in changes.items() if k in ('favorite','auto_sync') and isinstance(v,bool)}
    if not changes:raise HTTPException(422,'Choose a playlist setting to change')
    store=job_store()
    with store.repository.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        for key in keys:
            row=db.execute("SELECT value FROM state WHERE namespace='pending_playlist_settings' AND key=?",(key,)).fetchone()
            old=json.loads(row[0]) if row else {}
            old.update(changes);old['revision']=str(uuid.uuid4())
            db.execute("INSERT OR REPLACE INTO state VALUES('pending_playlist_settings',?,?)",(key,json.dumps(old)))
        jid=store.enqueue('playlist_settings',{},db=db)
    return {'queued':True,'job_id':jid,'message':'Change queued; it will apply when safe.'}

def execute():
    from .api import job_store,_config,_playlist_key
    from .legacy import ProcessLock
    from . import jobs
    repo=job_store().repository
    with ProcessLock():
        config=_config();pending=repo.load('pending_playlist_settings');count=0
        for p in config.config.get('playlists',[]):
            key=_playlist_key(p)
            if key not in pending:continue
            for field in ('favorite','auto_sync'):
                if field in pending[key]:p[field]=pending[key][field]
            count+=1
        jobs.progress('Applying queued playlist settings')
        config.save()
        with repo.connect() as db:
            for key,v in pending.items():db.execute("DELETE FROM state WHERE namespace='pending_playlist_settings' AND key=? AND json_extract(value,'$.revision')=?",(key,v['revision']))
    return {'summary':f'Updated settings for {count} playlists.'}
