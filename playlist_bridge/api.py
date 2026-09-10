"""FastAPI backend for Playlist Bridge 2.0."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from starlette.concurrency import run_in_threadpool
import contextlib
import io
import os
import threading
import time
import uuid
import json
import hashlib
import copy
from collections import Counter
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import network as requests

from . import __version__, __build__
from . import jobs
from datetime import datetime, timezone
from .legacy import (
    AppleMusicAPI,
    Config,
    Matcher,
    PlexAPI,
    ProcessLock,
    SpotifyAPI,
    Syncer,
    repair_text,
)
from .diagnostics import PlexDiagnosticError, plex_error, validate_plex_config, redact
from .notifications import WebhookNotifier, WebhookSettings


@contextlib.asynccontextmanager
async def lifespan(app):
    config = Config()
    config.repository.add_log("INFO", "startup", f"Playlist Bridge {__version__} started")
    manager = jobs.Manager(config.repository)
    manager.start()
    app.state.jobs = manager
    try:
        yield
    finally:
        await __import__("asyncio").to_thread(manager.close)


app = FastAPI(
    lifespan=lifespan,
    title="Playlist Bridge API",
    version=__version__,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlaylistAnalyzeRequest(BaseModel):
    url: str


class PlaylistAddRequest(BaseModel):
    url: str
    analysis_id: Optional[str] = None
    auto_sync: bool = True
    favorite: bool = False


class PlaylistUpdateRequest(BaseModel):
    favorite: Optional[bool] = None
    auto_sync: Optional[bool] = None




class PlexDiscoverRequest(BaseModel):
    url: str
    token: str = ""


class PlexSettingsRequest(BaseModel):
    url: str
    token: str = ""
    music_library_key: str

class MissingCandidateRequest(BaseModel):
    title: str
    artist: str
    album: str = ""
    query: str = ""
    limit: int = Field(default=10, ge=1, le=50)


class MissingMatchRequest(BaseModel):
    title: str
    artist: str
    album: str = ""
    plex_id: str
    playlist_keys: Optional[List[str]] = None
    replace_playlist_key: Optional[str] = None
    provenance: Literal["manual", "automatic"] = "manual"


class NotificationSettingsRequest(BaseModel):
    enabled: bool = False
    url: str = ""
    notify_sync_failures: bool = True
    notify_lost_matches: bool = True
    notify_unresolved: bool = True
    notify_source_changes: bool = True
    notify_successful_syncs: bool = False
    notify_sync_all_summary: bool = True


def _config(read_only=False, namespaces=None) -> Config:
    return Config(read_only=read_only, namespaces=namespaces)


def _playlist_key(playlist: dict) -> str:
    return f"{playlist.get('source', '')}:{playlist.get('source_id', '')}"


def _playlist_payload(config: Config, playlist: dict) -> dict:
    key = _playlist_key(playlist)
    missing = config.missing.get(key, [])
    counts = Counter(Syncer(config)._get_match_provenance(key, search_key) for search_key in config.mapping.get(key, {}))
    return {
        "match_counts": {name: counts.get(name, 0) for name in ('automatic','manual','legacy')},
        "fully_matched": bool(config.health.get(key) and config.health[key].get('source_tracks', 0)>0 and config.health[key].get('unresolved')==0 and config.health[key].get('ignored',0)==0 and config.health[key].get('matched_in_library')==config.health[key].get('source_tracks')),
        "key": key,
        "name": playlist.get("plex_playlist_name", ""),
        "source": playlist.get("source", ""),
        "source_url": playlist.get("source_url", ""),
        "source_id": playlist.get("source_id", ""),
        "plex_playlist_id": playlist.get("plex_playlist_id", ""),
        "favorite": playlist.get("favorite", False) is True,
        "auto_sync": playlist.get("auto_sync", True) is not False,
        "last_synced": playlist.get("last_synced"),
        "added_at": playlist.get("added_at"),
        "last_match_attempt": playlist.get("last_match_attempt"),
        "saved_matches": len(config.mapping.get(key, {})),
        "unresolved": len(missing),
        "lost": sum(1 for track in missing if track.get("status") == "lost"),
        "ignored": len(config.ignored_tracks.get(key, {})),
        "health": config.health.get(key),
        "health_attempt": config.health_attempts.get(key),
    }


def _source_for_url(url: str):
    normalized = Config._normalize_url_input(url)
    lower = normalized.lower()
    if "spotify.com" in lower or lower.startswith("spotify:playlist:"):
        return "spotify", normalized, SpotifyAPI()
    if "music.apple.com" in lower or "itunes.apple.com" in lower:
        return "applemusic", normalized, AppleMusicAPI()
    raise HTTPException(status_code=400, detail="URL must be a Spotify or Apple Music playlist")


def _record_log(level, operation, message, config=None):
    try:
        config = config or _config(read_only=True, namespaces=[])
        context = jobs.current()
        config.repository.add_log(level, context.action if context else operation, redact(message, config))
        if context:
            context.store.event(context.id, message, operation)
    except Exception:
        # A diagnostic failure must not turn a successful sync into an error.
        pass


@app.middleware("http")
async def log_operations(request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        await run_in_threadpool(_record_log, "ERROR", "request", f"{request.method} request failed unexpectedly. Check the server console.")
        raise
    route = request.scope.get("route")
    path = getattr(route, "path", "")
    if path.startswith("/api/") and path not in ("/api/health", "/api/settings/logs"):
        if request.method != "GET" or response.status_code >= 400:
            await run_in_threadpool(_record_log, "ERROR" if response.status_code >= 400 else "INFO", path,
                        f"{request.method} completed with HTTP {response.status_code}")
    if request.url.path.startswith('/assets/') and response.status_code == 200:
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif not request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
    return response


def _capture(callable_obj, *args, **kwargs):
    # Thread-local capture avoids redirecting unrelated requests' stdout.
    previous = getattr(jobs._local, 'output', None)
    buffer = []
    jobs._local.output = buffer
    try:
        result = callable_obj(*args, **kwargs)
        output = redact("\n".join(buffer), _config(read_only=True, namespaces=[]))
        return result, output
    finally:
        jobs._local.output = previous


_analysis_cache = {}
_analysis_lock = threading.Lock()
ANALYSIS_TTL = 600


def _analysis_fingerprint(config):
    data = [config.config.get('plex'), config.ignored_tracks, config.artist_aliases,
            config.mapping, config.match_metadata]
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def _health_plex(config):
    settings = validate_plex_config(config)
    return PlexAPI(settings['url'], settings['token'], settings['music_library_key'],
                   settings.get('music_library_name', ''), strict_errors=True)


def _validated_plex_libraries(url: str, token: str) -> List[dict]:
    base_url = str(url or "").strip().rstrip("/")
    plex_token = str(token or "").strip()
    if not base_url or not plex_token:
        raise HTTPException(status_code=400, detail="Plex URL and token are required")

    try:
        response = requests.get(
            f"{base_url}/identity",
            headers={"X-Plex-Token": plex_token},
            timeout=8,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not connect to Plex: {exc}") from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Plex connection failed (HTTP {response.status_code}). Check the URL and token.",
        )

    try:
        libraries = Config._get_plex_music_libraries(base_url, plex_token)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not libraries:
        raise HTTPException(status_code=400, detail="No Plex music libraries were found")

    return libraries


@app.get("/api/health")
def health():
    config = _config(read_only=True, namespaces=[])
    from .updates import stored_status
    playlists = config.config.get("playlists", [])
    unresolved = 0
    lost = 0
    for playlist in playlists:
        tracks = config.missing.get(_playlist_key(playlist), [])
        unresolved += len(tracks)
        lost += sum(1 for track in tracks if track.get("status") == "lost")

    return {
        "status": "ok",
        "version": __version__,
        "release_name": "Playlist Bridge 2.0",
        "update": stored_status(config.repository),
        "build": __build__,
        "playlists": len(playlists),
        "favorites": sum(1 for p in playlists if p.get("favorite") is True),
        "unresolved": unresolved,
        "lost": lost,
        "plex_configured": bool(
            config.config.get("plex", {}).get("url")
            and config.config.get("plex", {}).get("token")
        ),
    }


@app.get("/api/playlists")
def list_playlists():
    config = _config(read_only=True, namespaces=[])
    return [
        _playlist_payload(config, playlist)
        for playlist in config.config.get("playlists", [])
    ]


@app.patch("/api/playlists/{playlist_key:path}")
def update_playlist(playlist_key: str, request: PlaylistUpdateRequest):
    with ProcessLock():
        config = _config()
        playlist = next(
            (p for p in config.config.get("playlists", []) if _playlist_key(p) == playlist_key),
            None,
        )
        if playlist is None:
            raise HTTPException(status_code=404, detail="Playlist not found")

        if request.favorite is not None:
            playlist["favorite"] = request.favorite
        if request.auto_sync is not None:
            playlist["auto_sync"] = request.auto_sync
        config.save()
        return _playlist_payload(config, playlist)


def analyze_playlist(request: PlaylistAnalyzeRequest):
    config = _config(read_only=True)
    source_type, url, source_api = _source_for_url(request.url)
    playlist_id = Config._extract_id(url, source_type)
    if not playlist_id:
        raise HTTPException(status_code=400, detail="Could not extract playlist ID")

    if config.find_playlist(url):
        raise HTTPException(status_code=409, detail="Playlist is already registered")

    try:
        jobs.progress("Reading source playlist")
        (tracks, metadata), source_log = _capture(
            source_api.get_playlist_tracks,
            url,
            fetch_artwork=False,
        )
        jobs.target('job', repair_text(metadata.get('name', 'Source playlist')))
        jobs.progress("Matching source tracks against Plex")
        syncer = Syncer(config)
        syncer.plex = _health_plex(config)
        match_result, match_log = _capture(
            syncer._match_source_tracks,
            tracks,
            f"api-analyze:{source_type}:{playlist_id}",
            record_provenance=False,
            mark_new_matches=False,
        )
        matched, unmatched, _mapping, _library, stats = match_result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    analysis_id = str(uuid.uuid4())
    with _analysis_lock:
        for key in list(_analysis_cache):
            if _analysis_cache[key]['expires'] < time.monotonic():
                del _analysis_cache[key]
        while len(_analysis_cache) >= 10:
            del _analysis_cache[next(iter(_analysis_cache))]
        _analysis_cache[analysis_id] = {
            'expires': time.monotonic() + ANALYSIS_TTL, 'url': url,
            'fingerprint': _analysis_fingerprint(config),
            'tracks': tracks, 'metadata': metadata, 'result': match_result,
        }
    return {
        "analysis_id": analysis_id,
        "expires_in": ANALYSIS_TTL,
        "source": source_type,
        "source_id": playlist_id,
        "url": url,
        "name": repair_text(metadata.get("name", "Unknown Playlist")),
        "description": repair_text(metadata.get("description", "")),
        "source_tracks": len(tracks),
        "matched": len(matched),
        "unresolved": len(unmatched),
        "ignored": len(stats.get("ignored_tracks", [])),
        "log": (source_log + match_log).strip(),
    }


def add_playlist(request: PlaylistAddRequest):
    with ProcessLock():
        config = _config()
        source_type, url, source_api = _source_for_url(request.url)
        playlist_id = Config._extract_id(url, source_type)
        if not playlist_id:
            raise HTTPException(status_code=400, detail="Could not extract playlist ID")
        if config.find_playlist(url):
            raise HTTPException(status_code=409, detail="Playlist is already registered")

        try:
            jobs.progress("Connecting to Plex")
            plex = _health_plex(config)
            cached = None
            if request.analysis_id:
                with _analysis_lock:
                    cached = copy.deepcopy(_analysis_cache.get(request.analysis_id))
                if (not cached or cached['expires'] < time.monotonic() or cached['url'] != url
                        or cached['fingerprint'] != _analysis_fingerprint(config)):
                    raise HTTPException(409, "Analysis expired or matching settings changed. Analyze again or choose Add Now.")
            syncer = Syncer(config)
            syncer.plex = plex
            mapping_key = f"{source_type}:{playlist_id}"
            if cached:
                jobs.progress("Reusing analyzed source tracks and matches")
                tracks, metadata = cached['tracks'], cached['metadata']
                jobs.target('job', repair_text(metadata.get('name', 'Source playlist')))
                matched, unmatched, mapping, _library, _stats = cached['result']
                lookup = {str(t.get('plex_id')): t for t in _library or []}
                for search_key, plex_id in mapping.items():
                    syncer._set_match_provenance(mapping_key, search_key, 'automatic',
                        matched_track=lookup.get(str(plex_id)), plex_id=plex_id)
            else:
                jobs.progress("Reading source playlist and artwork")
                tracks, metadata = source_api.get_playlist_tracks(url, fetch_artwork=True)
                jobs.target('job', repair_text(metadata.get('name', 'Source playlist')))
                jobs.progress("Matching tracks against the Plex library")
                matched, unmatched, mapping, _library, _stats = syncer._match_source_tracks(
                    tracks, mapping_key, mark_new_matches=False)
            if not tracks:
                raise HTTPException(422, "Source returned no tracks. Check that the playlist is public and its URL is correct.")
            syncer._store_unmatched(mapping_key, unmatched)
            config.mapping[mapping_key] = mapping

            if not matched:
                raise HTTPException(
                    status_code=422,
                    detail="No source tracks matched Plex, so the playlist was not created",
                )

            jobs.progress(f"Creating Plex playlist with {len(matched)} matched tracks; {len(unmatched)} unresolved")
            plex_playlist_id = syncer._build_new_plex_playlist(
                metadata.get("name", "Unknown Playlist"),
                metadata.get("description", ""),
                matched,
                metadata.get("image_url", ""),
            )
            if not plex_playlist_id:
                raise HTTPException(status_code=502, detail="Plex playlist creation failed")

            jobs.progress("Saving playlist registration and source snapshot", check=False)
            playlist = config.add_playlist(
                url,
                source_type,
                metadata.get("name", "Unknown Playlist"),
                plex_playlist_id,
            )
            playlist["auto_sync"] = request.auto_sync
            playlist["favorite"] = request.favorite
            from datetime import datetime
            playlist["added_at"] = datetime.now(timezone.utc).isoformat()
            # Preserve the registration even if Plex accepted only part of the update.
            # This gives the user a repair target instead of creating duplicates on retry.
            verification_error = None
            try:
                actual = plex.get_playlist_items(str(plex_playlist_id))
                from .verification import compare, describe
                verification = compare(matched, actual)
                if not verification['ok']:
                    verification_error = describe(verification)
                elif verification['duplicates_collapsed']:
                    jobs.output(f"⚠ Plex collapsed {verification['duplicates_collapsed']} repeated occurrences; completed with a server limitation.")
            except Exception as exc:
                verification_error = f"Could not verify the new Plex playlist: {exc}"
            if not verification_error:
                playlist["last_synced"] = datetime.now(timezone.utc).isoformat()
            syncer._save_source_snapshot(mapping_key, tracks)
            config.save()
            if not verification_error:
                from .sync_health import persist_sync_health
                persist_sync_health(config, playlist, tracks, matched, unmatched, _stats, actual)
            if request.analysis_id:
                with _analysis_lock:
                    _analysis_cache.pop(request.analysis_id, None)
            result = _playlist_payload(config, playlist)
            if verification_error:
                ctx = jobs.current()
                if ctx:
                    ctx.store.update(ctx.id, result=result)
                raise HTTPException(status_code=502, detail=f"Playlist was created and registered, but {verification_error} Open it in Playlists and sync to repair; do not add it again.")
            return result
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc


def sync_all():
    with ProcessLock():
        config = _config()
        result, log = _capture(Syncer(config).sync_all)
        return {"summary": result, "log": log}


def sync_favorites():
    with ProcessLock():
        config = _config()
        result, log = _capture(Syncer(config).sync_favorites)
        return {"summary": result, "log": log}


def sync_one(playlist_key: str):
    with ProcessLock():
        config = _config()
        playlist = next(
            (p for p in config.config.get("playlists", []) if _playlist_key(p) == playlist_key),
            None,
        )
        if playlist is None:
            raise HTTPException(status_code=404, detail="Playlist not found")
        result, log = _capture(Syncer(config).sync_playlist, playlist)
        return {"summary": result, "log": log, "health": config.repository.load('health').get(playlist_key)}


def _health_call(fn, *args, **kwargs):
    return fn(*args, **kwargs), ""


def playlist_health(playlist_key: str):
    """Read-only source/Plex comparison. Only health results/history are persisted."""
    config = _config(read_only=True)
    playlist = next(
        (p for p in config.config.get("playlists", []) if _playlist_key(p) == playlist_key),
        None,
    )
    if playlist is None:
        raise HTTPException(status_code=404, detail="Playlist not found")

    jobs.progress("Connecting to Plex")
    stage = "Plex connection"
    _record_log("INFO", "health", f"Checking health: {playlist.get('plex_playlist_name', playlist_key)}", config)
    try:
        syncer = Syncer(config)
        plex = _health_plex(config)
        syncer.plex = plex
        jobs.progress("Reading source playlist")
        stage = "source playlist"
        source_type, source_url, source_api = _source_for_url(playlist.get("source_url", ""))
        (source_tracks, _metadata), source_log = _health_call(
            source_api.get_playlist_tracks,
            source_url,
            fetch_artwork=False,
        )

        jobs.progress("Checking Plex library matches")
        stage = "Plex library"
        plex_library, library_log = _health_call(plex.search_library, "")
        if not plex_library:
            raise HTTPException(status_code=502, detail="The selected Plex music library returned no tracks. Check the library selection in Settings → Plex.")

        mapping_key = _playlist_key(playlist)
        match_result, match_log = _health_call(
            syncer._match_source_tracks,
            source_tracks,
            mapping_key,
            plex_library=plex_library,
            record_provenance=False,
            mark_new_matches=False,
        )
        matched_ids, unmatched, _mapping, _library, stats = match_result

        jobs.progress("Comparing destination playlist")
        stage = "Plex destination playlist"
        plex_playlist_id = str(playlist.get("plex_playlist_id", ""))
        plex_items, playlist_log = _health_call(plex.get_playlist_items, plex_playlist_id)
        actual_ids = [
            str(item.get("plex_id"))
            for item in plex_items
            if item.get("plex_id") is not None
        ]

        expected = Counter(str(value) for value in matched_ids)
        actual = Counter(actual_ids)
        from .verification import compare
        verification = compare(matched_ids, plex_items)
        if verification['duplicates_collapsed']:
            expected = actual.copy()
        missing_from_plex = sum((expected - actual).values())
        extra_in_plex = sum((actual - expected).values())

        source_changes = syncer._source_change_report(mapping_key, source_tracks)
        source_added = 0 if source_changes.get("baseline") else len(source_changes.get("added", []))
        source_removed = 0 if source_changes.get("baseline") else len(source_changes.get("removed", []))
        ignored = len(stats.get("ignored_tracks", []))
        unresolved = len(unmatched)
        plex_count = len(actual_ids)

        lookup = {str(t.get("plex_id")): t for t in [*plex_items, *plex_library]}
        def differences(counts):
            return [{"plex_id": key, "title": lookup.get(key, {}).get("title", key),
                     "artist": lookup.get(key, {}).get("artist", ""), "count": count}
                    for key, count in counts.items()]
        result = {
            "key": mapping_key,
            "name": playlist.get("plex_playlist_name", ""),
            "source": source_type,
            "source_tracks": len(source_tracks),
            "plex_playlist_tracks": plex_count,
            "matched_in_library": len(matched_ids),
            "unresolved": unresolved,
            "lost": sum(1 for track in unmatched if track.get("status") == "lost"),
            "ignored": ignored,
            "missing_from_plex_playlist": missing_from_plex,
            "extra_in_plex_playlist": extra_in_plex,
            "source_added_since_last_sync": source_added,
            "source_removed_since_last_sync": source_removed,
            "healthy": (
                unresolved == 0
                and missing_from_plex == 0
                and extra_in_plex == 0
                and source_added == 0
                and source_removed == 0
                and verification['ok']
            ),
            "duplicates_collapsed": verification['duplicates_collapsed'],
            "read_only": True,
            "drift_details": {
                "missing_from_plex": differences(expected - actual),
                "extra_in_plex": differences(actual - expected),
                "unresolved": unmatched,
                "source_added": source_changes.get("added", []),
                "source_removed": source_changes.get("removed", []),
            },
            "source_preview": [{k:t.get(k, "") for k in ("title","artist","album","source_id")} for t in source_tracks],
            "log": "\n".join(part for part in [source_log, library_log, match_log, playlist_log] if part).strip(),
        }
        config.repository.save_health(mapping_key, result)
        config.repository.record_health_attempt(mapping_key)
        _record_log("INFO", "health", f"Health check completed: {playlist.get('plex_playlist_name', playlist_key)}", config)
        return result
    except Exception as exc:
        if isinstance(exc, HTTPException):
            message = str(exc.detail)
        elif isinstance(exc, PlexDiagnosticError) or stage.startswith("Plex"):
            message = plex_error(exc)
        else:
            message = 'Could not read the source playlist. Check that its URL is correct and the playlist is public, then retry.'
        message = redact(f"Health check failed — {stage}: {message}", config)
        config.repository.record_health_attempt(playlist_key, message)
        _record_log("ERROR", "health", message, config)
        raise HTTPException(status_code=502, detail=message) from exc


def playlist_detail(playlist_key: str, report=lambda message, percent: None):
    config = _config(read_only=True)
    playlist = next((p for p in config.config.get("playlists", []) if _playlist_key(p) == playlist_key), None)
    if playlist is None:
        raise HTTPException(status_code=404, detail="Playlist not found")
    try:
        _, url, source = _source_for_url(playlist.get("source_url", ""))
        report("Loading source playlist", 5)
        tracks, metadata = source.get_playlist_tracks(url, fetch_artwork=False)
        report(f"{len(tracks)} source tracks found; loading Plex library", 25)
        syncer = Syncer(config)
        library = {str(t.get("plex_id")): t for t in _health_plex(config).search_library("")}
        report("Resolving saved matches", 50)
        rows = []
        for index, track in enumerate(tracks):
            if index % 10 == 0:
                report(f"Comparing tracks {index + 1} / {len(tracks)}", 50 + int(45 * (index + 1) / max(1, len(tracks))))
            search_key = f"{track.get('title', '')}|{track.get('artist', '')}"
            plex_id = config.mapping.get(playlist_key, {}).get(search_key)
            match = library.get(str(plex_id)) if plex_id is not None else None
            status = syncer._get_match_provenance(playlist_key, search_key).capitalize() if match else ('LOST' if plex_id else 'Unresolved')
            if not match and any(t.get('status') == 'lost' and syncer._same_missing_identity(t, track) for t in config.missing.get(playlist_key, [])):
                status = 'LOST'
            if syncer._find_ignored_track_key(playlist_key, track):
                status = 'Ignored'
            rows.append({**track, "index": index, "status": status, "match": match, "plex_id": plex_id})
        report("Playlist details ready", 100)
        return {"playlist": _playlist_payload(config, playlist), "metadata": metadata, "tracks": rows}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=redact("Could not load playlist details: " + str(exc), config)) from exc


# A separate, bounded pool keeps slow external I/O away from lightweight routes.
DETAIL_TIMEOUT = 60
_detail_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="playlist-detail")
_detail_slots = threading.BoundedSemaphore(2)

_detail_progress = {}
_detail_progress_lock = threading.Lock()


@app.get('/api/detail-progress/{progress_id}')
def detail_progress(progress_id: str):
    with _detail_progress_lock:
        return _detail_progress.get(progress_id, {'events': [], 'percent': 0})


@app.get("/api/playlists/{playlist_key:path}/detail")
async def playlist_detail_route(playlist_key: str, progress_id: str = Query(default='', max_length=100)):
    def report(message, percent):
        if not progress_id:
            return
        with _detail_progress_lock:
            item = _detail_progress.get(progress_id)
            if item and not item.get('done'):
                item['events'].append({'message': message, 'created_at': jobs.now()})
                item['percent'] = percent
    with _detail_progress_lock:
        for key in list(_detail_progress):
            if time.monotonic() - _detail_progress[key]['created'] > 180:
                del _detail_progress[key]
        if progress_id:
            if len(_detail_progress) >= 100:
                del _detail_progress[next(iter(_detail_progress))]
            _detail_progress[progress_id] = {'events': [], 'percent': 0, 'created': time.monotonic()}
    report('Loading playlist', 0)
    if not _detail_slots.acquire(blocking=False):
        raise HTTPException(503, "Playlist details are busy. Please retry shortly.")
    try:
        future = _detail_pool.submit(playlist_detail, playlist_key, report)
    except BaseException:
        _detail_slots.release()
        raise
    # Keep the slot occupied after a timeout until the actual worker exits.
    future.add_done_callback(lambda _: _detail_slots.release())
    wrapped = asyncio.wrap_future(future)
    wrapped.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
    try:
        return await asyncio.wait_for(asyncio.shield(wrapped), DETAIL_TIMEOUT)
    except asyncio.TimeoutError:
        report("Timed out after 60 seconds. Check source/Plex connectivity and retry.", 0)
        raise HTTPException(504, "Playlist details timed out after 60 seconds. Check source/Plex connectivity and retry.") from None
    finally:
        with _detail_progress_lock:
            if progress_id in _detail_progress:
                _detail_progress[progress_id]['done'] = True


@app.get("/api/settings/plex")
def get_plex_settings():
    config = _config(read_only=True, namespaces=[])
    plex = config.config.get("plex", {})
    token = str(plex.get("token", ""))
    return {
        "url": plex.get("url", ""),
        "token_configured": bool(token),
        "token_hint": (f"••••{token[-4:]}" if len(token) >= 4 else ("••••" if token else "")),
        "music_library_key": str(plex.get("music_library_key", "")),
        "music_library_name": plex.get("music_library_name", ""),
    }


@app.post("/api/settings/plex/discover")
def discover_plex_libraries(request: PlexDiscoverRequest):
    config = _config(read_only=True, namespaces=[])
    existing = config.config.get("plex", {})
    token = request.token.strip() or str(existing.get("token", "")).strip()
    libraries = _validated_plex_libraries(request.url, token)
    return {"libraries": libraries}


@app.put("/api/settings/plex")
def put_plex_settings(request: PlexSettingsRequest):
    with ProcessLock():
        config = _config()
        existing = config.config.get("plex", {})
        token = request.token.strip() or str(existing.get("token", "")).strip()
        libraries = _validated_plex_libraries(request.url, token)
        selected = next((library for library in libraries if library["key"] == str(request.music_library_key)), None)
        if selected is None:
            raise HTTPException(status_code=400, detail="Select a valid Plex music library")

        config.config["plex"] = {
            "url": request.url.strip().rstrip("/"),
            "token": token,
            "music_library_key": selected["key"],
            "music_library_name": selected["name"],
        }
        config.save()
        return {
            "url": config.config["plex"]["url"],
            "token_configured": True,
            "token_hint": f"••••{token[-4:]}" if len(token) >= 4 else "••••",
            "music_library_key": selected["key"],
            "music_library_name": selected["name"],
            "connected": True,
        }


@app.get("/api/missing")
def missing_tracks(scope: Literal["all", "favorites"] = "all"):
    config = _config(read_only=True, namespaces=[])
    playlists = config.config.get("playlists", [])
    if scope == "favorites":
        playlists = [p for p in playlists if p.get("favorite") is True]
    syncer = Syncer(config)
    rows = syncer.collect_all_missing_tracks_deduped(playlists=playlists)
    for row in rows:
        members = []
        for playlist in playlists:
            key = _playlist_key(playlist)
            matches = [t for t in config.missing.get(key, []) if syncer._same_missing_identity(t, row)]
            if matches:
                members.append({"key":key, "name":playlist.get("plex_playlist_name", key),
                                "count":len(matches), "last_checked":playlist.get("last_match_attempt") or playlist.get("last_synced")})
        row['memberships'] = members
        row['playlist_count'] = len(members)
        row['last_checked'] = max((m['last_checked'] for m in members if m['last_checked']), default=None)
    return rows


@app.post("/api/missing/candidates")
def missing_candidates(request: MissingCandidateRequest):
    config = _config(read_only=True)
    syncer = Syncer(config)
    plex = syncer._get_plex()
    library = plex.search_library("")
    source = {
        "title": request.title,
        "artist": request.artist,
        "album": request.album,
    }
    rows = []
    for track in library:
        if request.query and request.query.casefold() not in " ".join(str(track.get(k, "")) for k in ("title", "artist", "album")).casefold():
            continue
        details = Matcher.score_candidate(source, track)
        rows.append(
            {
                "plex_id": str(track.get("plex_id", "")),
                "title": track.get("title", ""),
                "artist": track.get("artist", ""),
                "album": track.get("album", ""),
                "score": round(details["adjusted_score"], 1),
                "identity_score": round(details["identity_score"], 1),
                "title_score": details["title_score"],
                "artist_score": details["artist_score"],
                "album_score": details["album_score"],
                "album_penalty": details["album_penalty"],
                "title_variant_penalty": details["title_variant_penalty"],
                "release_intent_penalty": details["release_intent_penalty"],
            }
        )
    rows.sort(
        key=lambda row: (
            row["score"],
            row["identity_score"],
            row["title_score"],
            row["artist_score"],
            row["album_score"] or 0,
        ),
        reverse=True,
    )
    return rows[: request.limit]


def save_missing_match(request: MissingMatchRequest):
    with ProcessLock():
        config = _config()
        syncer = Syncer(config)
        playlists = config.config.get("playlists", [])
        if request.playlist_keys is not None:
            wanted = set(request.playlist_keys)
            playlists = [p for p in playlists if _playlist_key(p) in wanted]

        source_track = {
            "title": request.title,
            "artist": request.artist,
            "album": request.album,
        }
        affected_playlists = syncer._playlists_containing_missing_track(
            source_track,
            playlists,
        )

        plex = syncer._get_plex()
        selected = next(
            (track for track in plex.search_library("") if str(track.get("plex_id")) == request.plex_id),
            None,
        )
        if selected is None:
            raise HTTPException(status_code=404, detail="Plex track not found")

        target = None
        if request.replace_playlist_key:
            target = next((p for p in config.config.get("playlists", [])
                           if _playlist_key(p) == request.replace_playlist_key), None)
            if target is None:
                raise HTTPException(status_code=404, detail="Playlist not found")
            if target not in affected_playlists and any(
                syncer._same_missing_identity(t, source_track)
                for t in config.missing.get(request.replace_playlist_key, [])
            ):
                affected_playlists.append(target)

        if request.provenance == 'automatic':
            automatic_id = Matcher.match_track(source_track, plex.search_library(''), {})
            if str(automatic_id) != request.plex_id:
                raise HTTPException(409, 'The automatic candidate has changed. Retry automatic matching before applying it.')
        jobs.progress("Saving " + request.provenance + " match")
        affected = syncer._apply_global_missing_match(source_track, selected, affected_playlists)

        if request.provenance == 'automatic':
            for affected_playlist in affected_playlists:
                affected_key = _playlist_key(affected_playlist)
                for search_key, value in config.mapping.get(affected_key, {}).items():
                    title, _, artist = search_key.partition('|')
                    if str(value) == request.plex_id and syncer._same_missing_identity({'title':title,'artist':artist}, source_track):
                        syncer._set_match_provenance(affected_key, search_key, 'automatic', matched_track=selected, plex_id=request.plex_id)
            config.save()
        if target is not None:
            key = request.replace_playlist_key
            search_key = f"{request.title}|{request.artist}"
            config.mapping.setdefault(key, {})[search_key] = request.plex_id
            syncer._set_match_provenance(key, search_key, request.provenance, matched_track=selected, plex_id=request.plex_id)
            config.save()
            if target not in affected_playlists:
                affected_playlists.append(target)
                affected += 1

        sync_results = []
        combined_log = []
        for index, playlist in enumerate(affected_playlists):
            jobs.target(_playlist_key(playlist), playlist.get('plex_playlist_name',''), index+1, len(affected_playlists))
            jobs.progress("Syncing affected playlist: " + playlist.get("plex_playlist_name", ""))
            result, log = _capture(syncer.sync_playlist, playlist)
            jobs.activity(mode='failed' if result.get('errors') else 'completed', stage='Playlist update finished')
            sync_results.append({
                "key": _playlist_key(playlist),
                "name": playlist.get("plex_playlist_name", ""),
                "summary": result,
                "ok": not result.get('errors'),
            })
            ctx = jobs.current()
            if ctx:
                ctx.store.update(ctx.id, result={'affected': affected, 'total': len(affected_playlists),
                    'synced_playlists': len(sync_results), 'playlists': sync_results})
            if log:
                combined_log.append(log)

        if any(p.get('summary', {}).get('errors') for p in sync_results):
            ctx = jobs.current()
            if ctx:
                ctx.store.update(ctx.id, result={'affected': affected, 'synced_playlists': len(affected_playlists),
                    'playlists': [{**p, 'ok': not p.get('summary', {}).get('errors')} for p in sync_results]})
            raise HTTPException(502, 'Manual match was saved, but a playlist update failed. Review the output and sync that playlist again.')
        return {
            "affected": affected,
            "synced_playlists": len(affected_playlists),
            "playlists": sync_results,
            "log": "\n".join(combined_log).strip(),
        }


@app.get("/api/settings/notifications")
def get_notification_settings():
    config = _config(read_only=True, namespaces=[])
    return WebhookSettings.from_dict(
        config.config.get("notifications")
    ).to_dict()


@app.put("/api/settings/notifications")
def put_notification_settings(request: NotificationSettingsRequest):
    with ProcessLock():
        config = _config()
        settings = WebhookSettings.from_dict(request.model_dump())
        config.config["notifications"] = settings.to_dict()
        config.save()
        return settings.to_dict()


@app.post("/api/settings/notifications/test")
def test_notification():
    config = _config(read_only=True, namespaces=[])
    settings = WebhookSettings.from_dict(config.config.get("notifications"))
    if not settings.enabled or not settings.url:
        raise HTTPException(status_code=400, detail="Webhook notifications are not enabled/configured")
    try:
        sent = WebhookNotifier(settings).send(
            "test",
            "Playlist Bridge webhook test",
            {"version": __version__},
        )
        return {"sent": sent}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/settings/logs")
def get_logs(limit: int = Query(default=100, ge=1, le=500),
             level: Optional[Literal["INFO", "ERROR"]] = None, action: Optional[str] = None):
    config = _config(read_only=True, namespaces=[])
    rows = config.repository.logs(limit, level, action)
    for row in rows:
        row['message'] = redact(row['message'], config)
    return {"entries": rows, "retention": 1000}


class RemoveRequest(BaseModel):
    playlist_keys: List[str] = Field(min_length=1)
    delete_plex: bool = False


class JobRequest(BaseModel):
    action: Literal['sync','health','analyze','add','fix_match','track_match','remove','backup','check_updates']
    payload: dict = Field(default_factory=dict)


class ScheduleRequest(BaseModel):
    action: Literal['sync','health','backup','check_updates']
    scope: Literal['all','favorites','automatic'] = 'all'
    hours: Literal[0,1,3,6,12,24]


def job_store():
    from .storage import get_repository
    from .legacy import CONFIG_DIR
    return jobs.Store(get_repository(CONFIG_DIR))


def validated_payload(action, payload):
    if action in ('backup','check_updates'):return {}
    if action == 'remove':
        return RemoveRequest(**payload).model_dump()
    if action == 'track_match':
        from .track_routes import ApplyRequest
        return ApplyRequest(**payload).model_dump()
    if action in ('add','analyze','fix_match'):
        model = {'add':PlaylistAddRequest,'analyze':PlaylistAnalyzeRequest,'fix_match':MissingMatchRequest}[action]
        data=model(**payload).model_dump()
        if action=='add':
            source,url,_source_api=_source_for_url(data['url'])
            if not Config._extract_id(url,source):raise ValueError('Enter a valid Spotify or Apple Music playlist URL')
            if _config(read_only=True,namespaces=[]).find_playlist(url):raise HTTPException(409,'Playlist is already registered')
        return data
    scope = payload.get('scope', 'all')
    if scope not in jobs.SCOPES:
        raise ValueError('Choose all, favorites, automatic or selected playlists')
    keys = payload.get('playlist_keys', [])
    if not isinstance(keys, list) or not all(isinstance(k,str) for k in keys):
        raise ValueError('playlist_keys must be a list of playlist ids')
    if scope=='selected' and not keys:
        raise ValueError('Select at least one playlist')
    return {'scope':scope, **({'playlist_keys':keys} if scope=='selected' else {})}


@app.post('/api/jobs', status_code=202)
def queue_job(request: JobRequest):
    try:
        payload = validated_payload(request.action, request.payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    store = job_store()
    return store.get(store.enqueue(request.action,payload))


@app.get('/api/jobs')
def list_jobs():
    return job_store().list()


@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    row = job_store().get(job_id)
    if not row:
        raise HTTPException(404,'Job not found')
    return row


@app.get('/api/jobs/{job_id}/events')
def job_events(job_id: str, after: int = Query(default=0, ge=0)):
    if not job_store().get(job_id):
        raise HTTPException(404, 'Job not found')
    return job_store().events(job_id, after)


@app.get('/api/jobs/{job_id}/live')
def live_job(job_id: str, after: int = Query(default=0, ge=0)):
    store = job_store()
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, 'Job not found')
    return {'job': job, 'events': store.events(job_id, after)}


@app.get('/api/jobs/{job_id}/log')
def download_job_log(job_id: str):
    from starlette.responses import StreamingResponse
    store = job_store()
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, 'Job not found')
    def lines():
        yield f"{job['action']} · {job['status']}\nStarted: {job['started_at']}\n"
        after = 0
        while True:
            rows = store.events(job_id, after)
            if not rows:
                break
            for row in rows:
                yield f"{row['created_at']}  {row['message']}\n"
            after = rows[-1]['id']
        if job.get('error'):
            yield f"Error: {job['error']}\n"
    return StreamingResponse(lines(), media_type='text/plain', headers={
        'Content-Disposition': f'attachment; filename="playlist-bridge-{job["id"]}.log"'})


@app.post('/api/jobs/{job_id}/cancel')
def cancel_job(job_id: str):
    row = job_store().cancel(job_id)
    if not row:
        raise HTTPException(404,'Job not found')
    return row


@app.get('/api/schedules')
def list_schedules():
    return job_store().schedules()


@app.post('/api/schedules')
def create_schedule(request: ScheduleRequest):
    try:
        return job_store().save_schedule(request.model_dump())
    except (ValueError, KeyError) as exc:
        raise HTTPException(422,str(exc)) from exc


@app.put('/api/schedules/{schedule_id}')
def update_schedule(schedule_id: str, request: ScheduleRequest):
    if not any(s['id']==schedule_id for s in job_store().schedules()):
        raise HTTPException(404,'Schedule not found')
    try:
        return job_store().save_schedule(request.model_dump(),schedule_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422,str(exc)) from exc


@app.delete('/api/schedules/{schedule_id}')
def delete_schedule(schedule_id: str):
    store=job_store()
    task=next((t for t in store.schedules() if t['id']==schedule_id),None)
    if not task:raise HTTPException(404,'Task not found')
    if task['action']=='check_updates':raise HTTPException(422,'The update check is a built-in task')
    store.save_schedule({**task,'hours':0},schedule_id)
    return {'disabled':True}



@app.post('/api/schedules/{schedule_id}/run', status_code=202)
def run_schedule(schedule_id: str):
    store=job_store()
    schedule=next((s for s in store.schedules() if s['id']==schedule_id),None)
    if not schedule:
        raise HTTPException(404,'Schedule not found')
    from .tasks import payload
    return store.get(store.enqueue(schedule['action'],payload(schedule)))


def _health_batch(playlists, config):
    """Three read-only checks at a time; persist each completion and drain on cancel."""
    ctx = jobs.current()
    results = []
    cancelled = False
    remaining = iter(playlists)

    def perform(playlist):
        jobs._local.context = ctx
        jobs.target(_playlist_key(playlist), playlist.get('plex_playlist_name',''), playlists.index(playlist)+1, len(playlists))
        try:
            if ctx:
                ctx.checkpoint()
            result = playlist_health(_playlist_key(playlist))
            jobs.activity(mode='completed', stage='Health check complete')
            return {"key": _playlist_key(playlist), "name": playlist.get("plex_playlist_name"), "ok": True, "result": result}
        except Exception as exc:
            jobs.activity(mode='failed', stage=redact(getattr(exc, 'detail', str(exc)), config))
            return {"key": _playlist_key(playlist), "name": playlist.get("plex_playlist_name"), "ok": False,
                    "error": redact(getattr(exc, "detail", str(exc)), config)}
        finally:
            jobs._local.context = None
            jobs._local.target = None

    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="playlist-health") as pool:
        pending = set()
        while True:
            try:
                if ctx:
                    ctx.checkpoint()
            except jobs.Cancelled:
                cancelled = True
            while not cancelled and len(pending) < 3:
                playlist = next(remaining, None)
                if playlist is None:
                    break
                pending.add(pool.submit(perform, playlist))
            if not pending:
                break
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    results.append(future.result())
                except jobs.Cancelled:
                    cancelled = True
            if ctx:
                ctx.store.update(ctx.id, result={"playlists": results, "total": len(playlists)},
                                 progress=f"Health: {len(results)} of {len(playlists)} finished")
    if cancelled:
        raise jobs.Cancelled()
    if any(not r['ok'] for r in results):
        raise ValueError(f"{sum(not r['ok'] for r in results)} of {len(results)} playlists failed. See job results and logs.")
    return {"playlists": results, "total": len(playlists)}


def execute_job(action, payload):
    if action=='check_updates':
        from .updates import check
        jobs.progress('Checking the published release image')
        result=check(True)
        if result.get('error'):raise ValueError(result['error'])
        return result
    if action in ('backup','restore_backup'):
        from . import backups
        with ProcessLock():
            repo=job_store().repository
            if action=='restore_backup':return backups.restore(repo,payload['name'])
            ctx=jobs.current()
            kind='daily' if ctx and ctx.store.get(ctx.id).get('schedule_id') else 'manual'
            return backups.create(repo,kind)

    if action == 'remove':
        return remove_selected(RemoveRequest(**payload))
    if action == 'track_match':
        from .track_routes import apply_preview
        return apply_preview(payload['preview_id'])
    if action in ('analyze', 'add', 'fix_match'):
        jobs.target('job', payload.get('url') or payload.get('title') or 'Playlist')
    if action=='analyze':
        return analyze_playlist(PlaylistAnalyzeRequest(**payload))
    if action=='add':
        return add_playlist(PlaylistAddRequest(**payload))
    if action=='fix_match':
        return save_missing_match(MissingMatchRequest(**payload))
    config=_config(read_only=True, namespaces=[])
    scope=payload.get('scope','all')
    playlists=config.config.get('playlists',[])
    if scope=='favorites':
        playlists=[p for p in playlists if p.get('favorite') is True]
    elif scope=='automatic':
        playlists=[p for p in playlists if p.get('auto_sync',True) is not False]
    elif scope=='selected':
        playlists=[p for p in playlists if _playlist_key(p) in payload.get('playlist_keys',[])]
    if not playlists:
        raise ValueError('No playlists match this job scope')
    ctx = jobs.current()
    if ctx:
        ctx.store.update(ctx.id, result={'playlists': [], 'total': len(playlists)})
    if action == 'health':
        return _health_batch(playlists, config)
    results=[]
    for index,playlist in enumerate(playlists):
        jobs.target(_playlist_key(playlist), playlist.get('plex_playlist_name',''), index+1, len(playlists))
        jobs.progress(f"{index+1} of {len(playlists)}: {playlist.get('plex_playlist_name','')}")
        try:
            result=sync_one(_playlist_key(playlist)) if action=='sync' else playlist_health(_playlist_key(playlist))
            if action=='sync' and isinstance(result.get('summary'),dict) and result['summary'].get('errors'):
                raise ValueError('Playlist sync reported errors; see the sync log')
            results.append({'key':_playlist_key(playlist),'name':playlist.get('plex_playlist_name'),'ok':True,'result':result})
            jobs.activity(mode='completed', stage='Playlist completed')
            jobs.output('✓ Playlist completed: ' + playlist.get('plex_playlist_name',''))
        except Exception as exc:
            message = redact(getattr(exc,'detail',str(exc)),config)
            results.append({'key':_playlist_key(playlist),'name':playlist.get('plex_playlist_name'),'ok':False,'error':message})
            jobs.activity(mode='failed', stage=message)
            jobs.output('✗ ' + playlist.get('plex_playlist_name','') + ': ' + message)
        ctx=jobs.current()
        if ctx:
            ctx.store.update(ctx.id,result={'playlists':results, 'total':len(playlists)})
    if any(not r['ok'] for r in results):
        raise ValueError(f"{sum(not r['ok'] for r in results)} of {len(results)} playlists failed. See job results and logs.")
    return {'playlists':results, 'total':len(playlists)}


# Compatibility URLs now return 202 + a durable job; poll /api/jobs/{id}.
@app.post('/api/playlists/analyze',status_code=202)
def queue_analysis(request: PlaylistAnalyzeRequest):
    return queue_job(JobRequest(action='analyze',payload=request.model_dump()))


@app.post('/api/playlists',status_code=202)
def queue_add(request: PlaylistAddRequest):
    return queue_job(JobRequest(action='add',payload=request.model_dump()))


@app.post('/api/sync/all',status_code=202)
def queue_all():
    return queue_job(JobRequest(action='sync'))


@app.post('/api/sync/favorites',status_code=202)
def queue_favorites():
    return queue_job(JobRequest(action='sync',payload={'scope':'favorites'}))


@app.post('/api/sync/automatic',status_code=202)
def queue_automatic():
    return queue_job(JobRequest(action='sync',payload={'scope':'automatic'}))


@app.post('/api/sync/{playlist_key:path}',status_code=202)
def queue_one(playlist_key: str):
    return queue_job(JobRequest(action='sync',payload={'scope':'selected','playlist_keys':[playlist_key]}))


@app.get('/api/playlists/{playlist_key:path}/health',status_code=202)
def queue_health(playlist_key: str):
    return queue_job(JobRequest(action='health',payload={'scope':'selected','playlist_keys':[playlist_key]}))


@app.post('/api/missing/match',status_code=202)
def queue_match(request: MissingMatchRequest):
    return queue_job(JobRequest(action='fix_match',payload=request.model_dump()))


class IgnoreRequest(BaseModel):
    title: str
    artist: str
    album: str = ''
    universal: bool = False
    playlist_keys: List[str] = Field(default_factory=list)


@app.post('/api/missing/ignore')
def ignore_missing(request: IgnoreRequest):
    if not request.universal and not request.playlist_keys:
        raise HTTPException(422,'Select playlists or choose universal ignore')
    with ProcessLock():
        config=_config()
        syncer=Syncer(config)
        track=request.model_dump(include={'title','artist','album'})
        affected=0
        if request.universal:
            syncer._ignore_track('__global__',track)
        for playlist in config.config.get('playlists',[]):
            key=_playlist_key(playlist)
            if not request.universal and key not in request.playlist_keys:
                continue
            remaining=[]
            for t in config.missing.get(key,[]):
                if syncer._same_missing_identity(t,track):
                    if not request.universal:
                        syncer._ignore_track(key,t)
                    else:
                        search_key=f"{t.get('title','')}|{t.get('artist','')}"
                        config.mapping.get(key,{}).pop(search_key,None)
                        syncer._remove_match_provenance(key,search_key)
                    affected+=1
                else:
                    remaining.append(t)
            config.missing[key]=remaining
        config.save()
        _record_log('INFO','ignore',f"Ignored {request.title} in {affected} unresolved occurrences",config)
        return {'affected':affected,'universal':request.universal}


@app.get('/api/ignored')
def list_ignored():
    config=_config(read_only=True, namespaces=[])
    return [{'playlist_key':key,'ignore_key':identity,**track} for key,bucket in config.ignored_tracks.items() for identity,track in bucket.items()]


class RestoreIgnoreRequest(BaseModel):
    playlist_key: str
    ignore_key: str


@app.post('/api/ignored/restore')
def restore_ignore(request: RestoreIgnoreRequest):
    with ProcessLock():
        config=_config()
        config.ignored_tracks.get(request.playlist_key,{}).pop(request.ignore_key,None)
        config.save()
    return {'restored':True}


@app.delete('/api/settings/logs')
def clear_logs():
    job_store().repository.clear_logs()
    return {'cleared':True}


@app.get('/api/search')
def search_library(q: str = Query(min_length=1,max_length=200)):
    config=_config(read_only=True, namespaces=[])
    query=q.casefold().strip()
    playlists=[]; tracks=[]
    health=config.repository.load('health')
    for p in config.config.get('playlists',[]):
        key=_playlist_key(p); name=p.get('plex_playlist_name',key)
        if query in name.casefold():
            playlists.append({'key':key,'name':name})
        snapshot=config.source_snapshots.get(key,[])
        source=health.get(key,{}).get('source_preview') or (snapshot if isinstance(snapshot,list) else [])
        candidates=[*source,*config.missing.get(key,[])]
        for search_key in config.mapping.get(key,{}):
            title,_,artist=search_key.partition('|')
            candidates.append({'title':title,'artist':artist})
        seen=set()
        for track in candidates:
            identity=(track.get('title',''),track.get('artist',''))
            if identity in seen: continue
            seen.add(identity)
            if query in ' '.join(str(track.get(k,'')) for k in ('title','artist','album')).casefold():
                tracks.append({**track,'playlist_key':key,'playlist_name':name})
    return {'playlists':playlists[:100],'tracks':tracks[:200],'track_count':len(tracks),'cached':True}


def remove_selected(request):
    results=[]
    with ProcessLock():
        config=_config()
        selected=set(request.playlist_keys)
        targets=[p for p in config.config['playlists'] if _playlist_key(p) in selected]
        if selected != set(_playlist_key(p) for p in targets):
            raise HTTPException(409,'One or more playlists are no longer registered. Refresh the list.')
        plex=_health_plex(config) if request.delete_plex else None
        for index,playlist in enumerate(targets,1):
            key=_playlist_key(playlist)
            jobs.target(key,playlist.get('plex_playlist_name',key),index,len(targets))
            jobs.progress('Deleting Plex playlist and registration' if plex else 'Removing registration; leaving Plex untouched')
            try:
                if plex:
                    plex_id=str(playlist.get('plex_playlist_id',''))
                    if not plex_id:raise ValueError('This registration has no Plex playlist ID')
                    if any(str(p.get('plex_playlist_id',''))==plex_id and _playlist_key(p) not in selected for p in config.config['playlists']):
                        raise ValueError('Another unselected registration uses this Plex playlist. Remove from Bridge only or select every registration.')
                    response=requests.delete(f'{plex.base_url}/playlists/{plex_id}',headers=plex.headers,timeout=15)
                    if response.status_code not in (200,204,404):
                        raise ValueError(f'Plex deletion failed (HTTP {response.status_code}); registration retained.')
                remaining=[p for p in config.config['playlists'] if _playlist_key(p)!=key]
                with config.repository.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    db.execute("UPDATE state SET value=? WHERE namespace='runtime' AND key='playlists'",(json.dumps(remaining),))
                    for namespace in ('mapping','missing','match_metadata','source_snapshots','ignored_tracks','health','health_attempts'):
                        db.execute('DELETE FROM state WHERE namespace=? AND key=?',(namespace,key))
                config.config['playlists']=remaining
                results.append({'key':key,'name':playlist.get('plex_playlist_name'),'ok':True,'removed':True,'plex_deleted':bool(plex)})
                jobs.output('✓ Removed playlist' + (' from Bridge and Plex' if plex else ' from Bridge; Plex untouched'))
            except Exception as exc:
                results.append({'key':key,'name':playlist.get('plex_playlist_name'),'ok':False,'error':redact(str(exc),config)})
            if jobs.current():jobs.current().store.update(jobs.current().id,result={'playlists':results,'total':len(targets)})
        if any(not row['ok'] for row in results):raise ValueError('Some removals failed. Review the per-playlist results; failed registrations were retained where possible.')
    return {'playlists':results,'total':len(targets)}


@app.delete('/api/playlists/{playlist_key:path}')
def remove_playlist(playlist_key: str):
    with ProcessLock():
        config = _config()
        playlists = config.config.get('playlists', [])
        if not any(_playlist_key(p) == playlist_key for p in playlists):
            raise HTTPException(404, 'Playlist not found')
        # One transaction removes only this registration and its scoped state.
        with config.repository.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE state SET value=? WHERE namespace='runtime' AND key='playlists'",
                (json.dumps([p for p in playlists if _playlist_key(p) != playlist_key]),))
            for namespace in ('mapping','missing','match_metadata','source_snapshots','ignored_tracks','health','health_attempts'):
                db.execute('DELETE FROM state WHERE namespace=? AND key=?', (namespace,playlist_key))
        return {'deleted': True, 'plex_playlist_untouched': True}


@app.post('/api/missing/automatic')
def retry_automatic(request: MissingCandidateRequest):
    config = _config(read_only=True)
    plex = _health_plex(config)
    library = plex.search_library('')
    source = request.model_dump(include={'title','artist','album'})
    # Deliberately omit saved mappings so the unchanged matcher gets a fresh try.
    candidate_id = Matcher.match_track(source, library, {})
    candidate = next((t for t in library if str(t.get('plex_id')) == str(candidate_id)), None) if candidate_id is not None else None
    if candidate:
        score = Matcher.score_candidate(source, candidate)
        candidate = {**candidate, 'plex_id': str(candidate_id), 'score': round(score['adjusted_score'],1)}
    return {'candidate': candidate}


from .track_routes import register as register_tracks
register_tracks(app)
from .settings_routes import register as register_settings
register_settings(app)
from .updates import register as register_updates
register_updates(app)

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")


def run():
    import uvicorn

    port = int(os.environ.get("PLAYLIST_BRIDGE_PORT") or "8173")
    if not 1 <= port <= 65535:
        raise ValueError("PLAYLIST_BRIDGE_PORT must be between 1 and 65535")

    uvicorn.run(
        "playlist_bridge.api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    run()
