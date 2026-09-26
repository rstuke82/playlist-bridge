"""Plex PIN login, opaque sessions, and isolated personal SQLite stores.

The existing root store belongs to the verified server owner. Other accounts
never inherit its playlists or Plex token. Background work carries an explicit
account context, independent of the HTTP session that queued it.
"""
import contextlib
import contextvars
import hashlib
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode
import requests
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

_actor = contextvars.ContextVar('bridge_account', default=None)
COOKIE = 'bridge_session'
PIN_COOKIE = 'bridge_login'
CLIENT = 'playlist-bridge-3'


def root_repository():
    from .storage import get_repository
    from .legacy import CONFIG_DIR
    return get_repository(CONFIG_DIR)


def actor():
    return _actor.get()


@contextlib.contextmanager
def as_user(user):
    token = _actor.set(user)
    try:
        yield
    finally:
        _actor.reset(token)


def personal_repository():
    user = actor()
    root = root_repository()
    if not user or user.get('admin'):
        return root
    from .storage import get_repository
    return get_repository(root.directory / 'users' / str(int(user['id'])))


def public(user):
    return {k: user.get(k) for k in ('id', 'name', 'avatar', 'admin', 'can_request', 'can_playlists', 'disabled', 'pending_login')}


def put(namespace, key, value):
    with root_repository().connect() as db:
        db.execute('INSERT OR REPLACE INTO state VALUES(?,?,?)', (namespace, key, json.dumps(value)))


def delete(namespace, key):
    with root_repository().connect() as db:
        db.execute('DELETE FROM state WHERE namespace=? AND key=?', (namespace, key))


def users():
    return root_repository().load('accounts')


def headers(token=None):
    result = {'Accept': 'application/json', 'X-Plex-Product': 'Playlist Bridge', 'X-Plex-Client-Identifier': CLIENT}
    if token:
        result['X-Plex-Token'] = token
    return result


def plex_json(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=(5, 15), **kwargs)
        if response.status_code in (401, 403):
            raise HTTPException(403, 'Plex did not authorize this account.')
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise HTTPException(503, 'Plex login is temporarily unavailable. Please try again.') from exc


def verify(token):
    from .storage import read_json
    root = root_repository()
    settings = read_json(root.directory / 'config.json').get('plex', {})
    if not settings.get('url') or not settings.get('token') or not settings.get('music_library_key'):
        raise HTTPException(409, 'Configure the Plex server URL, token and music library in config.json before enabling sign-in.')
    profile = plex_json('GET', 'https://plex.tv/api/v2/user', headers=headers(token))
    if not profile.get('email') or profile.get('restricted') or profile.get('guest'):
        raise HTTPException(403, 'Use an individual Plex account. Managed users are not supported.')
    identity = plex_json('GET', settings['url'].rstrip('/') + '/identity', headers=headers(settings['token']))
    machine = identity.get('MediaContainer', {}).get('machineIdentifier')
    resources = plex_json('GET', 'https://plex.tv/api/v2/resources', headers=headers(token), params={'includeHttps': 1})
    resource = next((r for r in resources if machine and r.get('clientIdentifier') == machine and 'server' in r.get('provides', '').split(',')), None)
    if not resource or not resource.get('accessToken'):
        raise HTTPException(403, 'This account does not have access to the configured Plex server.')
    server_token = resource['accessToken']
    libraries = plex_json('GET', settings['url'].rstrip('/') + '/library/sections', headers=headers(server_token))
    if not any(str(s.get('key')) == str(settings['music_library_key']) and s.get('type') == 'artist' for s in libraries.get('MediaContainer', {}).get('Directory', [])):
        raise HTTPException(403, 'This account does not have access to the configured music library.')
    user_id = str(int(profile['id']))
    existing = users().get(user_id, {})
    if existing.get('disabled'):
        raise HTTPException(403, 'This account has been disabled by the administrator.')
    owner = resource.get('owned') is True
    if not users() and not owner:
        raise HTTPException(403, 'The Plex server owner must sign in first to initialize Playlist Bridge.')
    # Only the server owner may inherit the pre-3.0 root library and settings.
    user = {'id': user_id, 'name': profile.get('username') or profile.get('title') or user_id,
            'avatar': profile.get('thumb', ''), 'admin': owner, 'can_request': existing.get('can_request', True),
            'can_playlists':existing.get('can_playlists',True), 'pending_login':False, 'disabled': False, 'plex_token': server_token, 'verified_at': time.time()}
    put('accounts', user_id, user)
    root.add_log('INFO','Plex sign-in',f'Account {user_id} signed in; server owner={owner}')
    if (not existing or existing.get('pending_login')) and not owner:
        from .jobs import Store
        with as_user(user):
            Store(personal_repository()).enqueue('plex_scan',{})
    return user


