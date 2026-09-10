"""Midnight-aligned recurring tasks, including built-in maintenance jobs."""
import json
import os
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

INTERVALS = {0: 'Disabled', 1: 'Every hour', 3: 'Every 3 hours', 6: 'Every 6 hours', 12: 'Every 12 hours', 24: 'Daily'}
DEFINITIONS = [('sync','all','Sync All',0),('sync','favorites','Sync Favorites',0),
    ('sync','automatic','Sync Auto Sync Playlists',0),('health','all','Health Check',0),
    ('health','favorites','Health Check Favorites',0),('health','automatic','Health Check Auto Sync',0),
    ('backup','all','Backup',24),('check_updates','all','Check for Updates',6)]


def expression(hours):
    if hours not in INTERVALS:raise ValueError('Choose an available interval')
    return '0 0 * * *' if hours in (0,24) else f'0 */{hours} * * *'


def hours_for(cron):
    for hours in (1,3,6,12,24):
        if cron == expression(hours):return hours
    parts=cron.split()
    if len(parts)==5 and parts[1]=='*':return 1
    if len(parts)==5 and parts[1].startswith('*/'):
        try:
            n=int(parts[1][2:])
            if n in INTERVALS:return n
        except ValueError:pass
    return 24


def setup(store):
    from .jobs import next_run
    with store.repository.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        initialized=db.execute("SELECT value FROM state WHERE namespace='tasks' AND key='initialized'").fetchone()
        if initialized:
            saved=json.loads(initialized[0]); zone=os.environ.get('TZ')
            if zone and zone!=saved.get('timezone'):
                try:ZoneInfo(zone)
                except Exception:return
                for sid,cron in db.execute('SELECT id,cron FROM schedules').fetchall():
                    db.execute('UPDATE schedules SET timezone=?,next_run=? WHERE id=?',(zone,next_run(cron,zone),sid))
                saved['timezone']=zone
                db.execute("UPDATE state SET value=? WHERE namespace='tasks' AND key='initialized'",(json.dumps(saved),))
            return
        existing=db.execute('SELECT id,name,action,scope,cron,timezone,enabled,next_run FROM schedules').fetchall()
        zone=os.environ.get('TZ') or (existing[0][5] if existing else 'UTC')
        try:ZoneInfo(zone)
        except Exception:zone='UTC'
        # Preserve the original definitions for upgrade diagnostics, without deleting job history.
        db.execute("INSERT OR REPLACE INTO state VALUES('tasks','previous_schedules',?)",(json.dumps(existing),))
        for sid,name,action,scope,cron,old_zone,enabled,upcoming in existing:
            aligned=expression(hours_for(cron))
            db.execute('UPDATE schedules SET cron=?,timezone=?,next_run=? WHERE id=?',(aligned,zone,next_run(aligned,zone),sid))
        for action,scope,name,interval in DEFINITIONS:
            db.execute('INSERT INTO schedules(id,name,action,scope,cron,timezone,enabled,next_run) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(action,scope) DO UPDATE SET name=excluded.name',
                (str(uuid.uuid4()),name,action,scope,expression(interval),zone,int(interval>0),next_run(expression(interval),zone)))
        db.execute("INSERT OR REPLACE INTO state VALUES('tasks','initialized',?)",(json.dumps({'timezone':zone,'migrated':bool(existing)}),))


def payload(task):
    return {'scope':task['scope']} if task['action'] in ('sync','health') else {}


def rows(store):
    result=[]
    for task in store.schedules():
        predicate="(schedule_id=? OR (action=? AND COALESCE(json_extract(payload,'$.scope'),'all')=?))"
        params=(task['id'],task['action'],task['scope'])
        def latest(extra=''):
            found=store._rows('SELECT * FROM jobs WHERE '+predicate+extra+' ORDER BY created_at DESC LIMIT 1',params)
            return found[0] if found else None
        last=latest(' AND started_at IS NOT NULL')
        active=latest(" AND status IN ('queued','running','cancelling')")
        duration=None
        if last and last['finished_at']:duration=max(0,round((datetime.fromisoformat(last['finished_at'])-datetime.fromisoformat(last['started_at'])).total_seconds(),1))
        result.append({**task,'hours':hours_for(task['cron']) if task['enabled'] else 0,
            'fixed':task['action']=='check_updates','last_job':last,'latest_event':latest(),
            'active_job':active,'duration':duration,'next_run':task['next_run'] if task['enabled'] else None})
    return result
