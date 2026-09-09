"""Read-only GHCR beta-image update checks, shared across browser sessions."""
import re
import threading
import time
from datetime import datetime, timezone
import requests
from . import __version__

_lock = threading.Lock()
INTERVAL = 6 * 3600
REPO = 'rstuke82/playlist-bridge'


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
        if time.time()-previous.get('checked_epoch',0) < (60 if force else INTERVAL):
            return previous
        state = {'checked_epoch':time.time(), 'checked_at':datetime.now(timezone.utc).isoformat(),
                 'current_version':__version__, 'available':False, 'interval_hours':6}
        try:
            token_response=requests.get('https://ghcr.io/token',params={'service':'ghcr.io','scope':f'repository:{REPO}:pull'},timeout=6)
            token_response.raise_for_status()
            headers={'Authorization':'Bearer '+token_response.json()['token'],
                     'Accept':'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'}
            base=f'https://ghcr.io/v2/{REPO}'
            response=requests.get(base+'/manifests/beta',headers=headers,timeout=6);response.raise_for_status()
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
            state.update(error='Could not check the published beta image. Try again later.',
                         latest_version=previous.get('latest_version'), available=bool(previous.get('available')))
        store.save({'updates':{'latest':state}})
        return state
    finally:
        _lock.release()


def start(stop):
    def loop():
        while not stop.is_set():
            try:check()
            except Exception:pass
            stop.wait(INTERVAL)
    thread=threading.Thread(target=loop,daemon=True,name='playlist-update-check');thread.start();return thread


def register(app):
    @app.get('/api/updates')
    def status():return repository().load('updates').get('latest', {'current_version':__version__,'available':False,'interval_hours':6})
    @app.post('/api/updates/check')
    def check_now():return check(True)
