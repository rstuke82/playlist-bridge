"""Account-owned Discover preferences and artist exclusions."""
import hashlib
from fastapi import HTTPException
from pydantic import BaseModel, Field
from .accounts import personal_repository
from .lidarr import state_put


def normalize(value):
    from .legacy import Matcher
    return Matcher._normalize_match_text(value)


def preferences():
    return personal_repository().load('preferences').get('discover', {})


def blocked(row):
    credits = row.get('artists') or [{'name': row.get('artist', ''), 'mbid': row.get('artist_mbid', '')}]
    rules = personal_repository().load('blocked_artists').values()
    return any((r.get('mbid') and r['mbid'] == c.get('mbid')) or normalize(r['name']) == normalize(c.get('name', '')) for r in rules for c in credits)


def register(app):
    class Preferences(BaseModel):
        lastfm_username: str = Field(default='', max_length=100)
        hide_available: bool = False

    @app.get('/api/discover/preferences')
    def read():
        return Preferences(**preferences()).model_dump()

    @app.put('/api/discover/preferences')
    def save(body: Preferences):
        state_put(personal_repository(), 'preferences', 'discover', body.model_dump())
        return body.model_dump()

    class Artist(BaseModel):
        name: str = Field(min_length=1, max_length=250)
        mbid: str = Field(default='', max_length=36)

    @app.get('/api/discover/blocked-artists')
    def listing():
        return [{'id': k, **v} for k, v in personal_repository().load('blocked_artists').items()]

    @app.post('/api/discover/blocked-artists')
    def block(body: Artist):
        if not body.name.strip():
            raise HTTPException(422, 'Enter an artist name.')
        key = hashlib.sha256(normalize(body.name).encode()).hexdigest()
        state_put(personal_repository(), 'blocked_artists', key, body.model_dump())
        return {'id': key}

    @app.delete('/api/discover/blocked-artists/{key}')
    def unblock(key: str):
        with personal_repository().connect() as db:
            db.execute("DELETE FROM state WHERE namespace='blocked_artists' AND key=?", (key,))
        return {'removed': True}
