"""Independent MusicBrainz preferences and local release ordering."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Preferences(BaseModel):
    server_url: str = "https://musicbrainz.org"
    enabled: bool = True
    cache_days: Literal[7, 30] = 7
    release_priority: list[Literal['Album', 'EP', 'Single', 'Other']] = Field(default_factory=lambda: ['Album','EP','Single','Other'])
    prefer_studio: bool = True
    retries: int = Field(default=2, ge=0, le=3)

    @model_validator(mode='after')
    def unique_types(self):
        from urllib.parse import urlsplit
        parsed = urlsplit(self.server_url.strip())
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Enter an HTTP(S) MusicBrainz server URL without credentials, query, or fragment.')
        self.server_url = self.server_url.strip().rstrip('/')
        if len(self.release_priority) != 4 or len(set(self.release_priority)) != 4:
            raise ValueError('Include Album, EP, Single and Other exactly once.')
        return self

def settings(repo):
    old = repo.load('lidarr').get('settings', {})
    return Preferences(**({'enabled':old.get('musicbrainz_enabled',True),'cache_days':old.get('cache_days',7)} | repo.load('musicbrainz_settings').get('preferences',{}))).model_dump()

def ordered(rows, preferences):
    priority = preferences['release_priority']
    def rank(row):
        secondary = {str(s).strip().casefold() for s in (row.get('secondary_types') or [])}
        special = bool(secondary & {'live','compilation','remix'})
        kind = next((p for p in priority if p.casefold() == str(row.get('type','')).strip().casefold()), 'Other')
        return (int(preferences['prefer_studio'] and special), priority.index(kind if kind in priority else 'Other'))
    return sorted(rows, key=rank)

def register(app):
    from .lidarr import repository, musicbrainz_search, Lookup, config, _mb_lock
    @app.get('/api/settings/musicbrainz')
    def get():
        repo = repository()
        return settings(repo) | {'cache_entries':len(repo.load('musicbrainz_cache'))}
    @app.put('/api/settings/musicbrainz')
    def put(request: Preferences):
        repository().save({'musicbrainz_settings':{'preferences':request.model_dump()}})
        return get()
    @app.delete('/api/settings/musicbrainz/cache')
    def clear():
        with _mb_lock:
            repository().save({'musicbrainz_cache':{}})
        return get()
    @app.post('/api/settings/musicbrainz/test')
    def test():
        import time
        repo = repository()
        start = time.monotonic()
        result = musicbrainz_search(repo,config(repo),Lookup(title='The Distance',artist='CAKE',album='Fashion Nugget',provider='musicbrainz',force_refresh=True), test=True)
        return {'message':f'MusicBrainz responded successfully in {time.monotonic()-start:.2f}s. {len(result["rows"])} album candidates returned.'}


def search_scores(rows,request):
    """Query similarity, not proof of recording identity; preserve edition text."""
    import re,unicodedata
    from difflib import SequenceMatcher
    def normalize(s):
        return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',s or '').casefold()).strip()
    fields=[('artist',request.artist),('title',request.album)]
    supplied=[(key,normalize(value)) for key,value in fields if value and value.lower() not in ('n/a','unknown')]
    result=[]
    for row in rows:
        score=round(sum(SequenceMatcher(None,q,normalize(row.get(k,''))).ratio() for k,q in supplied)/len(supplied)*100) if supplied else None
        exact=len(supplied)==2 and all(q==normalize(row.get(k,'')) for k,q in supplied)
        result.append({**row,'query_score':100 if exact else min(99,score) if score is not None else None,'query_exact':exact})
    return sorted(result,key=lambda r:(not r['query_exact'],-(r['query_score'] or 0)))