def install(app):
    @app.middleware('http')
    async def authenticate(request: Request, call_next):
        path = request.url.path
        if not path.startswith('/api/') or path in ('/api/auth/me', '/api/auth/start', '/api/auth/poll'):
            return await call_next(request)
        secret = request.cookies.get(COOKIE, '')
        session = root_repository().load('sessions').get(hashlib.sha256(secret.encode()).hexdigest(), {}) if secret else {}
        user = users().get(session.get('user_id', ''))
        if not user or user.get('disabled') or session.get('expires', 0) < time.time():
            if path == '/api/health':
                return JSONResponse({'status':'ok'})
            return JSONResponse({'detail': 'Sign in with Plex to continue.'}, status_code=401)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            if not secrets.compare_digest(request.headers.get('X-Bridge-CSRF', ''), session.get('csrf', '') or 'invalid'):
                return JSONResponse({'detail': 'Your session changed. Refresh and try again.'}, status_code=403)
        if not user.get('admin'):
            if request.method not in ('GET','HEAD','OPTIONS') and user.get('can_playlists',True) is False and path.startswith(('/api/playlists','/api/missing','/api/matches','/api/match-queue','/api/tracks','/api/sync','/api/jobs')):
                return JSONResponse({'detail':'Playlist changes are disabled for this account.'},status_code=403)
            allowed = path.startswith(('/api/playlists', '/api/missing', '/api/ignored', '/api/tracks', '/api/matches', '/api/match-queue', '/api/detail-progress', '/api/sync', '/api/jobs', '/api/auth/', '/api/discover', '/api/requests-user', '/api/shared-playlists', '/api/job-history', '/api/playlist-schedule/')) or path in ('/api/search', '/api/health')
            if not allowed or (path.startswith('/api/playlist-schedule') and request.method != 'GET'):
                return JSONResponse({'detail': 'Administrator access required.'}, status_code=403)
        try:
            from starlette.concurrency import run_in_threadpool
            await run_in_threadpool(refresh_access,user)
        except HTTPException as exc:
            return JSONResponse({'detail':exc.detail},status_code=exc.status_code)
        with as_user(user):
            return await call_next(request)

    @app.get('/api/auth/me')
    def me(request: Request):
        secret = request.cookies.get(COOKIE, '')
        session = root_repository().load('sessions').get(hashlib.sha256(secret.encode()).hexdigest(), {}) if secret else {}
        user = users().get(session.get('user_id', ''))
        if not user or user.get('disabled') or session.get('expires', 0) < time.time():
            return {'user': None}
        return {'user': public(user), 'csrf': session['csrf']}

    @app.post('/api/auth/start')
    def start(request: Request):
        # Origin checks prevent another website initiating a login in this browser.
        origin = request.headers.get('origin')
        from urllib.parse import urlsplit
        if origin and (urlsplit(origin).netloc != request.headers.get('host') or urlsplit(origin).scheme not in ('http','https')):
            raise HTTPException(403, 'Open sign-in from Playlist Bridge.')
        with root_repository().connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("DELETE FROM state WHERE namespace IN ('login_pins','sessions') AND json_extract(value,'$.expires') < ?",(time.time(),))
            remote=hashlib.sha256(str(request.client.host if request.client else 'unknown').encode()).hexdigest()
            row=db.execute("SELECT value FROM state WHERE namespace='login_limits' AND key=?",(remote,)).fetchone()
            recent=[t for t in (json.loads(row[0]) if row else []) if t>time.time()-60]
            if len(recent)>=5:raise HTTPException(429,'Wait a minute before starting another sign-in.')
            db.execute("INSERT OR REPLACE INTO state VALUES('login_limits',?,?)",(remote,json.dumps([*recent,time.time()])))
        nonce = secrets.token_urlsafe(32)
        pin = plex_json('POST', 'https://plex.tv/api/v2/pins', headers=headers(), data={'strong': 'true'})
        put('login_pins', hashlib.sha256(nonce.encode()).hexdigest(), {'id': pin['id'], 'code': pin['code'], 'expires': time.time() + 600})
        response = JSONResponse({'url': 'https://app.plex.tv/auth#?' + urlencode({'clientID': CLIENT, 'code': pin['code'], 'context[device][product]': 'Playlist Bridge'})})
        response.set_cookie(PIN_COOKIE, nonce, max_age=600, httponly=True, samesite='strict', secure=request.url.scheme == 'https')
        return response

    @app.get('/api/auth/poll')
    def poll(request: Request):
        nonce = request.cookies.get(PIN_COOKIE, '')
        key = hashlib.sha256(nonce.encode()).hexdigest()
        saved = root_repository().load('login_pins').get(key, {})
        if not nonce or saved.get('expires', 0) < time.time():
            raise HTTPException(410, 'Sign-in expired. Start again.')
        pin = plex_json('GET', f"https://plex.tv/api/v2/pins/{saved['id']}", headers=headers(), params={'code': saved['code']})
        if not pin.get('authToken'):
            return {'pending': True}
        user = verify(pin['authToken'])
        delete('login_pins', key)
        secret, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        put('sessions', hashlib.sha256(secret.encode()).hexdigest(), {'user_id': user['id'], 'csrf': csrf, 'expires': time.time() + 7 * 86400})
        response = JSONResponse({'user': public(user), 'csrf': csrf})
        response.set_cookie(COOKIE, secret, max_age=7 * 86400, httponly=True, samesite='lax', secure=request.url.scheme == 'https')
        response.delete_cookie(PIN_COOKIE)
        return response

    @app.post('/api/auth/logout')
    def logout(request: Request):
        delete('sessions', hashlib.sha256(request.cookies.get(COOKIE, '').encode()).hexdigest())
        response = JSONResponse({'ok': True})
        response.delete_cookie(COOKIE)
        return response

    @app.get('/api/users')
    def listing():
        return [public(u) for u in users().values()]

    class Permissions(BaseModel):
        disabled: bool
        can_request: bool
        can_playlists: bool = True

    @app.put('/api/users/{user_id}')
    def update(user_id: str, body: Permissions):
        user = users().get(user_id)
        if not user:
            raise HTTPException(404, 'User not found')
        if user.get('admin'):
            raise HTTPException(409, 'The server owner cannot be disabled here.')
        user.update(body.model_dump())
        put('accounts', user_id, user)
        root_repository().add_log('INFO','Account permissions',f'Account {user_id}: disabled={user["disabled"]}; requests={user["can_request"]}')
        return public(user)


