"""Read-only comparison of the last successful server inventories."""
import hashlib
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
    @app.get('/api/library')
    def library():
        from .api import _config, job_store
        from .inventory import current
        config = _config(read_only=True, namespaces=[])
        plex, lidarr = current(job_store().repository, config)
        result = compare(plex, lidarr)
        from .lidarr import config as lidarr_config
        from urllib.parse import quote
        base = lidarr_config(job_store().repository).get('url', '').rstrip('/')
        machine = plex.get('machine_identifier')
        for row in result['rows']:
            row['lidarr_url'] = base + '/album/' + quote(str(row['lidarr_albums'][0]['album_id']),safe='') if base and row['lidarr_albums'] and row['lidarr_albums'][0].get('album_id') else None
            first = row['tracks'][0] if row['tracks'] else {}
            item = first.get('plex_album_id') or first.get('plex_id')
            row['plex_url'] = 'https://app.plex.tv/desktop/#!/server/' + quote(str(machine),safe='') + '/details?key=' + quote('/library/metadata/' + str(item),safe='') if machine and item else None
        return result
