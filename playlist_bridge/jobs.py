"""Durable, single-worker jobs with timezone-aware cron scheduling."""
import contextlib
import json
import threading
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from croniter import croniter

ACTIONS = {'sync', 'health', 'analyze', 'add', 'fix_match'}
SCOPES = {'all', 'favorites', 'automatic', 'selected'}
TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}
_local = threading.local()


def now():
    return datetime.now(timezone.utc).isoformat()


def next_run(expression, zone, after=None):
    if len(expression.split()) != 5 or not croniter.is_valid(expression):
        raise ValueError('Use five cron fields: minute hour day month weekday.')
    base = (after or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone))
    return croniter(expression, base, max_years_between_matches=5).get_next(datetime).astimezone(timezone.utc).isoformat()


class Cancelled(BaseException):
    pass


def current():
    return getattr(_local, 'context', None)


def progress(message, check=True):
    ctx = current()
    if ctx:
        if check:
            ctx.checkpoint()
        ctx.store.update(ctx.id, progress=message)


class Store:
    def __init__(self, repository):
        self.repository = repository

    def _rows(self, sql, params=()):
        with self.repository.connect() as db:
            cursor = db.execute(sql, params)
            rows = [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]
        for row in rows:
            for key in ('payload', 'result'):
                if key in row:
                    row[key] = json.loads(row[key]) if row[key] else None
        return rows

    def get(self, job_id):
        rows = self._rows('SELECT * FROM jobs WHERE id=?', (job_id,))
        return rows[0] if rows else None

    def list(self):
        return self._rows("SELECT * FROM jobs ORDER BY CASE WHEN status IN ('queued','running','cancelling') THEN 0 ELSE 1 END, created_at DESC LIMIT 200")

    def enqueue(self, action, payload, schedule_id=None, db=None):
        if action not in ACTIONS:
            raise ValueError('Unsupported job action')
        job_id = str(uuid.uuid4())
        def insert(conn):
            # Identical active requests share a job, preventing double clicks.
            encoded = json.dumps(payload, sort_keys=True)
            existing = conn.execute("SELECT id FROM jobs WHERE action=? AND payload=? AND status IN ('queued','running','cancelling')", (action, encoded)).fetchone()
            if existing:
                return existing[0]
            conn.execute('INSERT INTO jobs(id,action,payload,status,progress,created_at,schedule_id) VALUES(?,?,?,?,?,?,?)',
                         (job_id, action, encoded, 'queued', 'Waiting for the worker', now(), schedule_id))
            return job_id
        if db is not None:
            return insert(db)
        with self.repository.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            return insert(conn)

    def update(self, job_id, **values):
        allowed = {'status','progress','result','error','started_at','finished_at','cancel_requested'}
        if not values or not values.keys() <= allowed:
            raise ValueError('Invalid job update')
        if 'result' in values:
            values['result'] = json.dumps(values['result'], default=str)
        with self.repository.connect() as db:
            db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in values)+' WHERE id=?', (*values.values(),job_id))

    def cancel(self, job_id):
        with self.repository.connect() as db:
            db.execute("UPDATE jobs SET cancel_requested=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE 'cancelling' END, progress='Cancellation requested; current playlist update may finish',finished_at=CASE WHEN status='queued' THEN ? ELSE finished_at END WHERE id=? AND status IN ('queued','running','cancelling')", (now(),job_id))
        return self.get(job_id)

    def claim(self):
        with self.repository.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running',started_at=?,progress='Starting' WHERE id=?", (now(),row[0]))
        return self.get(row[0])

    def schedules(self):
        return self._rows('SELECT * FROM schedules ORDER BY name,id')

    def save_schedule(self, data, schedule_id=None):
        if data['action'] not in {'sync','health'} or data['scope'] not in {'all','favorites','automatic'}:
            raise ValueError('Schedules support sync or health for all, favorites, or automatic playlists.')
        upcoming = next_run(data['cron'], data['timezone'])
        schedule_id = schedule_id or str(uuid.uuid4())
        with self.repository.connect() as db:
            db.execute('INSERT INTO schedules(id,name,action,scope,cron,timezone,enabled,next_run) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,action=excluded.action,scope=excluded.scope,cron=excluded.cron,timezone=excluded.timezone,enabled=excluded.enabled,next_run=excluded.next_run',
                       (schedule_id,data['name'],data['action'],data['scope'],data['cron'],data['timezone'],int(data['enabled']),upcoming))
        return next(s for s in self.schedules() if s['id']==schedule_id)

    def due(self, timestamp=None):
        timestamp = timestamp or now()
        with self.repository.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for sid,action,scope,cron,zone in db.execute('SELECT id,action,scope,cron,timezone FROM schedules WHERE enabled=1 AND next_run<=?', (timestamp,)).fetchall():
                active = db.execute("SELECT 1 FROM jobs WHERE schedule_id=? AND status IN ('queued','running','cancelling')", (sid,)).fetchone()
                if not active:
                    self.enqueue(action, {'scope':scope}, sid, db)
                # Coalesce missed runs. Never replay a backlog after downtime.
                db.execute('UPDATE schedules SET next_run=? WHERE id=?', (next_run(cron,zone,datetime.fromisoformat(timestamp)),sid))


