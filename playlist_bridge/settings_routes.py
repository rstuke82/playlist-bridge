"""Task management, backup controls and bulk playlist preferences."""
from fastapi import HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal

class AutoSyncRequest(BaseModel):
    playlist_keys:list[str]=Field(min_length=1)
    auto_sync:bool
class BackupSettings(BaseModel):
    retention:Literal[1,3,7]=7
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
        return {'tasks':tasks.rows(store),**store.repository.load('tasks').get('initialized',{'timezone':'UTC'}),'migration_notes':store.repository.load('tasks').get('sync_modes_v3',{}).get('notes',[])}

    @app.get('/api/job-history')
    def history(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),owner:str=''):
        from .accounts import actor
        if actor() and actor().get('admin'):
            from .admin_activity import history as all_history
            return all_history(offset,limit,owner)
        store=job_store()
        with store.repository.connect() as db:total=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
        return {'rows':store._rows('SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?',(limit,offset)),'total':total}

    @app.post('/api/playlists/auto-sync',status_code=202)
    def set_auto_sync(request:AutoSyncRequest):
        raise HTTPException(410,'Auto Sync flags have been replaced by playlist Sync mode')

    @app.get('/api/backups')
    def get_backups():
        repo=job_store().repository
        return {'backups':backups.listing(repo),'retention':min(7,repo.load('backup_settings').get('retention',7))}

    @app.put('/api/backups/settings')
    def backup_settings(request:BackupSettings):
        job_store().repository.save({'backup_settings':request.model_dump()})
        return request.model_dump()

    @app.delete('/api/backups/{name}')
    def delete_backup(name: str):
        store=job_store()
        if any(j['action'] in ('backup','restore_backup') and j['status'] in ('queued','running','cancelling') for j in store.list()):
            raise HTTPException(409,'Wait for backup or restore to finish before deleting a backup.')
        try:
            with ProcessLock():
                path=backups.path_for(store.repository,name)
                if name not in {b['name'] for b in backups.listing(store.repository)}:
                    raise ValueError('Backup not recognized')
                path.unlink()
        except ValueError as exc:raise HTTPException(404,str(exc))
        except RuntimeError as exc:raise HTTPException(409,'A Bridge operation is using the data store. Try deleting the backup after it finishes.') from exc
        store.repository.add_log('INFO','Backup',f'Deleted backup {name}')
        return {'deleted':name}

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
