"""Admin-curated sources that users can opt into as their own Plex copies."""
import hashlib
from fastapi import HTTPException
from pydantic import BaseModel, Field
from .accounts import actor, root_repository
from .lidarr import state_put


def register(app):
    class Source(BaseModel):
        url: str = Field(max_length=1000)
        name: str = Field(min_length=1, max_length=200)

    class Lookup(BaseModel):
        url: str = Field(max_length=1000)

    @app.post('/api/shared-playlists/metadata')
    def metadata(body: Lookup):
        if not actor() or not actor().get('admin'):raise HTTPException(403,'Administrator access required.')
        import requests
        from urllib.parse import urlsplit
        from bs4 import BeautifulSoup
        from .legacy import Config
        url=Config._normalize_url_input(body.url)
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in ('music.apple.com','open.spotify.com') or parsed.username or parsed.password:
            raise HTTPException(422,'Enter a public Spotify or Apple Music HTTPS playlist URL.')
        try:
            response=requests.get(url,timeout=(5,15),allow_redirects=False)
            response.raise_for_status()
            page=BeautifulSoup(response.text,'html.parser')
            tag=page.find('meta',property='og:title')
            name=tag.get('content','').strip() if tag else ''
            if not name:raise ValueError('No playlist name found')
            name=name.removesuffix(' - Playlist - Apple Music')
            return {'name':name}
        except (requests.RequestException,ValueError):
            raise HTTPException(502,'Could not fetch the source name. Enter a name manually.')

    @app.get('/api/shared-playlists')
    def listing():
        return [{'id': key, **value} for key, value in root_repository().load('shared_playlists').items()]

    @app.post('/api/shared-playlists')
    def publish(body: Source):
        if not actor() or not actor().get('admin'):
            raise HTTPException(403, 'Only an administrator can publish shared playlist sources.')
        from .api import _source_for_url
        _source_for_url(body.url)
        key = hashlib.sha256(body.url.encode()).hexdigest()
        state_put(root_repository(), 'shared_playlists', key, body.model_dump())
        return {'id': key}

    @app.delete('/api/shared-playlists/{key}')
    def remove(key: str):
        if not actor() or not actor().get('admin'):
            raise HTTPException(403, 'Administrator access required.')
        with root_repository().connect() as db:
            db.execute("DELETE FROM state WHERE namespace='shared_playlists' AND key=?", (key,))
        return {'removed': True}

    @app.post('/api/shared-playlists/{key}/subscribe', status_code=202)
    def subscribe(key: str):
        source = root_repository().load('shared_playlists').get(key)
        if not source:
            raise HTTPException(404, 'Shared source not found')
        from .api import queue_job, JobRequest
        return queue_job(JobRequest(action='add', payload={**source, 'sync_mode': 'inherit'}))