def owner_key():
    return str(actor()['id']) if actor() else 'server'


def member_stores():
    from .jobs import Store
    for user in users().values():
        if not user.get('admin') and not user.get('disabled') and user.get('plex_token'):
            with as_user(user):
                yield user, Store(personal_repository())


def scheduled_members(action, schedule_id):
    if action not in ('sync', 'health'):
        return 0
    from .legacy import Config
    from .sync_policy import eligible
    count=0
    for user, store in member_stores():
        with as_user(user):
            if any(j['action'] == action and j['status'] in ('queued', 'running', 'cancelling') for j in store.list()):
                continue
            playlists = Config(read_only=True, namespaces=[]).config.get('playlists', [])
            if action == 'sync':
                playlists = eligible(store.repository, playlists)
            if playlists:
                store.enqueue(action, {'scope': 'selected', 'playlist_keys': [f"{p['source']}:{p['source_id']}" for p in playlists]}, schedule_id)
                count+=1
    return count


def refresh_access(user):
    """Recheck actual music-library access periodically, failing closed on errors."""
    if user.get('admin') or time.time() - user.get('verified_at', 0) < 300:
        return
    from .storage import read_json
    settings = read_json(root_repository().directory / 'config.json').get('plex', {})
    libraries = plex_json('GET', settings.get('url', '').rstrip('/') + '/library/sections', headers=headers(user['plex_token']))
    if not any(str(s.get('key')) == str(settings.get('music_library_key')) and s.get('type') == 'artist' for s in libraries.get('MediaContainer', {}).get('Directory', [])):
        raise HTTPException(403, 'Plex access to this music library has been removed.')
    user['verified_at'] = time.time()
    put('accounts', user['id'], user)
