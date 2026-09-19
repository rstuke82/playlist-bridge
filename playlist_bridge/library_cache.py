"""Bounded in-memory Plex snapshots, opt-in for sync operations only."""
import contextvars
import hashlib
import threading
import time
from contextlib import contextmanager

_policy=contextvars.ContextVar('library_cache_policy',default=None)
_lock=threading.Lock()
_entries={}

@contextmanager
def reuse(minutes=15, refresh=False):
    token=_policy.set({'seconds':minutes*60,'refresh':refresh,'seen':set()})
    try:yield
    finally:_policy.reset(token)

def load(client, fetch):
    policy=_policy.get()
    if policy is None:return fetch()
    identity=hashlib.sha256(repr((client.base_url,client.music_library_key,sorted(client.headers.items()))).encode()).hexdigest()
    with _lock:
        cached=_entries.get(identity)
        fresh=policy['refresh'] and identity not in policy['seen']
        if cached and not fresh and time.monotonic()-cached[0]<policy['seconds']:
            policy['seen'].add(identity)
            return [dict(t) for t in cached[1]]
        started=time.monotonic()
        rows=fetch()
        # Failed non-strict requests must never populate the shared snapshot.
        if rows:
            _entries.clear()
            _entries[identity]=(time.monotonic(),[dict(t) for t in rows])
        policy['seen'].add(identity)
        from . import jobs
        jobs.output(f'Plex library loaded: {len(rows)} tracks in {time.monotonic()-started:.2f}s')
        return rows

def invalidate():
    with _lock:_entries.clear()
