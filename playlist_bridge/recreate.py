"""Explicit recovery of a destination confirmed missing from the user's Plex."""
from fastapi import HTTPException
from pydantic import BaseModel
from . import jobs


def execute(payload):
    from .api import _config, _playlist_key, _health_plex, sync_one
    from .legacy import ProcessLock
    import requests
    with ProcessLock():
        config = _config()
        playlist = next((p for p in config.config['playlists'] if _playlist_key(p) == payload['playlist_key']), None)
        if not playlist:
            raise ValueError('Playlist registration no longer exists.')
        plex = _health_plex(config)
        # Validate library access separately: a Plex 404 alone cannot prove deletion.
        library = plex.search_library('')
        response = requests.get(f"{plex.base_url}/playlists/{playlist['plex_playlist_id']}", headers=plex.headers, timeout=(5, 15))
        if response.status_code != 404:
            response.raise_for_status()
            raise ValueError('The existing Plex playlist is accessible. Sync it instead of recreating it.')
        key = payload['playlist_key']
        available = {str(t['plex_id']) for t in library}
        seed = next((str(v) for v in config.mapping.get(key, {}).values() if str(v) in available), None)
        if not seed:
            raise ValueError('No saved match is currently available in Plex. Resolve a track before recreating this playlist.')
        jobs.progress('Creating a replacement Plex playlist')
        destination = plex.create_playlist(playlist.get('custom_name') or playlist['plex_playlist_name'], seed)
        if not destination:
            raise ValueError('Plex did not confirm the replacement ID. Inspect Plex before retrying; a playlist may have been created.')
        # Record the confirmed new ID before syncing, retaining mappings and schedule.
        playlist['plex_playlist_id'] = str(destination)
        config.save()
    return sync_one(key)


def register(app):
    class Confirm(BaseModel):
        confirmed: bool = False
    @app.post('/api/playlists/{key:path}/recreate', status_code=202)
    def recreate(key: str, body: Confirm):
        from .api import _config, _playlist_key, job_store
        if not body.confirmed:
            raise HTTPException(422, 'Confirm creation of a replacement Plex playlist.')
        if not any(_playlist_key(p) == key for p in _config(read_only=True, namespaces=[]).config['playlists']):
            raise HTTPException(404, 'Playlist not found')
        store = job_store()
        return store.get(store.enqueue('recreate', {'playlist_key': key}))
