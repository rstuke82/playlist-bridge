"""Read-only comparison of the last successful server inventories."""
import hashlib
import time
from fastapi import HTTPException


def compare(plex, lidarr):
    from .legacy import Matcher
    norm = Matcher._normalize_match_text
    def key(artist, album):
        return (norm(artist or ''), norm(album or ''))
    groups = {}
    for track in plex.get('rows', []):
        k = key(track.get('album_artist') or track.get('artist'), track.get('album'))
        groups.setdefault(k, []).append(track)
    catalog = {}
    for album in lidarr.get('rows', []):
        catalog.setdefault(key(album.get('artist'), album.get('title')), []).append(album)
    complete = bool(plex.get('checked_at') and lidarr.get('checked_at'))
    result = []
    for k in sorted(groups.keys() | catalog.keys()):
        tracks, albums = groups.get(k, []), catalog.get(k, [])
        first = albums[0] if albums else {}
        title = first.get('title') or (tracks[0].get('album') if tracks else '') or 'Unknown album'
        artist = first.get('artist') or (tracks[0].get('album_artist') or tracks[0].get('artist') if tracks else '')
        if not complete:
            status, reason = 'pending', 'Waiting for both library scans'
        elif not all(k) or len(albums) > 1:
            status, reason = 'review', 'Album identity needs review'
        elif tracks and not albums:
            status, reason = 'attention', 'Missing from Lidarr — review the album identity'
        elif not tracks:
            status, reason = 'lidarr_only', 'Not yet available in Plex'
        else:
            status, reason = 'linked', 'Linked by artist and album name'
        expected = max((int(a.get('statistics', {}).get('trackCount') or 0) for a in albums), default=0)
        unique = len({str(t.get('plex_id')) for t in tracks})
        result.append({'id': hashlib.sha256(repr(k).encode()).hexdigest(), 'artist': artist, 'album': title,
                       'status': status, 'reason': reason, 'plex_tracks': unique, 'expected_tracks': expected or None,
                       'completeness': 'unknown' if not expected else ('incomplete' if unique < expected else 'count_met'),
                       'lidarr_albums': albums, 'tracks': tracks})
    return {'rows': result, 'scans_complete': complete, 'plex_checked_at': plex.get('checked_at'),
            'lidarr_checked_at': lidarr.get('checked_at'),
            'note': 'Links use exact normalized artist and album names. Different editions may need review; matching counts do not prove identical recordings.'}


def register(app):
    from .api import _config,job_store
    from .inventory import current
    from .accounts import actor
    from .track_bridge import context,identity
    from pydantic import BaseModel,Field
    def read():
        config=_config(read_only=True,namespaces=[])
        plex,lidarr=current(config.repository,config)
        ctx=context(config,plex.get('rows',[])) or {'tracks':[],'links':{},'pending':True}
        return config,plex,lidarr,ctx
    @app.get('/api/library')
    def library():
        config,plex,lidarr,ctx=read()
        rows=[]
        from collections import defaultdict
        tracks=defaultdict(list)
        for t in ctx['tracks']:tracks[str(t.get('album_id'))].append(t)
        linked_ids={v['plex_id'] for v in ctx['links'].values()}
        for a in lidarr.get('rows',[]):
            ts=tracks[str(a.get('album_id'))];found=sum(str(t['id']) in ctx['links'] for t in ts)
            queue=[q for q in lidarr.get('queue',[]) if q.get('albumId')==a['id']]
            if ctx['pending'] or time.time()-plex.get('checked_at',0)>86400:status='Scan pending'
            elif ts and found==len(ts):status='Available'
            elif found:status='Partially Available'
            elif queue:status='Downloading'
            elif a.get('statistics',{}).get('trackFileCount',0)>0:status='Awaiting Plex'
            else:status='Awaiting Download'
            rows.append({**a,'status':status,'track_count':len(ts),'plex_count':found})
        errors=[{**r,'plex_id':'lidarr:'+str(r['id']),'album':r['title'],'reason':'Imported in Lidarr but not linked to playable Plex tracks.'} for r in rows if r['status']=='Awaiting Plex']
        if not ctx['pending'] and time.time()-plex.get('checked_at',0)<86400:
            for t in plex.get('rows',[]):
                if str(t['plex_id']) not in linked_ids:errors.append({**t,'status':'Needs Attention','reason':'Plex track not linked to Lidarr. It may be unmanaged or need an association.'})
        return {'rows':rows,'errors':errors,'plex_checked_at':plex.get('checked_at'),'lidarr_checked_at':lidarr.get('checked_at'),'tracks_scanned':'tracks' in lidarr}
    @app.get('/api/library/albums/{album_id}')
    def album(album_id:str):
        config,plex,lidarr,ctx=read()
        a=next((a for a in lidarr.get('rows',[]) if a.get('album_id')==album_id),None)
        if not a:raise HTTPException(404,'Album not found in the saved Lidarr library')
        from .lidarr import config as settings
        from .accounts import root_repository
        by_id={str(p['plex_id']):p for p in plex.get('rows',[])}
        tracks=[{**t,'link':ctx['links'].get(str(t['id'])),'plex':by_id.get(ctx['links'].get(str(t['id']),{}).get('plex_id'))} for t in ctx['tracks'] if t.get('album_id')==album_id]
        return {**a,'tracks':tracks,'lidarr_url':settings(root_repository()).get('url','').rstrip('/')+'/album/'+album_id}
    @app.get('/api/library/plex-tracks')
    def candidates(q:str=''):
        _,plex,_,_=read();terms=q.casefold().split()
        return [{k:t.get(k) for k in ('title','artist','album','plex_id')} for t in plex.get('rows',[]) if all(v in (' '.join(str(t.get(k,'')) for k in ('title','artist','album'))).casefold() for v in terms)][:100]
    class Link(BaseModel):
        plex_id:str | None=Field(default=None,max_length=100)
    @app.put('/api/library/tracks/{track_id}/link')
    def save_link(track_id:str,body:Link):
        if not actor() or not actor().get('admin'):raise HTTPException(403,'Administrator access required.')
        config,plex,lidarr,ctx=read()
        t=next((t for t in ctx['tracks'] if str(t['id'])==track_id),None)
        if not t or not t.get('file') or not ctx.get('scope'):raise HTTPException(409,'Import this track into Lidarr and run a current library scan before linking it.')
        from .lidarr import state_put
        import json
        from .accounts import root_repository
        with root_repository().connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT value FROM state WHERE namespace='track_links' AND key=?",(ctx['scope'],)).fetchone()
            values=json.loads(row[0]) if row else {}
            if body.plex_id is None:values.pop(track_id,None)
            else:
                p=next((p for p in plex.get('rows',[]) if str(p['plex_id'])==body.plex_id),None)
                if not p:raise HTTPException(409,'Plex track is no longer in the inventory.')
                values[track_id]={'plex_id':body.plex_id,'identity':list(identity(t)),'plex_identity':list(identity(p))}
            db.execute("INSERT OR REPLACE INTO state VALUES('track_links',?,?)",(ctx['scope'],json.dumps(values)))
        return {'saved':True}
