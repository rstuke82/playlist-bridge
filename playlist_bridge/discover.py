"""Last.fm discovery and user-safe album requests using server defaults."""
import uuid
import hashlib
import time
import threading
import requests
from fastapi import HTTPException, Query
from pydantic import BaseModel, Field
from .accounts import root_repository, actor, as_user, put

_lock = threading.Lock()


def lastfm(method, **params):
    repo = root_repository()
    settings = repo.load('lastfm').get('settings', {})
    key = settings.get('api_key', '')
    if not key:
        raise HTTPException(409, 'Last.fm is not configured. Ask the administrator to add an API key.')
    cache_key = hashlib.sha256(repr((method, sorted(params.items()))).encode()).hexdigest()
    cache = repo.load('lastfm_cache').get(cache_key, {})
    if cache.get('expires', 0) > time.time():
        return cache['data']
    with _lock:
        cache = repo.load('lastfm_cache').get(cache_key, {})
        if cache.get('expires', 0) > time.time():
            return cache['data']
        try:
            response = requests.get('https://ws.audioscrobbler.com/2.0/', params={'method': method, 'api_key': key, 'format': 'json', **params}, timeout=(5, 15))
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            repo.add_log('ERROR', 'Last.fm', f'{method}: lookup failed ({type(exc).__name__})')
            raise HTTPException(503, 'Last.fm is temporarily unavailable. Try again later.') from exc
        if data.get('error'):
            repo.add_log('ERROR', 'Last.fm', f"{method}: service error {data['error']}")
            raise HTTPException(502, 'Last.fm could not complete this lookup. Check the API key and username.')
        from .lidarr import state_put
        state_put(repo, 'lastfm_cache', cache_key, {'expires': time.time() + 21600, 'data': data})
        repo.add_log('INFO', 'Last.fm', f'{method}: lookup completed; cached for six hours')
        return data


def album_row(a):
    artist = a.get('artist', '')
    images = a.get('image', [])
    image = next((i.get('#text', '') for i in reversed(images) if i.get('#text', '').startswith('https://')), '')
    return {'album': a.get('name', ''), 'artist': artist.get('name', '') if isinstance(artist, dict) else artist,
            'mbid': a.get('mbid', ''), 'artwork': image}


def availability(rows):
    from .legacy import Matcher, Config
    from .inventory import current
    config=Config(read_only=True,namespaces=[])
    plex,lidarr=current(config.repository,config)
    normalize = Matcher._normalize_match_text
    def key(artist, album): return normalize(artist), normalize(album)
    p = {key(t.get('album_artist') or t.get('artist', ''), t.get('album', '')) for t in plex.get('rows', [])}
    l = {key(t.get('artist', ''), t.get('title', '')) for t in lidarr.get('rows', [])}
    seen = set()
    result = []
    for row in rows:
        k = key(row['artist'], row['album'])
        if k in seen or not all(k):
            continue
        seen.add(k)
        result.append({**row, 'availability': 'Available in Plex' if k in p else 'Managed / requested' if k in l else 'Not in saved inventories' if plex and lidarr else 'Availability not scanned'})
    return result


def register(app):
    class Settings(BaseModel):
        api_key: str = Field(default='', max_length=200)

    @app.get('/api/settings/lastfm')
    def settings():
        return {'configured': bool(root_repository().load('lastfm').get('settings', {}).get('api_key'))}

    @app.put('/api/settings/lastfm')
    def save_settings(body: Settings):
        if body.api_key.strip():
            put('lastfm', 'settings', {'api_key': body.api_key.strip()})
        return settings()

    @app.get('/api/discover')
    def discover(q: str = Query(default='', max_length=160), username: str = Query(default='', max_length=100)):
        if q.strip():
            data = lastfm('album.search', album=q.strip(), limit=30)
            rows = data.get('results', {}).get('albummatches', {}).get('album', [])
            heading = 'Album search'
        elif username.strip():
            data = lastfm('user.getTopAlbums', user=username.strip(), period='overall', limit=50)
            rows = data.get('topalbums', {}).get('album', [])
            heading = f'Top albums for {username.strip()}'
        else:
            artists = lastfm('chart.getTopArtists', limit=6).get('artists', {}).get('artist', [])
            rows = []
            for artist in artists:
                rows.extend(lastfm('artist.getTopAlbums', artist=artist['name'], limit=4).get('topalbums', {}).get('album', []))
            heading = 'Albums from trending artists'
        return {'heading': heading, 'rows': availability([album_row(a) for a in rows]), 'attribution': 'Powered by Last.fm', 'cached_for_hours': 6}

    def endpoint(path):
        return next(r.endpoint for r in app.routes if getattr(r, 'path', '') == path)

    def permitted():
        user = actor()
        if not user or not (user.get('can_request') or user.get('admin')):
            raise HTTPException(403, 'Album requests are disabled for this account.')
        return user

    class Search(BaseModel):
        artist: str = Field(default='', max_length=200)
        album: str = Field(default='', max_length=200)
        title: str = Field(default='', max_length=200)

    @app.post('/api/requests-user/search')
    def search(body: Search):
        permitted()
        from .lidarr import Lookup
        with as_user(None):
            result = endpoint('/api/lidarr/search')(Lookup(**body.model_dump(), query=' - '.join(x for x in (body.artist, body.album or body.title) if x)))
        return {'rows': [{k: row.get(k) for k in ('album_id', 'title', 'artist', 'year', 'artwork', 'exists', 'type', 'secondary_types')} for row in result['rows']]}

    class Album(BaseModel):
        album_id: uuid.UUID

    @app.post('/api/requests-user/add', status_code=202)
    def add(body: Album):
        user = permitted()
        from .lidarr import Preview, Confirm, config, Defaults
        # The selected release is resolved and reviewed against server defaults.
        # Users cannot override roots, profiles, tags, monitoring or search policy.
        with as_user(None):
            preview = endpoint('/api/lidarr/preview')(Preview(album_id=body.album_id, **Defaults(**config(root_repository())).model_dump()))
            endpoint('/api/lidarr/add')(Confirm(preview_id=preview['preview_id']))
        put('user_requests', user['id'] + ':' + str(body.album_id), {'user_id': user['id'], 'album_id': str(body.album_id), 'at': time.time()})
        return {'queued': True, 'message': 'Album requested. Status is available in Requests.'}

    @app.get('/api/requests-user')
    def own_requests():
        user = actor()
        mine = {r['album_id'] for r in root_repository().load('user_requests').values() if r.get('user_id') == user['id']}
        with as_user(None):
            from .lidarr_downloads import snapshot
            from .lidarr import config
            snapshot(root_repository(),config(root_repository()))
        rows = root_repository().load('lidarr_requests')
        return [{'album_id': k, **{f: v.get(f) for f in ('title', 'artist', 'status', 'updated_at', 'plex_available')},
                 'display_status': ('Available in Plex' if v.get('plex_available') else (v.get('download_status') or v.get('status','Requested')).replace('Imported into Lidarr','Imported; waiting for Plex').replace('_',' ')),
                 'percent': (v.get('downloads') or [{}])[0].get('percent')} for k, v in rows.items() if k in mine]
