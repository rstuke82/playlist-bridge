"""Transactional SQLite repository; legacy JSON is imported exactly once."""
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

STARTUP_KEYS = {'plex', 'server', 'data_directory', 'data_dir'}
FILES = {'mapping': 'mapping.json', 'missing': 'missing_tracks.json',
         'match_metadata': 'match_metadata.json', 'source_snapshots': 'source_snapshots.json',
         'ignored_tracks': 'ignored_tracks.json', 'artist_aliases': 'artist_aliases.json'}


def read_json(path):
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text() or '{}') if path.read_text().strip() else {}
        if '_schema_version' in raw:
            if raw['_schema_version'] not in (0, 1, 2):
                raise ValueError('Unsupported legacy schema')
            raw = raw['data']
        if not isinstance(raw, dict):
            raise ValueError('Expected an object')
        return raw
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeError(f'Could not read {path.name}: {exc}') from exc


class Repository:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'playlist-bridge.db'
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > 1:
                raise RuntimeError('Database requires a newer Playlist Bridge build')
            if version == 0:
                db.execute('CREATE TABLE state (namespace TEXT, key TEXT, value TEXT NOT NULL, PRIMARY KEY(namespace,key))')
                db.execute('CREATE TABLE health_history (id INTEGER PRIMARY KEY, playlist_key TEXT, checked_at TEXT, result TEXT)')
                db.execute('CREATE TABLE migration_backups (name TEXT PRIMARY KEY, content BLOB NOT NULL)')
                config = read_json(self.directory / 'config.json')
                buckets = {name: read_json(self.directory / file) for name, file in FILES.items()}
                buckets['runtime'] = {k: v for k, v in config.items() if k not in STARTUP_KEYS}
                for name, values in buckets.items():
                    for key, value in values.items():
                        encoded = json.dumps(value, ensure_ascii=False)
                        db.execute('INSERT INTO state VALUES (?,?,?)', (name, key, encoded))
                    actual = {k: json.loads(v) for k, v in db.execute('SELECT key,value FROM state WHERE namespace=?', (name,))}
                    if actual != values:
                        raise RuntimeError(f'Migration validation failed: {name}')
                for name in ['config.json', *FILES.values()]:
                    path = self.directory / name
                    if path.exists():
                        db.execute('INSERT INTO migration_backups VALUES (?,?)', (name, path.read_bytes()))
                db.execute('PRAGMA user_version=1')
        # Durable originals in the transaction make backup completion restart-safe.
        with self.connect() as db:
            backups = db.execute('SELECT name,content FROM migration_backups').fetchall()
        for name, content in backups:
            backup = self.directory / (name + '.pre-sqlite.bak')
            if not backup.exists():
                with backup.open('xb') as stream:
                    stream.write(content)
        startup = read_json(self.directory / 'config.json')
        clean = {k: v for k, v in startup.items() if k in STARTUP_KEYS}
        if startup != clean:
            self.save_startup(clean)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            db.execute('PRAGMA busy_timeout=30000')
            with db:
                yield db
        finally:
            db.close()

    def load(self, namespace):
        with self.connect() as db:
            return {k: json.loads(v) for k, v in db.execute('SELECT key,value FROM state WHERE namespace=?', (namespace,))}

    def save(self, buckets, baseline=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for name, values in buckets.items():
                old = baseline.get(name, {}) if baseline is not None else self.load(name)
                for key in old.keys() - values.keys():
                    db.execute('DELETE FROM state WHERE namespace=? AND key=?', (name, key))
                for key, value in values.items():
                    if key not in old or old[key] != value:
                        db.execute('INSERT OR REPLACE INTO state VALUES (?,?,?)', (name, key, json.dumps(value, ensure_ascii=False)))

    def save_startup(self, config):
        from .legacy import _atomic_write_json
        _atomic_write_json(self.directory / 'config.json', config)

    def save_health(self, key, result):
        result['checked_at'] = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('INSERT INTO health_history(playlist_key,checked_at,result) VALUES (?,?,?)', (key, result['checked_at'], json.dumps(result)))
            db.execute('INSERT OR REPLACE INTO state VALUES (?,?,?)', ('health', key, json.dumps(result)))
