"""Independent MusicBrainz preferences and local release ordering."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Preferences(BaseModel):
    enabled: bool = True
    cache_days: Literal[7, 30] = 7
    release_priority: list[Literal['Album', 'EP', 'Single', 'Other']] = Field(default_factory=lambda: ['Album','EP','Single','Other'])
    prefer_studio: bool = True
    retries: int = Field(default=2, ge=0, le=3)

    @model_validator(mode='after')
    def unique_types(self):
        if len(self.release_priority) != 4 or len(set(self.release_priority)) != 4:
            raise ValueError('Include Album, EP, Single and Other exactly once.')
        return self

def settings(repo):
    old = repo.load('lidarr').get('settings', {})
    return Preferences(**({'enabled':old.get('musicbrainz_enabled',True),'cache_days':old.get('cache_days',7)} | repo.load('musicbrainz_settings').get('preferences',{}))).model_dump()

def ordered(rows, preferences):
    priority = preferences['release_priority']
    def rank(row):
        secondary = {s.lower() for s in row.get('secondary_types',[])}
        special = bool(secondary & {'live','compilation','remix'})
        kind = row.get('type')
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