class Context:
    def __init__(self, store, job, stop):
        self.store, self.id, self.action, self.stop = store, job['id'], job['action'], stop

    def checkpoint(self):
        if self.stop.is_set() or self.store.get(self.id)['cancel_requested']:
            raise Cancelled()


class Manager:
    def __init__(self, repository):
        self.store = Store(repository)
        self.stop = threading.Event()
        self.thread = None
        self.worker = None
        self.lock = None

    def start(self):
        from .legacy import ProcessLock
        self.lock = ProcessLock(self.store.repository.directory / '.jobs.lock')
        try:
            self.lock.__enter__()
        except RuntimeError:
            self.lock = None
            return  # Another web process owns the shared queue.
        with self.store.repository.connect() as db:
            db.execute("UPDATE jobs SET status='interrupted',error='Server restarted during execution. Review the playlist before running again.',finished_at=? WHERE status IN ('running','cancelling')", (now(),))
        self.thread = threading.Thread(target=self.loop, daemon=True, name='playlist-job-scheduler')
        self.thread.start()

    def loop(self):
        try:
            while not self.stop.is_set():
                try:
                    self.store.due()
                    if not self.worker or not self.worker.is_alive():
                        job = self.store.claim()
                        if job:
                            self.worker = threading.Thread(target=self.execute,args=(job,),daemon=True,name='playlist-job-worker')
                            self.worker.start()
                except Exception as exc:
                    self.store.repository.add_log('ERROR','jobs',f'Queue error: {type(exc).__name__}')
                self.stop.wait(1)
        finally:
            if self.worker:
                self.worker.join()  # Complete the current safe unit before releasing ownership.
            if self.lock:
                self.lock.__exit__(None,None,None)

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=20)

    def execute(self, job):
        from . import api
        from .diagnostics import redact
        ctx = Context(self.store, job, self.stop)
        _local.context = ctx
        result = None
        try:
            ctx.checkpoint()
            api._record_log('INFO',job['action'],f"Job started: {job['id']}")
            result = api.execute_job(job['action'], job['payload'])
            ctx.checkpoint()
            self.store.update(job['id'],status='completed',progress='Completed',result=result,finished_at=now())
            api._record_log('INFO',job['action'],f"Job completed: {job['id']}")
        except Cancelled:
            self.store.update(job['id'],status='cancelled',progress='Cancelled at a safe checkpoint; completed changes are retained',finished_at=now(),**({'result':result} if result is not None else {}))
            api._record_log('INFO',job['action'],f"Job cancelled: {job['id']}")
        except Exception as exc:
            message = redact(getattr(exc,'detail',str(exc)),api._config())
            self.store.update(job['id'],status='failed',error=message,progress='Failed — see error and logs',finished_at=now())
            api._record_log('ERROR',job['action'],message)
        finally:
            _local.context = None
