"""Read-only GHCR release-image update checks, shared across browser sessions."""
import re
import os
import threading
import time
from datetime import datetime, timezone
import requests
from . import __version__

_lock = threading.Lock()
INTERVAL = 6 * 3600
REPO = 'rstuke82/playlist-bridge'
CHANNEL = os.environ.get('PLAYLIST_BRIDGE_UPDATE_CHANNEL','main')
if CHANNEL not in ('main','beta'):CHANNEL='main'


def version(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+))?', str(value))
    return tuple(map(int, match.groups()[:3])) + (int(match[4]) if match[4] else 1000000,) if match else None


def repository():
    from .legacy import CONFIG_DIR
    from .storage import get_repository
    return get_repository(CONFIG_DIR)


def check(force=False):
    store = repository()
    if not _lock.acquire(False):
        return store.load('updates').get('latest', {})
    try:
        previous = store.load('updates').get('latest', {})
        if previous.get('channel')==CHANNEL and time.time()-previous.get('checked_epoch',0) < (60 if force else INTERVAL):
            return previous
        state = {'checked_epoch':time.time(), 'checked_at':datetime.now(timezone.utc).isoformat(),
                 'current_version':__version__, 'channel':CHANNEL, 'available':False, 'interval_hours':6}
        try:
            token_response=requests.get('https://ghcr.io/token',params={'service':'ghcr.io','scope':f'repository:{REPO}:pull'},timeout=6)
            token_response.raise_for_status()
            headers={'Authorization':'Bearer '+token_response.json()['token'],
                     'Accept':'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'}
            base=f'https://ghcr.io/v2/{REPO}'
            response=requests.get(base+'/manifests/'+CHANNEL,headers=headers,timeout=6);response.raise_for_status()
            manifest=response.json()
            if 'manifests' in manifest:
                platform=next(m for m in manifest['manifests'] if m.get('platform',{}).get('architecture')=='amd64' and m.get('platform',{}).get('os')=='linux')
                response=requests.get(base+'/manifests/'+platform['digest'],headers=headers,timeout=6);response.raise_for_status();manifest=response.json()
            response=requests.get(base+'/blobs/'+manifest['config']['digest'],headers=headers,timeout=6);response.raise_for_status()
            latest=response.json().get('config',{}).get('Labels',{}).get('org.opencontainers.image.version','')
            parsed=version(latest)
            if not parsed:raise ValueError('Image has no recognized version label')
            state.update(latest_version=latest, available=parsed>version(__version__),url='https://github.com/rstuke82/playlist-bridge')
        except Exception:
            state.update(error='Could not check the published release image. Try again later.',
                         latest_version=previous.get('latest_version'), available=bool(previous.get('available')))
        store.save({'updates':{'latest':state}})
        return state
    finally:
        _lock.release()


def stored_status(repo):
    state=repo.load('updates').get('latest', {'available':False,'interval_hours':6})
    if state.get('channel')!=CHANNEL:state={'available':False,'interval_hours':6}
    state['channel']=CHANNEL
    state['current_version']=__version__
    latest=version(state.get('latest_version',''))
    state['available']=bool(latest and latest>version(__version__))
    return state


def register(app):
    @app.get('/api/updates')
    def status():return stored_status(repository())
    @app.post('/api/updates/check')
    def check_now():
        from .api import job_store
        store=job_store()
        return store.get(store.enqueue('check_updates',{}))
