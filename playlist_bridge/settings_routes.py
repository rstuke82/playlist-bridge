"""Task management, backup controls and bulk playlist preferences."""
from fastapi import HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal

class AutoSyncRequest(BaseModel):
    playlist_keys:list[str]=Field(min_length=1)
    auto_sync:bool
class BackupSettings(BaseModel):
    retention:Literal[7,14,30]=14
class RestoreRequest(BaseModel):
    name:str
class AliasRequest(BaseModel):
    canonical:str=Field(min_length=1)
    aliases:list[str]


def register(app):
    from .api import job_store, _config, _playlist_key
    from .legacy import ProcessLock
    from . import tasks, backups

    @app.get('/api/tasks')
    def list_tasks():
        store=job_store()
        return {'tasks':tasks.rows(store),**store.repository.load('tasks').get('initialized',{'timezone':'UTC'})}

    @app.get('/api/job-history')
    def history(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
        store=job_store()
        with store.repository.connect() as db:total=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
        return {'rows':store._rows('SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?',(limit,offset)),'total':total}

    @app.post('/api/playlists/auto-sync')
    def set_auto_sync(request:AutoSyncRequest):
        with ProcessLock():
            config=_config();keys=set(request.playlist_keys)
            selected=[p for p in config.config['playlists'] if _playlist_key(p) in keys]
            if len(selected)!=len(keys):raise HTTPException(409,'Playlist registrations changed. Refresh and select again.')
            for playlist in selected:playlist['auto_sync']=request.auto_sync
            config.save()
        return {'updated':len(selected),'auto_sync':request.auto_sync}

    @app.get('/api/backups')
    def get_backups():
        repo=job_store().repository
        return {'backups':backups.listing(repo),'retention':repo.load('backup_settings').get('retention',14)}

    @app.put('/api/backups/settings')
    def backup_settings(request:BackupSettings):
        job_store().repository.save({'backup_settings':request.model_dump()})
        return request.model_dump()

    @app.get('/api/backups/{name}/download')
    def download(name:str):
        try:path=backups.path_for(job_store().repository,name)
        except ValueError as exc:raise HTTPException(404,str(exc))
        return FileResponse(path,media_type='application/zip',filename=path.name)

    @app.post('/api/backups/restore',status_code=202)
    def restore(request:RestoreRequest):
        store=job_store()
        try:backups.path_for(store.repository,request.name)
        except ValueError as exc:raise HTTPException(404,str(exc))
        return store.get(store.enqueue('restore_backup',{'name':request.name}))

    @app.get('/api/settings/matching')
    def matching():return {'aliases':_config(read_only=True).artist_aliases}

    @app.put('/api/settings/matching/alias')
    def save_alias(request:AliasRequest):
        with ProcessLock():
            config=_config()
            canonical=request.canonical.strip()
            if not canonical:raise HTTPException(400,'Enter an artist name')
            aliases=list(dict.fromkeys(a.strip() for a in request.aliases if a.strip()))
            if aliases:config.artist_aliases[canonical]=aliases
            else:config.artist_aliases.pop(canonical,None)
            config.save_artist_aliases()
        return {'aliases':config.artist_aliases}
