"""Admin aggregation; execution always remains in the owning account store."""
from . import accounts, jobs


def stores():
    root=accounts.root_repository()
    owner=next((u for u in accounts.users().values() if u.get('admin')),None)
    yield owner,jobs.Store(root)
    for user in accounts.users().values():
        if user.get('admin'):continue
        with accounts.as_user(user):
            yield user,jobs.Store(accounts.personal_repository())


def describe(row,user):
    return {**row,'owner_id':user['id'] if user else 'server','owner_name':user.get('name','Server') if user else 'Server'}


def listing():
    rows=[describe(row,user) for user,store in stores() for row in store.list()]
    return sorted(rows,key=lambda j:j['created_at'],reverse=True)


def resolve(job_id):
    from .api import job_store
    mine=job_store()
    if mine.get(job_id):return mine
    if accounts.actor() and accounts.actor().get('admin'):
        for user,store in stores():
            if store.get(job_id):return store
    return mine


def history(offset=0,limit=50,owner=''):
    rows=[];total=0
    for user,store in stores():
        if owner and str(user['id'] if user else 'server')!=owner:continue
        with store.repository.connect() as db:total+=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
        rows.extend(describe(r,user) for r in store._rows('SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?',(offset+limit,)))
    return {'rows':sorted(rows,key=lambda r:r['created_at'],reverse=True)[offset:offset+limit],'total':total}


def job(job_id):
    store=resolve(job_id);row=store.get(job_id)
    if not row:return None
    for user,candidate in stores():
        if candidate.repository.directory==store.repository.directory:return describe(row,user)
    return row
