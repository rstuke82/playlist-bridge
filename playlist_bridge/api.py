"""FastAPI backend for Playlist Bridge 2.0."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
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
from .notifications import WebhookNotifier, WebhookSettings


app = FastAPI(
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
    auto_sync: bool = True
    favorite: bool = False


class PlaylistUpdateRequest(BaseModel):
    favorite: Optional[bool] = None
    auto_sync: Optional[bool] = None


class MissingCandidateRequest(BaseModel):
    title: str
    artist: str
    album: str = ""
    limit: int = Field(default=10, ge=1, le=50)


class MissingMatchRequest(BaseModel):
    title: str
    artist: str
    album: str = ""
    plex_id: str
    playlist_keys: Optional[List[str]] = None


class NotificationSettingsRequest(BaseModel):
    enabled: bool = False
    url: str = ""
    notify_sync_failures: bool = True
    notify_lost_matches: bool = True
    notify_unresolved: bool = True
    notify_source_changes: bool = True
    notify_successful_syncs: bool = False
    notify_sync_all_summary: bool = True


def _config() -> Config:
    return Config()


def _playlist_key(playlist: dict) -> str:
    return f"{playlist.get('source', '')}:{playlist.get('source_id', '')}"


def _playlist_payload(config: Config, playlist: dict) -> dict:
    key = _playlist_key(playlist)
    missing = config.missing.get(key, [])
    return {
        "key": key,
        "name": playlist.get("plex_playlist_name", ""),
        "source": playlist.get("source", ""),
        "source_url": playlist.get("source_url", ""),
        "source_id": playlist.get("source_id", ""),
        "plex_playlist_id": playlist.get("plex_playlist_id", ""),
        "favorite": playlist.get("favorite", False) is True,
        "auto_sync": playlist.get("auto_sync", True) is not False,
        "last_synced": playlist.get("last_synced"),
        "last_match_attempt": playlist.get("last_match_attempt"),
        "saved_matches": len(config.mapping.get(key, {})),
        "unresolved": len(missing),
        "lost": sum(1 for track in missing if track.get("status") == "lost"),
        "ignored": len(config.ignored_tracks.get(key, {})),
    }


def _source_for_url(url: str):
    normalized = Config._normalize_url_input(url)
    lower = normalized.lower()
    if "spotify.com" in lower or lower.startswith("spotify:playlist:"):
        return "spotify", normalized, SpotifyAPI()
    if "music.apple.com" in lower or "itunes.apple.com" in lower:
        return "applemusic", normalized, AppleMusicAPI()
    raise HTTPException(status_code=400, detail="URL must be a Spotify or Apple Music playlist")


def _capture(callable_obj, *args, **kwargs):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = callable_obj(*args, **kwargs)
    return result, stream.getvalue()


@app.get("/api/health")
def health():
    config = _config()
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
    config = _config()
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


@app.post("/api/playlists/analyze")
def analyze_playlist(request: PlaylistAnalyzeRequest):
    config = _config()
    source_type, url, source_api = _source_for_url(request.url)
    playlist_id = Config._extract_id(url, source_type)
    if not playlist_id:
        raise HTTPException(status_code=400, detail="Could not extract playlist ID")

    if config.find_playlist(url):
        raise HTTPException(status_code=409, detail="Playlist is already registered")

    try:
        (tracks, metadata), source_log = _capture(
            source_api.get_playlist_tracks,
            url,
            fetch_artwork=False,
        )
        syncer = Syncer(config)
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

    return {
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


@app.post("/api/playlists")
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
            tracks, metadata = source_api.get_playlist_tracks(url, fetch_artwork=True)
            syncer = Syncer(config)
            mapping_key = f"{source_type}:{playlist_id}"
            matched, unmatched, mapping, _library, _stats = syncer._match_source_tracks(
                tracks,
                mapping_key,
                mark_new_matches=False,
            )
            syncer._store_unmatched(mapping_key, unmatched)
            config.mapping[mapping_key] = mapping
            config.save()

            if not matched:
                raise HTTPException(
                    status_code=422,
                    detail="No source tracks matched Plex, so the playlist was not created",
                )

            plex_playlist_id = syncer._build_new_plex_playlist(
                metadata.get("name", "Unknown Playlist"),
                metadata.get("description", ""),
                matched,
                metadata.get("image_url", ""),
            )
            if not plex_playlist_id:
                raise HTTPException(status_code=502, detail="Plex playlist creation failed")

            playlist = config.add_playlist(
                url,
                source_type,
                metadata.get("name", "Unknown Playlist"),
                plex_playlist_id,
            )
            playlist["auto_sync"] = request.auto_sync
            playlist["favorite"] = request.favorite
            from datetime import datetime
            playlist["last_synced"] = datetime.now().isoformat()
            syncer._save_source_snapshot(mapping_key, tracks)
            config.save()
            return _playlist_payload(config, playlist)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/sync/all")
def sync_all():
    with ProcessLock():
        config = _config()
        result, log = _capture(Syncer(config).sync_all)
        return {"summary": result, "log": log}


@app.post("/api/sync/favorites")
def sync_favorites():
    with ProcessLock():
        config = _config()
        result, log = _capture(Syncer(config).sync_favorites)
        return {"summary": result, "log": log}


@app.post("/api/sync/{playlist_key:path}")
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
        return {"summary": result, "log": log}


@app.get("/api/missing")
def missing_tracks(scope: Literal["all", "favorites"] = "all"):
    config = _config()
    playlists = config.config.get("playlists", [])
    if scope == "favorites":
        playlists = [p for p in playlists if p.get("favorite") is True]
    return Syncer(config).collect_all_missing_tracks_deduped(playlists=playlists)


@app.post("/api/missing/candidates")
def missing_candidates(request: MissingCandidateRequest):
    config = _config()
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


@app.post("/api/missing/match")
def save_missing_match(request: MissingMatchRequest):
    with ProcessLock():
        config = _config()
        syncer = Syncer(config)
        playlists = config.config.get("playlists", [])
        if request.playlist_keys:
            wanted = set(request.playlist_keys)
            playlists = [p for p in playlists if _playlist_key(p) in wanted]

        plex = syncer._get_plex()
        selected = next(
            (track for track in plex.search_library("") if str(track.get("plex_id")) == request.plex_id),
            None,
        )
        if selected is None:
            raise HTTPException(status_code=404, detail="Plex track not found")

        affected = syncer._apply_global_missing_match(
            {
                "title": request.title,
                "artist": request.artist,
                "album": request.album,
            },
            selected,
            playlists,
        )
        return {"affected": affected}


@app.get("/api/settings/notifications")
def get_notification_settings():
    config = _config()
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
    config = _config()
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


WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")


def run():
    import uvicorn

    uvicorn.run(
        "playlist_bridge.api:app",
        host="0.0.0.0",
        port=8787,
        reload=False,
    )


if __name__ == "__main__":
    run()
