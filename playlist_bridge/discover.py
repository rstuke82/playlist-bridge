"""Last.fm discovery and user-safe album requests using server defaults."""
import uuid
import hashlib
import time
import threading
import requests
from fastapi import HTTPException, Query
from pydantic import BaseModel, Field
from .accounts import root_repository, actor, as_user, put
from .lidarr_downloads import Action as DownloadAction

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
            'mbid': a.get('mbid', ''), 'artwork': image, 'artist_mbid':artist.get('mbid','') if isinstance(artist,dict) else ''}


def availability(rows, apply_preferences=True):
    from .local_library import settings as local_settings, availability as local_availability
    if local_settings()["enabled"]:return local_availability(rows,apply_preferences)
    from .legacy import Matcher, Config
    from .inventory import current
    config=Config(read_only=True,namespaces=[])
    plex,lidarr=current(config.repository,config)
    normalize = Matcher._normalize_match_text
    def key(artist, album): return normalize(artist), normalize(album)
    p = {}
    for track in plex.get('rows',[]):
        p.setdefault(key(track.get('album_artist') or track.get('artist',''),track.get('album','')),[]).append(track)
    l = {}
    for t in lidarr.get('rows', []):l.setdefault(key(t.get('artist',''),t.get('title','')),[]).append(t)
    from .lidarr import config as lidarr_config
    base=lidarr_config(root_repository()).get('url','').rstrip('/')
    from .user_preferences import blocked, preferences
    prefs=preferences()
    from .track_bridge import context as track_context
    bridge=track_context(config,plex.get('rows',[])) if 'tracks' in lidarr else None
    plex_by_id={str(t['plex_id']):t for t in plex.get('rows',[])}
    associations=root_repository().load('album_links')
    by_mbid={a.get('album_id'):a for a in lidarr.get('rows',[]) if a.get('album_id')}
    seen = set()
    result = []
    fresh=bool(plex and lidarr and time.time()-min(plex.get('checked_at',0),lidarr.get('checked_at',0))<86400)
    for row in rows:
        k = key(row['artist'], row['album'])
        if k in seen or not all(k) or (apply_preferences and blocked(row)):
            continue
        seen.add(k)
        linked_id=associations.get(hashlib.sha256(repr(k).encode()).hexdigest(),{}).get('album_id')
        candidates=l.get(k,[])
        exact=[by_mbid[i] for i in (linked_id or row.get('mbid'),) if i in by_mbid]
        album=exact[0] if len(exact)==1 else candidates[0] if len(candidates)==1 else None
        tracks=p.get(key(album.get('artist',''),album.get('title','')),[]) if album else p.get(k,[])
        if album and bridge is not None:
            ids={bridge['links'].get(str(t['id']),{}).get('plex_id') for t in bridge['tracks'] if t.get('album_id')==album.get('album_id')}
            tracks=[plex_by_id[i] for i in ids if i in plex_by_id]
        ambiguous=bool((linked_id and linked_id not in by_mbid) or (len(candidates)>1 and not exact))
        status='Unknown'; explanation='Availability needs a current library scan.'
        queue=[q for q in lidarr.get('queue',[]) if album and (q.get('albumId')==album.get('id') or q.get('album',{}).get('id')==album.get('id'))]
        if fresh:
            if ambiguous:
                status='Needs Attention';explanation='Multiple Lidarr albums share this artist and title; their association needs review.'
            elif tracks and album:
                status='Available'; explanation='Confirmed in Plex and linked to Lidarr.'
                total=album.get('statistics',{}).get('trackCount')
                if total and len(tracks)<total:status='Partially Available';explanation=f'{len(tracks)}/{total} tracks found in Plex; edition counts may differ.'
            elif tracks:status='Needs Attention';explanation='Available in Plex, but not linked to Lidarr.'
            elif queue:
                from .lidarr_downloads import describe
                states=[describe(q)['status'] for q in queue]
                status='Importing' if 'Importing' in states else 'Downloading';explanation='In the active Lidarr download queue.'
                if any(x in ('Blocked','Import blocked','Failed') for x in states):status='Needs Attention';explanation='Lidarr reports a download or import problem.'
            elif album:
                status='Awaiting Plex' if album.get('statistics',{}).get('trackFileCount',0)>0 else 'Requested'
                explanation='Files found in Lidarr; waiting for Plex.' if status=='Awaiting Plex' else 'Added to Lidarr; no active download or available files.'
            else:status='Not Available';explanation='Not found in the latest Plex and Lidarr scans.'
        if apply_preferences and prefs.get('hide_available') and fresh and tracks and not ambiguous:continue
        from urllib.parse import quote
        first=tracks[0] if tracks else {}
        item=first.get('plex_album_id') or first.get('plex_id')
        machine=plex.get('machine_identifier')
        plex_url='https://app.plex.tv/desktop/#!/server/'+quote(str(machine),safe='')+'/details?key='+quote('/library/metadata/'+str(item),safe='') if machine and item else None
        lidarr_url=base+'/album/'+quote(str(album['album_id']),safe='') if actor() and actor().get('admin') and base and album and album.get('album_id') else None
        result.append({**row,'plex_url':plex_url,'lidarr_url':lidarr_url,'availability':status,'availability_detail':explanation,'checked_at':min(plex.get('checked_at',0),lidarr.get('checked_at',0)) or None,'lidarr_album_id':album.get('album_id') if album else None,'monitored':album.get('monitored') if album else None,'statistics':album.get('statistics',{}) if album else {},'releases':album.get('releases',[]) if album else [],'any_release_ok':album.get('anyReleaseOk') if album else None})
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

    @app.get('/api/discover/lidarr-albums')
    def link_candidates(q:str=Query(default='',max_length=200)):
        if not actor() or not actor().get('admin'):raise HTTPException(403,'Administrator access required.')
        rows=root_repository().load('inventory').get('lidarr',{}).get('rows',[])
        terms=q.casefold().split()
        return [{'album_id':r.get('album_id'),'title':r.get('title'),'artist':r.get('artist')} for r in rows if all(t in (r.get('artist','')+' '+r.get('title','')).casefold() for t in terms)][:100]

    class Link(BaseModel):
        artist:str=Field(min_length=1,max_length=300)
        album:str=Field(min_length=1,max_length=300)
        album_id:uuid.UUID | None = None
    @app.put('/api/discover/album-link')
    def link_album(body:Link):
        if not actor() or not actor().get('admin'):raise HTTPException(403,'Administrator access required.')
        from .legacy import Matcher
        k=tuple(Matcher._normalize_match_text(v) for v in (body.artist,body.album))
        key=hashlib.sha256(repr(k).encode()).hexdigest()
        if body.album_id is None:
            from .accounts import delete
            delete('album_links',key)
        else:
            if not any(a.get('album_id')==str(body.album_id) for a in root_repository().load('inventory').get('lidarr',{}).get('rows',[])):
                raise HTTPException(409,'Album not in the saved Lidarr library. Refresh the Lidarr scan first.')
            put('album_links',key,{'album_id':str(body.album_id),'artist':body.artist,'album':body.album})
        return {'saved':True}

    @app.get('/api/discover')
    def discover(q: str = Query(default='', max_length=160), username: str = Query(default='', max_length=100), artist: str = Query(default='',max_length=200), album: str = Query(default='',max_length=200), trending: bool=False):
        from .user_preferences import preferences
        if not username and not trending:username=preferences().get('lastfm_username','')
        if artist and album:
            data=lastfm('album.getInfo',artist=artist,album=album)
            return {'heading':album,'rows':availability([album_row(data.get('album',{}))]),'detail':True}
        if artist:
            data=lastfm('artist.getTopAlbums',artist=artist,limit=40)
            return {'heading':f'Top albums by {artist}','rows':availability([album_row(a) for a in data.get('topalbums',{}).get('album',[])])}
        if q.strip():
            data = lastfm('album.search', album=q.strip(), limit=30)
            rows = data.get('results', {}).get('albummatches', {}).get('album', [])
            heading = 'Album search'
        elif username.strip():
            data = lastfm('user.getTopAlbums', user=username.strip(), period='overall', limit=50)
            rows = data.get('topalbums', {}).get('album', [])
            heading = f'Top albums for {username.strip()}'
        else:
            artists = lastfm('chart.getTopArtists', limit=15).get('artists', {}).get('artist', [])
            groups=[]
            from .user_preferences import blocked
            for artist in artists:
                if blocked({'artist':artist['name'],'artist_mbid':artist.get('mbid','')}):continue
                groups.append(lastfm('artist.getTopAlbums',artist=artist['name'],limit=2).get('topalbums',{}).get('album',[]))
            rows=[group[i] for i in range(2) for group in groups if len(group)>i]
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
        from .user_preferences import blocked
        return {'rows': [{k: row.get(k) for k in ('album_id', 'title', 'artist', 'year', 'artwork', 'exists', 'type', 'secondary_types', 'query_score', 'query_exact')} for row in result['rows'] if not blocked(row)]}

    class Album(BaseModel):
        album_id: uuid.UUID
        title:str=Field(default='',max_length=500)
        artist:str=Field(default='',max_length=500)

    @app.post('/api/requests-user/add', status_code=202)
    def add(body: Album):
        user = permitted()
        if not user.get('admin') and user.get('auto_approve',True) is False:
            put('pending_requests',user['id']+':'+str(body.album_id),{**body.model_dump(mode='json'),'user_id':user['id'],'at':time.time()})
            return {'queued':False,'message':'Request submitted for administrator approval.'}
        from .lidarr import Preview, Confirm, config, Defaults
        # The selected release is resolved and reviewed against server defaults.
        # Users cannot override roots, profiles, tags, monitoring or search policy.
        with as_user(None):
            preview = endpoint('/api/lidarr/preview')(Preview(album_id=body.album_id, **Defaults(**config(root_repository())).model_dump()))
            endpoint('/api/lidarr/add')(Confirm(preview_id=preview['preview_id'],source_title=body.title,source_artist=body.artist))
        put('user_requests', user['id'] + ':' + str(body.album_id), {'user_id': user['id'], 'album_id': str(body.album_id), 'at': time.time()})
        return {'queued': True, 'message': 'Album requested. Status is available in Requests.'}

    def safe_requests(downloads=False):
        user=actor()
        if downloads and not (user.get('admin') or user.get('can_downloads') or user.get('can_manage_downloads')):
            raise HTTPException(403,'Download visibility is disabled for this account.')
        mine={r['album_id'] for r in root_repository().load('user_requests').values() if r.get('user_id')==user['id']}
        with as_user(None):
            records=endpoint('/api/lidarr/requests')()
        result=[]
        for r in records:
            if r['key'] not in mine and not downloads:continue
            fields=('key','title','artist','status','active','sources','availability','availability_detail','download_status','download_checked_at')
            value={k:r.get(k) for k in fields}
            value['album_id']=r['key'];value['display_status']=r.get('download_status') or r.get('availability','Unknown')
            value['detail']=r.get('availability_detail','')
            if user.get('admin') or user.get('can_downloads') or user.get('can_manage_downloads'):
                value['downloads']=[{k:d.get(k) for k in ('queue_id','download_id','title','status','percent','remaining')} for d in r.get('downloads',[])]
                value['lidarr_id']=r.get('lidarr_id')
            result.append(value)
        for key,r in root_repository().load('pending_requests').items():
            if r['user_id']==user['id'] and not downloads:
                result.append({'key':key,'album_id':r['album_id'],'title':r.get('title') or 'Album request','artist':r.get('artist'),'status':'approval','display_status':'Awaiting approval','sources':[{'title':r.get('title',''),'artist':r.get('artist','')}],'downloads':[]})
        return result

    @app.get('/api/requests-user')
    def own_requests():return safe_requests()

    @app.get('/api/requests-user/downloads')
    def downloads():return safe_requests(True)

    @app.post('/api/requests-user/{album}/download-action')
    def download_action(album:str,body:DownloadAction):
        if not (actor().get('admin') or actor().get('can_manage_downloads')):raise HTTPException(403,'Download management is disabled for this account.')
        from .lidarr_downloads import perform
        from .lidarr import config
        with as_user(None):return perform(root_repository(),config(root_repository()),album,body)

    @app.get('/api/requests-user/pending')
    def pending():
        if not actor().get('admin'):raise HTTPException(403,'Administrator access required.')
        return [{'key':k,**v} for k,v in root_repository().load('pending_requests').items()]

    @app.post('/api/requests-user/pending/{key}/approve')
    def approve(key:str):
        if not actor().get('admin'):raise HTTPException(403,'Administrator access required.')
        value=root_repository().load('pending_requests').get(key)
        if not value:raise HTTPException(404,'Pending request not found.')
        from .accounts import users,delete
        user=users().get(value['user_id'])
        if not user or user.get('disabled'):raise HTTPException(409,'Requestor is disabled or no longer exists.')
        with as_user({**user,'auto_approve':True}):result=add(Album(**value))
        delete('pending_requests',key)
        return result

    @app.delete('/api/requests-user/pending/{key}')
    def reject(key:str):
        if not actor().get('admin'):raise HTTPException(403,'Administrator access required.')
        from .accounts import delete
        delete('pending_requests',key)
        return {'removed':True}
