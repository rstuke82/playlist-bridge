"""Per-playlist weekly schedules with a shared server timezone."""
import json
import uuid
from datetime import datetime,timezone
from typing import Literal
from pydantic import BaseModel,Field,model_validator
from fastapi import HTTPException
from .jobs import next_run,now

class Schedule(BaseModel):
    mode:Literal['inherit','disabled','custom']='inherit'
    days:list[int]=Field(default_factory=lambda:[0]) # Sunday = 0
    hour:int=Field(default=2,ge=0,le=23)
    minute:int=Field(default=0,ge=0,le=59)
    @model_validator(mode='after')
    def valid(self):
        if any(d<0 or d>6 for d in self.days) or (self.mode=='custom' and not self.days):raise ValueError('Select at least one valid day')
        self.days=sorted(set(self.days));return self

def zone(repo):return repo.load('tasks').get('initialized',{}).get('timezone','UTC')
def expression(value):return f"{value['minute']} {value['hour']} * * {','.join(map(str,value['days']))}"
def read(repo,key):
    value=repo.load('playlist_schedules').get(key,Schedule().model_dump())
    return {**value,'timezone':zone(repo)}

def due(store):
    if not store.repository.load('playlist_schedules'):return
    from .api import _config,_playlist_key
    keys={_playlist_key(p) for p in _config(read_only=True,namespaces=[]).config.get('playlists',[])}
    timestamp=now();tz=zone(store.repository)
    with store.repository.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM jobs WHERE action='restore_backup' AND status IN ('running','cancelling')").fetchone():return
        for key,raw in db.execute("SELECT key,value FROM state WHERE namespace='playlist_schedules'").fetchall():
            value=json.loads(raw)
            if key not in keys:
                db.execute("DELETE FROM state WHERE namespace='playlist_schedules' AND key=?",(key,));continue
            if value['mode']!='custom':continue
            if value.get('timezone')!=tz:
                value.update(timezone=tz,next_run=next_run(expression(value),tz))
            elif value.get('next_run','9999')<=timestamp:
                active=False
                for rawjob, in db.execute("SELECT payload FROM jobs WHERE action='sync' AND status IN ('queued','running','cancelling')"):
                    payload=json.loads(rawjob)
                    if payload.get('scope','all')!='selected' or key in payload.get('playlist_keys',[]):active=True
                if not active:
                    jid=store.enqueue('sync',{'scope':'selected','playlist_keys':[key],'playlist_schedule':key},db=db)
                    value.update(last_job=jid,last_scheduled_at=timestamp,last_event='Queued')
                else:value.update(last_scheduled_at=timestamp,last_event='Skipped — playlist sync already queued or running')
                value['next_run']=next_run(expression(value),tz,datetime.fromisoformat(timestamp))
            db.execute("UPDATE state SET value=? WHERE namespace='playlist_schedules' AND key=?",(json.dumps(value),key))

def register(app):
    from .api import job_store,_config,_playlist_key
    def exists(key):
        if not any(_playlist_key(p)==key for p in _config(read_only=True,namespaces=[]).config.get('playlists',[])):raise HTTPException(404,'Playlist not found')
    @app.get('/api/playlist-schedules')
    def listing():
        repo=job_store().repository
        return [{'key':_playlist_key(p),'name':p.get('plex_playlist_name'),**read(repo,_playlist_key(p))} for p in _config(read_only=True,namespaces=[]).config.get('playlists',[]) if read(repo,_playlist_key(p))['mode']!='inherit']
    @app.get('/api/playlist-schedule/{key:path}')
    def get(key:str):exists(key);return read(job_store().repository,key)
    @app.put('/api/playlist-schedule/{key:path}')
    def put(key:str,request:Schedule):
        exists(key);repo=job_store().repository;tz=zone(repo);value={**request.model_dump(),'timezone':tz}
        value['next_run']=next_run(expression(value),tz) if value['mode']=='custom' else None
        from .lidarr import state_put
        state_put(repo,'playlist_schedules',key,value)
        return value
