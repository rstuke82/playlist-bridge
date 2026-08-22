#!/usr/bin/env python3
"""
Playlist Bridge - Sync Spotify/Apple Music playlists to Plex
Public playlist URLs, fuzzy matching, interactive menu

Plex playlist handling uses the Plex server/library URI format and
creates playlists only after at least one source track has been
successfully matched to a Plex library track.
"""

import argparse
import json
import re
import shutil
import sys
from collections import Counter
import copy
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse, unquote
from html import unescape

import requests
from bs4 import BeautifulSoup # type: ignore
from fuzzywuzzy import fuzz # type: ignore
from fuzzywuzzy import process # type: ignore

APP_NAME = "Playlist Bridge"
VERSION = "1.21-dev"

# Color codes for terminal output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    MAGENTA = '\033[95m'
    BLUE = '\033[94m'
    WHITE = '\033[97m'

def colored(text: str, color: str) -> str:
    """Add color to text for terminal output."""
    return f"{color}{text}{Colors.RESET}"


def repair_text(value) -> str:
    """
    Repair common UTF-8 text that was accidentally decoded as Latin-1.

    Example:
        We Didnât -> We Didn’t

    Already-correct Unicode is left unchanged.
    """
    if value is None:
        return ""

    text = str(value)

    suspicious_markers = ("Ã", "Â", "â", "ð", "�")

    def suspicious_count(candidate: str) -> int:
        return (
            sum(candidate.count(marker) for marker in suspicious_markers)
            + sum(1 for ch in candidate if 0x80 <= ord(ch) <= 0x9F)
        )

    # Two passes also repairs common double-encoded strings.
    for _ in range(2):
        before = suspicious_count(text)

        if before == 0:
            break

        best = text
        best_count = before

        for encoding in ("latin-1", "cp1252"):
            try:
                candidate = text.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

            candidate_count = suspicious_count(candidate)

            if candidate_count < best_count:
                best = candidate
                best_count = candidate_count

        if best == text:
            break

        text = best

    return text


def clean_playlist_description(value) -> str:
    """
    Return a meaningful playlist description, or an empty string.

    Spotify/Apple Music public metadata sometimes exposes a generated label
    such as:
        Playlist · 86 Songs
    rather than a user-authored description. Plex already knows the object is
    a playlist and shows its item count, so those generated descriptions add
    no useful information and are suppressed.

    Genuine source descriptions are preserved.
    """
    text = repair_text(value).strip()

    if not text:
        return ""

    # Common generated descriptions from public playlist metadata.
    # Allow an optional trailing duration/metadata segment, e.g.
    # "Playlist · 86 Songs · 5 hr 12 min".
    generic_patterns = (
        r"^playlist\s*[·•]\s*\d+\s+songs?"
        r"(?:\s*[·•]\s*.*)?$",
        r"^\d+\s+songs?$",
    )

    if any(
        re.fullmatch(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        for pattern in generic_patterns
    ):
        return ""

    return text


def source_display_name(source_type: str) -> str:
    """Return one consistent user-facing service name."""
    names = {
        "spotify": "Spotify",
        "applemusic": "Apple Music",
    }
    value = str(source_type or "").lower()
    return names.get(value, str(source_type or "").title())



def source_album_display(track: dict) -> str:
    """Return source album using the same format as Plex album output."""
    album = repair_text(track.get("album", "") or "").strip()

    if album:
        return colored(f"({album})", Colors.YELLOW)

    return "(N/A)"


def parse_timestamp(value):
    """Parse an ISO timestamp, returning None for empty/invalid values."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def format_timestamp(value) -> str:
    """Format a stored timestamp for terminal display."""
    parsed = parse_timestamp(value)

    if parsed is None:
        return "Never"

    return parsed.strftime("%Y-%m-%d %H:%M")


def oldest_timestamp_sort_key(item: dict, field: str):
    """Sort Never/invalid first, followed by oldest valid timestamp."""
    parsed = parse_timestamp(item.get(field))

    if parsed is None:
        return (0, datetime.min)

    return (1, parsed)


def parse_index_selection(
    value: str,
    max_index: int,
) -> List[int]:
    """
    Parse comma-separated menu selections and simple ranges.

    Examples:
        1,3,5
        1-3,7
    """
    selected = []

    for part in str(value).split(","):
        token = part.strip()

        if not token:
            continue

        values = []

        if "-" in token:
            pieces = token.split("-", 1)

            try:
                start = int(pieces[0])
                end = int(pieces[1])
            except ValueError:
                raise ValueError("Invalid selection")

            if start > end:
                start, end = end, start

            values = list(
                range(start, end + 1)
            )
        else:
            try:
                values = [int(token)]
            except ValueError:
                raise ValueError("Invalid selection")

        for number in values:
            if not 1 <= number <= max_index:
                raise ValueError("Selection out of range")

            index = number - 1
            if index not in selected:
                selected.append(index)

    if not selected:
        raise ValueError("No selection")

    return selected


# Config file locations - stored in project root
CONFIG_DIR = Path.cwd()
CONFIG_FILE = CONFIG_DIR / "config.json"
MAPPING_FILE = CONFIG_DIR / "mapping.json"
MISSING_FILE = CONFIG_DIR / "missing_tracks.json"
MATCH_METADATA_FILE = CONFIG_DIR / "match_metadata.json"
SOURCE_SNAPSHOTS_FILE = CONFIG_DIR / "source_snapshots.json"

# Persistent JSON schema version.
#
# This is intentionally independent from Playlist Bridge's app VERSION.
# Increment only when the on-disk JSON structure changes.
STATE_SCHEMA_VERSION = 1

# Requested square Apple Music playlist artwork size for Plex.
APPLE_ARTWORK_SIZE = 3000


class Config:
    """Handle configuration file management"""

    STATE_FILES = {
        "config": CONFIG_FILE,
        "mapping": MAPPING_FILE,
        "missing": MISSING_FILE,
        "match_metadata": MATCH_METADATA_FILE,
        "source_snapshots": SOURCE_SNAPSHOTS_FILE,
    }

    def __init__(self):
        CONFIG_DIR.mkdir(exist_ok=True)

        self._loaded_schema_versions = {}
        self._migration_needed = set()

        self.config = self._load_config()
        self.mapping = self._load_mapping()
        self.missing = self._load_missing()
        self.match_metadata = self._load_state_dict(
            "match_metadata",
            {},
        )
        self.source_snapshots = self._load_state_dict(
            "source_snapshots",
            {},
        )

    @staticmethod
    def _state_wrapper(data: dict) -> dict:
        """Wrap one state object using the current on-disk schema."""
        return {
            "_schema_version": STATE_SCHEMA_VERSION,
            "data": data,
        }

    @staticmethod
    def _schema_backup_path(path: Path) -> Path:
        """Return the one-time backup path used before schema migration."""
        return path.with_name(
            f"{path.name}.pre-schema-{STATE_SCHEMA_VERSION}.bak"
        )

    @staticmethod
    def _validate_state_data(
        name: str,
        data,
    ) -> dict:
        """Require every state payload to be a JSON object."""
        if not isinstance(data, dict):
            raise RuntimeError(
                f"{name}.json contains an unsupported root value. "
                "Expected a JSON object."
            )

        return data

    @staticmethod
    def _migrate_state_data(
        name: str,
        data: dict,
        from_version: int,
    ) -> dict:
        """
        Migrate a state payload to STATE_SCHEMA_VERSION.

        Schema 0 is the pre-versioned Playlist Bridge format. The 0 -> 1
        migration adds the version/data wrapper only; the payload itself does
        not need to change.
        """
        version = from_version
        migrated = data

        while version < STATE_SCHEMA_VERSION:
            if version == 0:
                version = 1
                continue

            raise RuntimeError(
                f"No migration path is implemented for {name}.json "
                f"from schema {version} to {STATE_SCHEMA_VERSION}."
            )

        return migrated

    def _load_state_dict(
        self,
        name: str,
        default: dict,
    ) -> dict:
        """
        Load legacy or schema-versioned state.

        Legacy files are treated as schema 0 and migrated only in memory.
        They are backed up and rewritten the next time Config.save() runs.
        This preserves dry-run's no-write guarantee.
        """
        path = self.STATE_FILES[name]

        if not path.exists():
            self._loaded_schema_versions[name] = (
                STATE_SCHEMA_VERSION
            )
            return copy.deepcopy(default)

        try:
            with open(path) as f:
                raw = json.load(f)
        except (OSError, ValueError) as e:
            raise RuntimeError(
                f"Could not read {path.name}: {e}"
            ) from e

        loaded_version = 0
        data = raw

        if (
            isinstance(raw, dict)
            and "_schema_version" in raw
        ):
            version_value = raw.get(
                "_schema_version"
            )

            if not isinstance(version_value, int):
                raise RuntimeError(
                    f"{path.name} has an invalid _schema_version. "
                    "Expected an integer."
                )

            loaded_version = version_value

            if loaded_version > STATE_SCHEMA_VERSION:
                raise RuntimeError(
                    f"{path.name} uses schema {loaded_version}, but this "
                    f"Playlist Bridge build only supports through schema "
                    f"{STATE_SCHEMA_VERSION}. Use a newer Playlist Bridge "
                    "version rather than risking state-file corruption."
                )

            if "data" not in raw:
                raise RuntimeError(
                    f"{path.name} is schema-versioned but has no 'data' "
                    "payload."
                )

            data = raw["data"]

        data = self._validate_state_data(
            name,
            data,
        )

        self._loaded_schema_versions[
            name
        ] = loaded_version

        if loaded_version < STATE_SCHEMA_VERSION:
            self._migration_needed.add(name)
            data = self._migrate_state_data(
                name,
                data,
                loaded_version,
            )

        return data

    def _load_config(self) -> dict:
        return self._load_state_dict(
            "config",
            {
                "plex": {},
                "playlists": [],
            },
        )

    def _load_mapping(self) -> dict:
        return self._load_state_dict(
            "mapping",
            {},
        )

    def _load_missing(self) -> dict:
        data = self._load_state_dict(
            "missing",
            {},
        )

        for tracks in data.values():
            if not isinstance(tracks, list):
                continue

            for track in tracks:
                if not isinstance(track, dict):
                    continue

                for field in (
                    "title",
                    "artist",
                    "album",
                ):
                    if field in track:
                        track[field] = repair_text(
                            track.get(field, "")
                        )

                previous_match = track.get(
                    "previous_match"
                )

                if isinstance(previous_match, dict):
                    for field in (
                        "title",
                        "artist",
                        "album",
                    ):
                        if field in previous_match:
                            previous_match[field] = repair_text(
                                previous_match.get(field, "")
                            )

        return data

    def _backup_before_schema_upgrade(
        self,
        name: str,
    ):
        """Create a one-time byte-for-byte backup before schema rewrite."""
        if name not in self._migration_needed:
            return

        path = self.STATE_FILES[name]

        if not path.exists():
            return

        backup_path = self._schema_backup_path(
            path
        )

        if backup_path.exists():
            return

        shutil.copy2(
            path,
            backup_path,
        )

    def save(self):
        """
        Save all state using the current schema.

        Older/legacy files are backed up once before the first rewrite.
        """
        state = {
            "config": self.config,
            "mapping": self.mapping,
            "missing": self.missing,
            "match_metadata": self.match_metadata,
            "source_snapshots": self.source_snapshots,
        }

        for name, data in state.items():
            self._backup_before_schema_upgrade(
                name
            )

            path = self.STATE_FILES[name]

            with open(path, "w") as f:
                json.dump(
                    self._state_wrapper(data),
                    f,
                    indent=2,
                )

            self._loaded_schema_versions[
                name
            ] = STATE_SCHEMA_VERSION
            self._migration_needed.discard(
                name
            )

    def setup_plex(self):
        """Interactive Plex authentication"""
        print("\n=== Plex Setup ===")
        plex_url = input(
            "Plex server URL (e.g., http://localhost:32400): "
        ).strip().rstrip("/")
        plex_token = input("Plex API token: ").strip()

        try:
            resp = requests.get(
                f"{plex_url}/identity",
                headers={"X-Plex-Token": plex_token},
                timeout=5,
            )

            if resp.status_code == 200:
                print("✓ Connected to Plex")
                self.config["plex"] = {
                    "url": plex_url,
                    "token": plex_token,
                }
                self.save()
                return True

            print(
                f"✗ Failed to connect. HTTP {resp.status_code}. "
                "Check URL and token."
            )
            return False

        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    def get_plex(self):
        """Get Plex config, prompt setup if missing"""
        if not self.config.get("plex", {}).get("token"):
            if not self.setup_plex():
                raise Exception("Plex setup required")

        return self.config["plex"]

    def add_playlist(
        self,
        source_url: str,
        source_type: str,
        plex_playlist_name: str,
        plex_playlist_id: str,
    ):
        """Add a new playlist to sync"""
        canonical_url = self._canonical_source_url(source_url, source_type)
        playlist_entry = {
            "source": source_type,
            "source_url": canonical_url,
            "source_id": self._extract_id(canonical_url, source_type),
            "plex_playlist_id": plex_playlist_id,
            "plex_playlist_name": plex_playlist_name,
            "last_synced": None,
            "last_match_attempt": None,
        }

        self.config["playlists"].append(playlist_entry)
        self.save()
        return playlist_entry

    @staticmethod
    def _normalize_url_input(value: str) -> str:
        """Normalize pasted playlist text into a usable URL/URI."""
        if not value:
            return ""

        value = unquote(str(value).strip())
        value = value.replace("\\&", "&").strip()

        # Accept Markdown links copied from chat/web pages:
        # [https://...](https://...)
        markdown = re.search(r"\[[^\]]*\]\((https?://[^)]+)\)", value)
        if markdown:
            value = markdown.group(1)

        # Accept text that contains a Spotify/Apple playlist URL plus
        # surrounding punctuation or commentary.
        url_match = re.search(
            r"https?://(?:open\.)?spotify\.com/playlist/[^\s<>)\]]+"
            r"|https?://(?:music|itunes)\.apple\.com/[^\s<>)\]]+",
            value,
            re.IGNORECASE,
        )
        if url_match:
            value = url_match.group(0)

        return value.strip().strip("<>[](){}.,;\"'")

    @staticmethod
    def _extract_id(url: str, source_type: str) -> Optional[str]:
        """Extract a canonical playlist ID while ignoring URL query data."""
        value = Config._normalize_url_input(url)
        if not value:
            return None

        if source_type == "spotify":
            # spotify:playlist:7eahWLng9go8LDR5gcW6A3
            uri_match = re.fullmatch(
                r"spotify:playlist:([A-Za-z0-9]{22})",
                value,
                re.IGNORECASE,
            )
            if uri_match:
                return uri_match.group(1)

            # Bare Spotify playlist ID.
            if re.fullmatch(r"[A-Za-z0-9]{22}", value):
                return value

            # Parse only the path component, so ?si=..., &nd=1,
            # &dlsi=..., etc. can never become part of the ID.
            try:
                parsed = urlparse(value)
                host = parsed.netloc.lower().split(":", 1)[0]
                if host in {"open.spotify.com", "spotify.com", "www.spotify.com"}:
                    parts = [p for p in parsed.path.split("/") if p]
                    for index, part in enumerate(parts[:-1]):
                        if part.lower() == "playlist":
                            candidate = parts[index + 1]
                            if re.fullmatch(r"[A-Za-z0-9]{22}", candidate):
                                return candidate
            except ValueError:
                pass

            # Last-resort extraction from pasted Spotify text.
            match = re.search(
                r"(?:open\.)?spotify\.com/playlist/([A-Za-z0-9]{22})",
                value,
                re.IGNORECASE,
            )
            return match.group(1) if match else None

        if source_type == "applemusic":
            # Apple Music IDs are not always purely alphanumeric after "pl.".
            # Replay playlists, for example, use IDs such as:
            #   pl.rp-B7CXevA0GM
            # Parse only the path so query parameters never become part of ID.
            try:
                parsed = urlparse(value)
                path = parsed.path
            except ValueError:
                path = value

            # Normal Apple Music playlist URL:
            # /us/playlist/replay-all-time/pl.rp-B7CXevA0GM
            match = re.search(
                r"/playlist/[^/]+/(pl\.[A-Za-z0-9._-]+)",
                path,
                re.IGNORECASE,
            )
            if match:
                return match.group(1)

            # Fallback for any path/text containing a playlist ID.
            match = re.search(
                r"(pl\.[A-Za-z0-9._-]+)",
                path,
                re.IGNORECASE,
            )
            if match:
                return match.group(1)

            # Also accept a bare Apple Music playlist ID.
            if re.fullmatch(r"pl\.[A-Za-z0-9._-]+", value, re.IGNORECASE):
                return value

            return None

        return None

    @staticmethod
    def _canonical_source_url(url: str, source_type: str) -> str:
        """Return a stable URL for storage and future syncs."""
        source_id = Config._extract_id(url, source_type)

        if source_type == "spotify" and source_id:
            return f"https://open.spotify.com/playlist/{source_id}"

        return Config._normalize_url_input(url)

    def find_playlist(self, source_url: str) -> Optional[dict]:
        """Find a playlist by canonical source identity, not query string."""
        normalized = self._normalize_url_input(source_url)

        if "spotify.com" in normalized.lower() or normalized.lower().startswith("spotify:playlist:"):
            source_type = "spotify"
        elif "music.apple.com" in normalized.lower() or "itunes.apple.com" in normalized.lower():
            source_type = "applemusic"
        else:
            source_type = None

        requested_id = (
            self._extract_id(normalized, source_type)
            if source_type
            else None
        )

        for playlist in self.config["playlists"]:
            if source_type and playlist.get("source") == source_type:
                existing_id = playlist.get("source_id") or self._extract_id(
                    playlist.get("source_url", ""),
                    source_type,
                )
                if requested_id and existing_id == requested_id:
                    return playlist

            if playlist.get("source_url") == normalized:
                return playlist

        return None

    def remove_playlist(self, index: int) -> bool:
        """Remove playlist by index"""
        if 0 <= index < len(self.config["playlists"]):
            self.config["playlists"].pop(index)
            self.save()
            return True
        return False



class SpotifyAPI:
    """Spotify API wrapper - scrapes public playlists without auth."""

    @staticmethod
    def _clean_artwork_url(value: str) -> str:
        """
        Decode and validate a Spotify artwork URL.

        Spotify also serves CSS/JS/fonts from spotifycdn.com, so simply
        checking the hostname is not enough.
        """
        if not isinstance(value, str):
            return ""

        value = unescape(value)
        value = value.replace("\\/", "/")
        value = value.replace("\\u0026", "&")
        value = value.strip()

        if not value.startswith("https://"):
            return ""

        try:
            parsed = urlparse(value)
        except ValueError:
            return ""

        host = (parsed.hostname or "").lower()
        path = parsed.path.lower()

        if not host:
            return ""

        blocked_suffixes = (
            ".css", ".js", ".mjs", ".map",
            ".woff", ".woff2", ".ttf", ".otf",
            ".json", ".html", ".svg",
        )

        if path.endswith(blocked_suffixes):
            return ""

        if "/_next/" in path or "/static/css/" in path or "/static/js/" in path:
            return ""

        # Current Spotify custom/playlist artwork CDN.
        if host.endswith(".spotifycdn.com") and (
            host.startswith("image-cdn-")
            or ".image-cdn-" in host
        ):
            return value

        # Standard Spotify artwork CDN.
        if host == "i.scdn.co" and "/image/" in path:
            return value

        # Spotify-generated mosaic playlist covers.
        if host == "mosaic.scdn.co":
            return value

        # Conservative fallback for explicit image files.
        if (
            host.endswith("spotifycdn.com")
            or host.endswith("scdn.co")
        ) and re.search(r"\.(?:jpe?g|png|webp|gif|avif)$", path):
            return value

        return ""


    @classmethod
    def _extract_artwork_url(cls, html_text: str, entity: dict = None) -> str:
        """Extract the main Spotify playlist cover URL."""
        entity = entity or {}
        candidates = []

        def add(value):
            cleaned = cls._clean_artwork_url(value)
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)

        # First prefer image fields from Spotify's playlist entity.
        def walk_images(obj, depth=0):
            if depth > 5:
                return
            if isinstance(obj, str):
                add(obj)
            elif isinstance(obj, list):
                for item in obj:
                    walk_images(item, depth + 1)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    key_lower = str(key).lower()
                    if any(token in key_lower for token in ("image", "cover", "art", "src", "url")):
                        walk_images(value, depth + 1)

        walk_images(entity)

        # OpenGraph is a strong signal for the playlist's main cover.
        og_patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        ]
        for pattern in og_patterns:
            for match in re.findall(pattern, html_text, re.IGNORECASE):
                add(match)

        # Spotify's playlist-header image is commonly eager-loaded.
        for tag in re.findall(r'<img\b[^>]*>', html_text, re.IGNORECASE):
            if re.search(r'loading=["\']eager["\']', tag, re.IGNORECASE):
                src_match = re.search(r'src=["\']([^"\']+)["\']', tag, re.IGNORECASE)
                if src_match:
                    add(src_match.group(1))

        # Generic Spotify CDN fallback. This handles hosts such as
        # image-cdn-fa.spotifycdn.com without hard-coding the region.
        direct_patterns = [
            r'https://(?:[A-Za-z0-9-]+\.)?image-cdn-[A-Za-z0-9-]+\.spotifycdn\.com/[^"\'\s<>]+',
            r'https://i\.scdn\.co/image/[A-Za-z0-9]+',
            r'https://mosaic\.scdn\.co/[^"\'\s<>]+',
        ]
        for pattern in direct_patterns:
            for match in re.findall(pattern, html_text, re.IGNORECASE):
                add(match)

        # Prefer playlist-cover/CDN style URLs over arbitrary nested images.
        for candidate in candidates:
            if "/image/" in candidate and (
                "image-cdn-" in candidate or "i.scdn.co" in candidate
            ):
                return candidate

        return candidates[0] if candidates else ""

    @classmethod
    def _fetch_oembed_artwork(cls, playlist_id: str) -> str:
        """
        Fetch playlist artwork from Spotify's public oEmbed endpoint.

        Spotify oEmbed returns thumbnail_url for public playlists and is
        considerably more reliable for cover art than scraping embed HTML.
        """
        normalized_id = Config._extract_id(playlist_id, "spotify")
        if not normalized_id:
            return ""

        public_url = (
            f"https://open.spotify.com/playlist/{normalized_id}"
        )

        try:
            resp = requests.get(
                "https://open.spotify.com/oembed",
                params={"url": public_url},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json",
                },
                timeout=10,
            )

            if resp.status_code != 200:
                return ""

            try:
                data = resp.json()
            except ValueError:
                return ""

            return cls._clean_artwork_url(
                data.get("thumbnail_url", "")
            )

        except requests.RequestException:
            return ""


    def get_playlist_tracks(
        self,
        playlist_id: str,
        fetch_artwork: bool = True,
    ) -> Tuple[List[dict], dict]:
        """
        Fetch a public Spotify playlist from a raw ID or full URL.

        Artwork discovery is optional so non-sync workflows such as
        missing-track triage and match editing do not perform artwork work.
        """

        normalized_id = Config._extract_id(playlist_id, "spotify")
        if not normalized_id:
            raise Exception(
                "Could not extract Spotify playlist ID from the supplied URL"
            )

        embed_url = f"https://open.spotify.com/embed/playlist/{normalized_id}"
        public_url = f"https://open.spotify.com/playlist/{normalized_id}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }

        try:
            resp = requests.get(embed_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                raise Exception(
                    f"Failed to fetch Spotify playlist: {resp.status_code}"
                )

            html_text = resp.text

            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">'
                r'({.*?})</script>',
                html_text,
                re.DOTALL,
            )
            if not match:
                raise Exception("Could not find playlist data in page")

            data = json.loads(match.group(1))
            entity = (
                data.get("props", {})
                .get("pageProps", {})
                .get("state", {})
                .get("data", {})
                .get("entity", {})
            )
            if not entity:
                raise Exception("Could not parse playlist entity data")

            name = repair_text(
                entity.get("name", "Unknown Playlist")
            )
            description = clean_playlist_description(
                entity.get("description", "")
            )

            image_url = ""

            if fetch_artwork:
                # Prefer Spotify's official oEmbed thumbnail. The embed/public
                # HTML structure changes frequently, while oEmbed exposes a
                # dedicated thumbnail_url for public playlist artwork.
                image_url = self._fetch_oembed_artwork(normalized_id)

                if image_url:
                    print(f"  ✓ Artwork via Spotify oEmbed: {image_url}")
                else:
                    # Fall back to the embed page if oEmbed did not return art.
                    image_url = self._extract_artwork_url(html_text, entity)

                    # The normal public page may expose og:image/header artwork
                    # even when the embed widget does not.
                    if not image_url:
                        try:
                            public_resp = requests.get(
                                public_url,
                                headers=headers,
                                timeout=10,
                            )
                            if public_resp.status_code == 200:
                                image_url = self._extract_artwork_url(
                                    public_resp.text
                                )
                        except requests.RequestException:
                            pass

                    if image_url:
                        print(
                            f"  ✓ Artwork extracted from Spotify page: "
                            f"{image_url}"
                        )
                    else:
                        print(
                            "  ⚠ No Spotify playlist artwork found "
                            "(oEmbed and page fallbacks failed)"
                        )

            tracks = entity.get("trackList", [])
            if not tracks:
                items = entity.get("tracks", {}).get("items", [])
                tracks = [item.get("track", item) for item in items]

            track_list = []
            for track in tracks:
                if not track:
                    continue

                title = (
                    track.get("title")
                    or track.get("name")
                    or "Unknown Title"
                )

                if "subtitle" in track:
                    artist_names = track.get("subtitle")
                else:
                    artists = track.get("artists", [])
                    artist_names = ", ".join(
                        a.get("name", "Unknown Artist") for a in artists
                    )

                if not artist_names:
                    artist_names = "Unknown Artist"

                # Spotify's embed payload is not consistent about album
                # metadata, but preserve it whenever it is available so the
                # matcher can prefer the original studio-album copy.
                album_name = (
                    track.get("albumName")
                    or track.get("album_name")
                    or ""
                )

                album_obj = track.get("album")
                if not album_name and isinstance(album_obj, dict):
                    album_name = (
                        album_obj.get("name")
                        or album_obj.get("title")
                        or ""
                    )
                elif not album_name and isinstance(album_obj, str):
                    album_name = album_obj

                track_uri = str(
                    track.get("uri", "") or ""
                )
                source_track_id = str(
                    track.get("id", "") or ""
                )

                if (
                    not source_track_id
                    and track_uri.startswith("spotify:track:")
                ):
                    source_track_id = track_uri.rsplit(":", 1)[-1]

                track_list.append(
                    {
                        "title": repair_text(title),
                        "artist": repair_text(artist_names),
                        "album": repair_text(album_name),
                        "source_id": source_track_id,
                        "uri": track_uri,
                    }
                )

            return track_list, {
                "name": name,
                "description": description,
                "image_url": image_url,
                "source_url": public_url,
            }

        except requests.exceptions.Timeout:
            raise Exception(
                "Request timed out. Spotify is tarpitting the connection."
            )
        except requests.exceptions.RequestException as e:
            raise Exception(f"Connection error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse playlist JSON: {e}")
        except Exception as e:
            raise Exception(f"Failed to extract playlist data: {e}")


class AppleMusicAPI:
    """
    Apple Music public-playlist scraper.

    Current music.apple.com playlist pages embed their server-rendered data
    in:
        <script id="serialized-server-data" type="application/json">...</script>

    This does not require an Apple Music developer token for public playlists.
    """

    @staticmethod
    def _normalize_artwork_url(value) -> str:
        """
        Normalize an Apple Music artwork URL.

        Only expand Apple's {w}/{h} artwork templates here. Do NOT blindly
        rewrite a fixed 1200x630 social-preview URL to 3000x3000; Apple's CDN
        preserves the source aspect ratio, so a URL containing "3000x3000bb"
        can still return a 3000x750 image.
        """
        if isinstance(value, list):
            for item in value:
                result = AppleMusicAPI._normalize_artwork_url(item)
                if result:
                    return result
            return ""

        if isinstance(value, dict):
            for key in ("url", "contentUrl", "src"):
                result = AppleMusicAPI._normalize_artwork_url(
                    value.get(key)
                )
                if result:
                    return result
            return ""

        if not isinstance(value, str):
            return ""

        value = unescape(value).replace("\\/", "/").strip()

        if not value.startswith("https://"):
            return ""

        # Expand true Apple artwork templates only.
        if "{w}" in value or "{h}" in value:
            replacements = {
                "{w}": str(APPLE_ARTWORK_SIZE),
                "{h}": str(APPLE_ARTWORK_SIZE),
                "{f}": "jpg",
                "{c}": "bb",
            }
            for old, new in replacements.items():
                value = value.replace(old, new)

        return value

    @staticmethod
    def _artwork_dimensions_from_value(value) -> Tuple[Optional[int], Optional[int]]:
        """Read declared width/height from an Apple artwork object or URL."""
        if isinstance(value, dict):
            width = (
                value.get("width")
                or value.get("maximumWidth")
                or value.get("maxWidth")
            )
            height = (
                value.get("height")
                or value.get("maximumHeight")
                or value.get("maxHeight")
            )

            try:
                width = int(width) if width is not None else None
            except (TypeError, ValueError):
                width = None

            try:
                height = int(height) if height is not None else None
            except (TypeError, ValueError):
                height = None

            if width and height:
                return width, height

            for key in ("url", "contentUrl", "src"):
                if value.get(key):
                    return AppleMusicAPI._artwork_dimensions_from_value(
                        value.get(key)
                    )

        if isinstance(value, str):
            # Useful for fixed derivatives such as 1200x630wp-60.jpg.
            match = re.search(
                r"/(\d+)x(\d+)[A-Za-z0-9._-]*\.(?:jpe?g|png|webp)$",
                value,
                re.IGNORECASE,
            )
            if match:
                return int(match.group(1)), int(match.group(2))

        return None, None


    @staticmethod
    def _walk_json(obj):
        """Yield every dict inside an arbitrarily nested JSON structure."""
        if isinstance(obj, dict):
            yield obj
            for value in obj.values():
                yield from AppleMusicAPI._walk_json(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from AppleMusicAPI._walk_json(value)

    @classmethod
    def _extract_metadata(cls, data, soup) -> dict:
        """
        Extract playlist metadata and prefer true square playlist artwork.

        Apple pages can contain several images:
          - the playlist cover
          - album artwork for individual tracks
          - wide OpenGraph/social preview cards

        Rank playlist-level square artwork above social preview images.
        """
        name = ""
        description = ""

        # First obtain the playlist identity from SEO data.
        schema_images = []

        for obj in cls._walk_json(data):
            schema = obj.get("schemaContent")
            if not isinstance(schema, dict):
                continue

            schema_type = str(
                schema.get("@type")
                or schema.get("type")
                or ""
            ).casefold()

            if "playlist" not in schema_type and name:
                continue

            if not name:
                name = schema.get("name", "") or ""

            if not description:
                description = (
                    schema.get("description", "")
                    or schema.get("abstract", "")
                    or ""
                )

            raw_image = (
                schema.get("image")
                or schema.get("thumbnailUrl")
            )
            if raw_image:
                schema_images.append(raw_image)

        if not name:
            meta = soup.find("meta", attrs={"name": "apple:title"})
            if meta:
                name = meta.get("content", "") or ""

        if not name:
            meta = soup.find("meta", attrs={"property": "og:title"})
            if meta:
                name = meta.get("content", "") or ""

        if not description:
            meta = soup.find(
                "meta",
                attrs={"property": "og:description"},
            )
            if meta:
                description = meta.get("content", "") or ""

        if name.endswith(" - Apple Music"):
            name = name[:-14].strip()

        target_name = name.casefold().strip()
        candidates = []

        def add_candidate(raw, context_score=0, label="unknown"):
            url = cls._normalize_artwork_url(raw)
            if not url:
                return

            width, height = cls._artwork_dimensions_from_value(raw)

            # If the URL was a template, dimensions may no longer be visible
            # in the normalized URL. Treat requested dimensions as a hint,
            # but Plex will validate the actual downloaded pixels later.
            if not width or not height:
                width, height = cls._artwork_dimensions_from_value(url)

            score = float(context_score)

            if width and height:
                ratio = width / height if height else 0

                if 0.95 <= ratio <= 1.05:
                    score += 80
                elif 0.80 <= ratio <= 1.20:
                    score += 25
                else:
                    # Strongly demote wide social/banner art.
                    score -= 80

                score += min(min(width, height) / 100.0, 25.0)

            if "{w}" in str(raw) or "{h}" in str(raw):
                score += 20

            # Social-preview markers are weak candidates unless they are
            # actually square.
            if re.search(
                r"\d+x\d+(?:wp|sr|mv)",
                url,
                re.IGNORECASE,
            ):
                score -= 20

            candidates.append(
                {
                    "url": url,
                    "score": score,
                    "width": width,
                    "height": height,
                    "label": label,
                }
            )

        # Strongest candidates: objects that look like the playlist itself.
        for obj in cls._walk_json(data):
            obj_name = str(
                obj.get("name")
                or obj.get("title")
                or ""
            ).casefold().strip()

            obj_type = str(
                obj.get("kind")
                or obj.get("type")
                or obj.get("contentType")
                or obj.get("entityType")
                or ""
            ).casefold()

            play_params = obj.get("playParams")
            if isinstance(play_params, dict):
                obj_type += " " + str(
                    play_params.get("kind")
                    or play_params.get("type")
                    or ""
                ).casefold()

            exact_name = bool(
                target_name
                and obj_name
                and obj_name == target_name
            )
            playlist_type = "playlist" in obj_type

            if not (exact_name or playlist_type):
                continue

            context_score = 0
            if exact_name:
                context_score += 100
            if playlist_type:
                context_score += 60

            for key in (
                "artwork",
                "image",
                "images",
                "coverArt",
                "cover",
                "artworkUrl",
                "artworkURL",
            ):
                if key in obj:
                    add_candidate(
                        obj.get(key),
                        context_score=context_score,
                        label=f"playlist:{key}",
                    )

        # SEO images are fallbacks; these are often 1200x630 social cards.
        for raw in schema_images:
            add_candidate(
                raw,
                context_score=10,
                label="schema",
            )

        # OpenGraph image is the final fallback.
        og = soup.find("meta", attrs={"property": "og:image"})
        if og:
            add_candidate(
                og.get("content", ""),
                context_score=0,
                label="og:image",
            )

        candidates.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        image_url = candidates[0]["url"] if candidates else ""

        if candidates:
            best = candidates[0]
            dim_text = ""
            if best["width"] and best["height"]:
                dim_text = (
                    f" ({best['width']}x{best['height']} declared)"
                )

            print(
                f"  ✓ Apple artwork candidate [{best['label']}]"
                f"{dim_text}: {best['url']}"
            )

        return {
            "name": repair_text(
                name or "Apple Music Playlist"
            ),
            "description": clean_playlist_description(
                description
            ),
            "image_url": image_url,
        }


    @staticmethod
    def _track_from_item(item: dict) -> Optional[dict]:
        """Convert one Apple server-data item into our common track format."""
        if not isinstance(item, dict):
            return None

        artist = item.get("artistName")
        title = item.get("title") or item.get("name")

        if not isinstance(artist, str) or not artist.strip():
            return None
        if not isinstance(title, str) or not title.strip():
            return None

        # The server data can contain artist/album cards too. A real song
        # item normally has one or more of these track-specific fields.
        track_markers = (
            "duration",
            "playParams",
            "tertiaryLinks",
            "audioTraits",
            "contentDescriptor",
            "releaseDate",
        )
        if not any(key in item for key in track_markers):
            return None

        album = item.get("albumName", "") or ""

        if not album:
            tertiary = item.get("tertiaryLinks")
            if isinstance(tertiary, list) and tertiary:
                first = tertiary[0]
                if isinstance(first, dict):
                    album = first.get("title", "") or ""

        source_id = (
            item.get("id")
            or item.get("adamId")
            or ""
        )

        play_params = item.get("playParams")
        if isinstance(play_params, dict):
            source_id = (
                source_id
                or play_params.get("catalogId")
                or play_params.get("id")
                or ""
            )

        return {
            "title": repair_text(title).strip(),
            "artist": repair_text(artist).strip(),
            "album": (
                repair_text(album).strip()
                if isinstance(album, str)
                else ""
            ),
            "source_id": str(source_id) if source_id else "",
        }

    @classmethod
    def _extract_tracks(cls, data) -> List[dict]:
        """Extract ordered playlist tracks from serialized-server-data."""
        tracks = []
        seen = set()

        def add_track(item):
            track = cls._track_from_item(item)
            if not track:
                return

            # Prefer catalog ID for dedupe, otherwise title + artist + album.
            key = (
                ("id", track["source_id"])
                if track["source_id"]
                else (
                    "text",
                    track["title"].casefold(),
                    track["artist"].casefold(),
                    track["album"].casefold(),
                )
            )

            if key in seen:
                return

            seen.add(key)
            tracks.append(track)

        # First pass: Apple playlist pages currently organize songs under
        # section["items"]. Walking those lists preserves playlist order.
        for obj in cls._walk_json(data):
            sections = obj.get("sections")
            if not isinstance(sections, list):
                continue

            for section in sections:
                if not isinstance(section, dict):
                    continue
                items = section.get("items")
                if not isinstance(items, list):
                    continue
                for item in items:
                    add_track(item)

        if tracks:
            return tracks

        # Fallback for future layout changes: scan all dictionaries while
        # retaining traversal order.
        for obj in cls._walk_json(data):
            add_track(obj)

        return tracks

    @classmethod
    def _extract_metadata_without_artwork(cls, data, soup) -> dict:
        """Extract playlist name/description without inspecting artwork."""
        name = ""
        description = ""

        for obj in cls._walk_json(data):
            schema = obj.get("schemaContent")
            if not isinstance(schema, dict):
                continue

            schema_type = str(
                schema.get("@type")
                or schema.get("type")
                or ""
            ).casefold()

            if "playlist" not in schema_type:
                continue

            if not name:
                name = schema.get("name", "") or ""

            if not description:
                description = (
                    schema.get("description", "")
                    or schema.get("abstract", "")
                    or ""
                )

            if name and description:
                break

        if not name:
            meta = soup.find("meta", attrs={"name": "apple:title"})
            if meta:
                name = meta.get("content", "") or ""

        if not name:
            meta = soup.find("meta", attrs={"property": "og:title"})
            if meta:
                name = meta.get("content", "") or ""

        if not description:
            meta = soup.find(
                "meta",
                attrs={"property": "og:description"},
            )
            if meta:
                description = meta.get("content", "") or ""

        if name.endswith(" - Apple Music"):
            name = name[:-14].strip()

        return {
            "name": repair_text(
                name or "Apple Music Playlist"
            ),
            "description": clean_playlist_description(
                description
            ),
            "image_url": "",
        }

    def get_playlist_tracks(
        self,
        playlist_url: str,
        fetch_artwork: bool = True,
    ) -> Tuple[List[dict], dict]:
        """
        Fetch tracks and metadata from a public Apple Music playlist.

        Artwork discovery is optional so non-sync workflows can fetch only
        the metadata needed for matching.
        """

        playlist_id = Config._extract_id(
            playlist_url,
            "applemusic",
        )

        if not playlist_id:
            raise Exception(
                "Could not extract Apple Music playlist ID from the supplied URL"
            )

        normalized_input = Config._normalize_url_input(playlist_url)

        if normalized_input.startswith("http"):
            url = normalized_input
        else:
            # Apple ignores the human-readable slug when the ID is valid.
            url = (
                f"https://music.apple.com/us/playlist/playlist/"
                f"{playlist_id}"
            )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }

        try:
            resp = requests.get(
                url,
                headers=headers,
                timeout=15,
            )

            if resp.status_code != 200:
                raise Exception(
                    f"Apple Music returned HTTP {resp.status_code} "
                    f"for {url}"
                )

            soup = BeautifulSoup(
                resp.text,
                "html.parser",
            )

            script = soup.find(
                "script",
                id="serialized-server-data",
            )

            if not script:
                raise Exception(
                    "Could not find Apple Music serialized-server-data "
                    "in the playlist page"
                )

            raw_json = script.string or script.get_text()

            if not raw_json or not raw_json.strip():
                raise Exception(
                    "Apple Music serialized-server-data was empty"
                )

            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError as e:
                raise Exception(
                    f"Could not parse Apple Music server data: {e}"
                )

            if fetch_artwork:
                metadata = self._extract_metadata(
                    data,
                    soup,
                )
            else:
                metadata = self._extract_metadata_without_artwork(
                    data,
                    soup,
                )

            tracks = self._extract_tracks(data)

            if not tracks:
                raise Exception(
                    "Apple Music page loaded, but no playlist tracks "
                    "could be extracted from serialized-server-data"
                )

            if fetch_artwork and not metadata.get("image_url"):
                print(
                    "  ⚠ No Apple Music playlist artwork found"
                )

            metadata["source_url"] = url
            metadata["source_id"] = playlist_id

            return tracks, metadata

        except requests.exceptions.Timeout:
            raise Exception(
                "Request timed out. Apple Music is not responding."
            )
        except requests.exceptions.RequestException as e:
            raise Exception(
                f"Apple Music connection error: {e}"
            )
        except Exception as e:
            raise Exception(
                f"Failed to fetch Apple Music playlist: {e}"
            )


class PlexAPI:
    """Plex API wrapper"""

    def __init__(self, plex_url: str, plex_token: str):
        self.base_url = plex_url.rstrip("/")
        self.token = plex_token
        self.headers = {
            "X-Plex-Token": plex_token,
            "Accept": "application/json",
        }
        self.machine_identifier = self._get_machine_identifier()

    def _get_machine_identifier(self) -> str:
        """Get Plex server machine identifier."""
        try:
            resp = requests.get(
                f"{self.base_url}/identity",
                headers=self.headers,
                timeout=10,
            )

            if resp.status_code != 200:
                raise Exception(
                    f"Plex /identity returned HTTP {resp.status_code}: "
                    f"{resp.text[:500]}"
                )

            data = resp.json()
            identifier = data.get("MediaContainer", {}).get(
                "machineIdentifier"
            )

            if not identifier:
                raise Exception(
                    "Plex did not return a machineIdentifier"
                )

            return identifier

        except requests.RequestException as e:
            raise Exception(
                f"Could not connect to Plex /identity: {e}"
            )
        except ValueError as e:
            raise Exception(
                f"Plex returned invalid JSON from /identity: {e}"
            )

    def _library_uri(self, plex_track_id: str) -> str:
        """
        Build the URI Plex expects for library media in playlists.
        """
        return (
            f"server://{self.machine_identifier}"
            f"/com.plexapp.plugins.library/library/metadata/"
            f"{plex_track_id}"
        )

    def search_library(
        self, title: str = "", artist: str = ""
    ) -> List[dict]:
        """Load all tracks from the first Plex music library."""

        try:
            resp = requests.get(
                f"{self.base_url}/library/sections",
                headers=self.headers,
                timeout=15,
            )

            if resp.status_code != 200:
                print(
                    f"Failed to get library sections: "
                    f"{resp.status_code}"
                )
                return []

            sections = (
                resp.json()
                .get("MediaContainer", {})
                .get("Directory", [])
            )

            music_sections = [
                s for s in sections if s.get("type") == "artist"
            ]

            if not music_sections:
                print("No music library found in Plex")
                return []

            section_id = music_sections[0]["key"]

            resp = requests.get(
                f"{self.base_url}/library/sections/{section_id}/all",
                headers=self.headers,
                params={"type": 10},
                timeout=30,
            )

            if resp.status_code != 200:
                print(
                    f"Failed to fetch tracks: {resp.status_code}"
                )
                return []

            tracks = (
                resp.json()
                .get("MediaContainer", {})
                .get("Metadata", [])
            )

            return [
                {
                    "title": repair_text(t.get("title", "")),
                    # Plex uses originalTitle for the track artist when it
                    # differs from the album artist (common on soundtracks
                    # and Various Artists compilations).
                    "artist": repair_text(
                        t.get("originalTitle")
                        or t.get("grandparentTitle", "")
                    ),
                    "track_artist": repair_text(
                        t.get("originalTitle", "")
                    ),
                    "album_artist": repair_text(
                        t.get("grandparentTitle", "")
                    ),
                    "album": repair_text(
                        t.get("parentTitle", "")
                    ),
                    "plex_id": str(t.get("ratingKey")),
                    "key": t.get("key"),
                }
                for t in tracks
                if t.get("ratingKey")
            ]

        except Exception as e:
            print(f"Error searching library: {e}")
            return []

    def get_audio_playlists(self) -> List[dict]:
        """
        Return every Plex audio playlist visible to this server/token.

        This is used only by read-only developer diagnostics. Both normal and
        smart audio playlists are included when Plex exposes them.
        """

        try:
            resp = requests.get(
                f"{self.base_url}/playlists",
                headers=self.headers,
                timeout=15,
            )

            if resp.status_code != 200:
                print(
                    f"Failed to get Plex playlists: "
                    f"{resp.status_code}"
                )
                return []

            playlists = (
                resp.json()
                .get("MediaContainer", {})
                .get("Metadata", [])
            )

            results = []

            for playlist in playlists:
                playlist_type = str(
                    playlist.get("playlistType")
                    or playlist.get("type")
                    or ""
                ).casefold()

                # Plex normally reports playlistType="audio". If the field is
                # absent on a server/version, retain the item unless it is
                # explicitly known to be video/photo.
                if playlist_type in (
                    "video",
                    "photo",
                ):
                    continue

                if (
                    playlist_type
                    and playlist_type != "audio"
                ):
                    continue

                rating_key = playlist.get(
                    "ratingKey"
                )

                if rating_key is None:
                    continue

                results.append(
                    {
                        "plex_id": str(rating_key),
                        "title": repair_text(
                            playlist.get("title", "")
                        ),
                        "smart": bool(
                            playlist.get("smart")
                        ),
                        "leaf_count": playlist.get(
                            "leafCount"
                        ),
                    }
                )

            return results

        except Exception as e:
            print(
                f"Error getting Plex playlists: {e}"
            )
            return []

    def get_playlist(self, playlist_id: str) -> dict:
        """Get playlist details."""

        try:
            resp = requests.get(
                f"{self.base_url}/playlists/{playlist_id}",
                headers=self.headers,
                timeout=10,
            )

            if resp.status_code == 200:
                return (
                    resp.json()
                    .get("MediaContainer", {})
                    .get("Metadata", [{}])[0]
                )

            print(
                f"Failed to get playlist details: {resp.status_code}"
            )
            return {}

        except Exception as e:
            print(f"Error getting playlist: {e}")
            return {}

    def get_playlist_items(self, playlist_id: str) -> List[dict]:
        """
        Get playlist items.

        IMPORTANT:
        Plex exposes playlistItemID for the item inside the playlist.
        That is different from the track's ratingKey and is what must
        be used when deleting a playlist item.
        """

        try:
            resp = requests.get(
                f"{self.base_url}/playlists/{playlist_id}/items",
                headers=self.headers,
                timeout=15,
            )

            if resp.status_code != 200:
                print(
                    f"Failed to get playlist items: "
                    f"{resp.status_code}"
                )
                return []

            items = (
                resp.json()
                .get("MediaContainer", {})
                .get("Metadata", [])
            )

            return [
                {
                    "playlist_item_id": i.get("playlistItemID"),
                    "plex_id": str(i.get("ratingKey"))
                    if i.get("ratingKey") is not None
                    else None,
                    "title": i.get("title", ""),
                }
                for i in items
            ]

        except Exception as e:
            print(f"Error getting playlist items: {e}")
            return []

    def create_playlist(
        self,
        title: str,
        first_track_plex_id: str,
        description: str = "",
    ) -> Optional[str]:
        """
        Create a normal Plex audio playlist.

        Plex requires a media URI when creating a normal playlist, so
        the first matched track is used as the initial playlist item.
        """

        try:
            uri = self._library_uri(first_track_plex_id)

            resp = requests.post(
                f"{self.base_url}/playlists",
                headers=self.headers,
                params={
                    "type": "audio",
                    "title": title,
                    "smart": 0,
                    "uri": uri,
                },
                timeout=15,
            )

            if resp.status_code not in [200, 201]:
                print(
                    f"Plex error ({resp.status_code}): "
                    f"{resp.text[:2000]}"
                )
                return None

            try:
                data = resp.json()
            except ValueError:
                print(
                    "Plex created the playlist but returned "
                    f"non-JSON data: {resp.text[:1000]}"
                )
                return None

            container = data.get("MediaContainer", {})
            metadata = container.get("Metadata", [])

            if not metadata:
                print(
                    f"No playlist metadata in Plex response: "
                    f"{resp.text[:2000]}"
                )
                return None

            playlist_id = metadata[0].get("ratingKey")

            if not playlist_id:
                print(
                    "Plex response did not contain a playlist ratingKey"
                )
                return None

            # Description is updated separately because Plex playlist
            # creation does not reliably accept it in all versions.
            if description:
                self.update_playlist_metadata(
                    str(playlist_id), title, description
                )

            return str(playlist_id)

        except requests.RequestException as e:
            print(f"Error creating playlist: {e}")
            return None
        except Exception as e:
            print(f"Error creating playlist: {e}")
            return None

    def add_to_playlist(
        self, playlist_id: str, track_plex_id: str
    ) -> bool:
        """Add a Plex library track to a Plex playlist."""

        try:
            uri = self._library_uri(track_plex_id)

            resp = requests.put(
                f"{self.base_url}/playlists/{playlist_id}/items",
                headers=self.headers,
                params={"uri": uri},
                timeout=15,
            )

            if resp.status_code not in [200, 201]:
                print(
                    f"Warning: Failed to add track "
                    f"{track_plex_id}: {resp.status_code} "
                    f"{resp.text[:500]}"
                )
                return False

            return True

        except Exception as e:
            print(f"Error adding to playlist: {e}")
            return False

    def remove_from_playlist(
        self, playlist_id: str, playlist_item_id: str
    ) -> bool:
        """
        Remove an item from a Plex playlist.

        playlist_item_id must be Plex's playlistItemID, not the
        track's ratingKey.
        """

        try:
            resp = requests.delete(
                f"{self.base_url}/playlists/{playlist_id}/items/"
                f"{playlist_item_id}",
                headers=self.headers,
                timeout=15,
            )

            if resp.status_code not in [200, 204]:
                print(
                    f"Warning: Failed to remove playlist item "
                    f"{playlist_item_id}: {resp.status_code} "
                    f"{resp.text[:500]}"
                )
                return False

            return True

        except Exception as e:
            print(f"Error removing from playlist: {e}")
            return False

    def clear_playlist(self, playlist_id: str) -> bool:
        """
        Remove every item from a playlist.

        Items are removed one at a time because Plex's playlist item
        endpoint identifies each item by playlistItemID.
        """

        items = self.get_playlist_items(playlist_id)

        if not items:
            return True

        success = True

        for item in items:
            item_id = item.get("playlist_item_id")

            if not item_id:
                print(
                    f"Warning: Playlist item for "
                    f"'{item.get('title', 'Unknown')}' has no "
                    "playlistItemID; cannot remove it."
                )
                success = False
                continue

            if not self.remove_from_playlist(
                playlist_id, str(item_id)
            ):
                success = False

        return success

    def update_playlist_metadata(
        self,
        playlist_id: str,
        title: str,
        description: str,
        artwork_url: str = None,
    ):
        """Update playlist name, description, and optionally artwork."""

        try:
            clean_title = repair_text(
                title
            )
            clean_description = clean_playlist_description(
                description or ""
            )

            params = {
                "title": clean_title,
                "summary": clean_description,
            }

            resp = requests.put(
                f"{self.base_url}/playlists/{playlist_id}",
                headers=self.headers,
                params=params,
                timeout=15,
            )

            if resp.status_code not in [200, 204]:
                print(
                    f"Warning: Failed to update playlist metadata: "
                    f"{resp.status_code} {resp.text[:500]}"
                )

            # Attempt to update artwork if URL provided
            if artwork_url:
                if self._update_playlist_artwork(
                    playlist_id,
                    artwork_url,
                ):
                    print("  ✓ Synced artwork from source")

        except Exception as e:
            print(f"Error updating playlist metadata: {e}")

    @staticmethod
    def _detect_image_dimensions(data: bytes) -> Tuple[Optional[int], Optional[int]]:
        """
        Detect PNG/JPEG dimensions using only the Python standard library.
        This avoids adding Pillow as a required dependency.
        """
        if not data:
            return None, None

        # PNG: signature + IHDR width/height.
        if (
            len(data) >= 24
            and data[:8] == b"\x89PNG\r\n\x1a\n"
        ):
            width = int.from_bytes(data[16:20], "big")
            height = int.from_bytes(data[20:24], "big")
            return width, height

        # JPEG: scan marker segments until a Start Of Frame marker.
        if len(data) >= 4 and data[:2] == b"\xff\xd8":
            i = 2
            sof_markers = {
                0xC0, 0xC1, 0xC2, 0xC3,
                0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB,
                0xCD, 0xCE, 0xCF,
            }

            while i + 3 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue

                while i < len(data) and data[i] == 0xFF:
                    i += 1

                if i >= len(data):
                    break

                marker = data[i]
                i += 1

                # Standalone markers.
                if marker in (0xD8, 0xD9):
                    continue

                if i + 1 >= len(data):
                    break

                segment_length = int.from_bytes(
                    data[i:i + 2],
                    "big",
                )

                if segment_length < 2:
                    break

                if marker in sof_markers and i + 7 < len(data):
                    height = int.from_bytes(
                        data[i + 3:i + 5],
                        "big",
                    )
                    width = int.from_bytes(
                        data[i + 5:i + 7],
                        "big",
                    )
                    return width, height

                i += segment_length

        return None, None

    @staticmethod
    def _apple_artwork_variants(url: str) -> List[str]:
        """
        Generate safer Apple CDN alternatives.

        "bb" preserves the original aspect ratio. For a wide social card,
        Apple's CDN may therefore return 3000x750 even when the request says
        3000x3000bb. A "cc" variant asks the CDN for a square crop and is
        useful as a fallback when no true square playlist artwork was found.
        """
        variants = [url]

        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            return variants

        if "mzstatic" not in host:
            return variants

        size = APPLE_ARTWORK_SIZE

        # Replace a fixed final Apple rendition with square crop variants.
        match = re.search(
            r"/\d+x\d+[A-Za-z0-9._-]*\.(?:jpe?g|png|webp)$",
            url,
            re.IGNORECASE,
        )

        if match:
            base = url[:match.start()]
            for suffix in (
                f"/{size}x{size}cc.jpg",
                f"/{size}x{size}bb-999.jpg",
            ):
                candidate = base + suffix
                if candidate not in variants:
                    variants.append(candidate)

        # If already using bb, explicitly try cc.
        cc = re.sub(
            r"/(\d+)x(\d+)bb(?:-\d+)?\.(jpe?g|png|webp)$",
            r"/\1x\2cc.\3",
            url,
            flags=re.IGNORECASE,
        )
        if cc != url and cc not in variants:
            variants.append(cc)

        return variants

    def _update_playlist_artwork(
        self,
        playlist_id: str,
        artwork_url: str,
    ) -> bool:
        """
        Download source artwork, verify its real pixel dimensions, and upload
        only a suitable square poster to Plex.
        """

        if not artwork_url:
            return False

        variants = self._apple_artwork_variants(
            artwork_url
        )

        last_error = None

        for index, candidate_url in enumerate(variants, 1):
            try:
                image_resp = requests.get(
                    candidate_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        ),
                        "Accept": (
                            "image/avif,image/webp,image/apng,"
                            "image/*,*/*;q=0.8"
                        ),
                    },
                    timeout=15,
                )

                if image_resp.status_code != 200:
                    last_error = (
                        f"HTTP {image_resp.status_code} downloading "
                        f"artwork variant {index}"
                    )
                    continue

                content_type = (
                    image_resp.headers.get(
                        "Content-Type",
                        "",
                    )
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )

                if not content_type.startswith("image/"):
                    last_error = (
                        f"variant {index} returned "
                        f"{content_type or 'unknown content type'}"
                    )
                    continue

                if not image_resp.content:
                    last_error = (
                        f"variant {index} returned an empty image"
                    )
                    continue

                width, height = self._detect_image_dimensions(
                    image_resp.content
                )

                if width and height:
                    print(
                        f"  → Artwork variant {index}: "
                        f"{width}x{height} actual pixels"
                    )

                    ratio = width / height if height else 0

                    if not (0.95 <= ratio <= 1.05):
                        print(
                            "    ↳ rejected: not square enough "
                            "for a Plex playlist poster"
                        )
                        last_error = (
                            f"variant {index} was {width}x{height}"
                        )
                        continue

                    # Avoid tiny thumbnails masquerading as high-res art.
                    if min(width, height) < 600:
                        print(
                            "    ↳ rejected: artwork is below "
                            "600x600"
                        )
                        last_error = (
                            f"variant {index} was only {width}x{height}"
                        )
                        continue
                else:
                    # Unknown format: still allow it only for non-Apple art.
                    try:
                        host = (
                            urlparse(candidate_url).hostname
                            or ""
                        ).lower()
                    except ValueError:
                        host = ""

                    if "mzstatic" in host:
                        last_error = (
                            "could not verify Apple artwork dimensions"
                        )
                        continue

                upload_resp = requests.post(
                    f"{self.base_url}/library/metadata/"
                    f"{playlist_id}/posters",
                    headers={
                        "X-Plex-Token": self.token,
                        "Content-Type": content_type,
                    },
                    data=image_resp.content,
                    timeout=20,
                )

                if upload_resp.status_code in [
                    200, 201, 204
                ]:
                    if width and height:
                        print(
                            f"  ✓ Plex poster uploaded at "
                            f"{width}x{height}"
                        )
                    return True

                last_error = (
                    f"Plex poster upload HTTP "
                    f"{upload_resp.status_code}"
                )

            except requests.exceptions.Timeout:
                last_error = (
                    f"artwork variant {index} timed out"
                )
            except requests.exceptions.RequestException as e:
                last_error = (
                    f"artwork variant {index} request error: {e}"
                )
            except Exception as e:
                last_error = (
                    f"artwork variant {index} error: {e}"
                )

        print(
            "  ⚠ No suitable square artwork was uploaded"
        )
        if last_error:
            print(f"    Last artwork issue: {last_error}")

        return False



class Matcher:
    """Track matching logic with title/artist identity + album preference."""

    MATCH_THRESHOLD = 90
    PROMPT_THRESHOLD = 70
    MIN_DISPLAY_SCORE = 50

    # These are ranking penalties, not hard exclusions. If the only copy
    # available is on a compilation/live/deluxe release, it can still match.
    ALBUM_TYPE_PENALTIES = {
        "compilation": 14,
        "live": 16,
        "remix": 14,
        "acoustic": 10,
        "demo": 16,
        "session": 14,
        "deluxe": 7,
        "remaster": 5,
    }

    # Track-title markers that identify a distinct recording/version.
    # Featured-artist credits are intentionally NOT included here.
    # "session" means branded platform sessions (iTunes/Apple Music/Spotify),
    # not generic album-era provenance such as "(Evolver Sessions)".
    VERSION_TYPES = {
        "remix",
        "live",
        "acoustic",
        "demo",
        "session",
    }

    @staticmethod
    def _normalize_match_text(value: str) -> str:
        """Normalize punctuation/whitespace used in title and artist scoring."""
        if not value:
            return ""

        text = repair_text(value).casefold()
        text = (
            text.replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"')
            .replace("–", "-")
            .replace("—", "-")
        )
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _strip_title_metadata(cls, title: str) -> str:
        """
        Remove common release/credit qualifiers that are usually metadata,
        while leaving arbitrary parenthetical subtitles intact.

        Examples:
            Dark Sky (feat. S.A. Martinez) -> Dark Sky
            Song (Remastered 2011) -> Song
            Song - Radio Edit -> Song
        """
        value = cls._normalize_match_text(title)

        if not value:
            return ""

        # Parenthetical/bracketed metadata.
        metadata_parenthetical = re.compile(
            r"\s*[\(\[]\s*"
            r"(?:"
            r"feat(?:uring)?\.?|ft\.?|with|"
            r"remaster(?:ed)?(?:\s+\d{4})?|"
            r"live\b[^)\]]*|"
            r"acoustic|stripped|"
            r"demo\b[^)\]]*|"
            r"(?:itunes\s+)?sessions?\b[^)\]]*|"
            r"[^)\]]+\s+sessions?\b[^)\]]*|"
            r"radio\s+edit|single\s+edit|edit|"
            r"remix(?:ed)?|mix|"
            r"[^)\]]+\s+(?:remix|mix)\b[^)\]]*|"
            r"mono|stereo|"
            r"bonus\s+track|"
            r"from\s+.+?(?:soundtrack|motion\s+picture)"
            r")"
            r"[^)\]]*[\)\]]",
            re.IGNORECASE,
        )

        value = metadata_parenthetical.sub(" ", value)

        # Suffix metadata outside parentheses.
        value = re.sub(
            r"\s*[-:]\s*"
            r"(?:"
            r"feat(?:uring)?\.?|ft\.?|with|"
            r"remaster(?:ed)?(?:\s+\d{4})?|"
            r"live(?:\s+(?:at|from|in|on)\b.*)?|"
            r"acoustic|stripped|"
            r"demo\b.*|"
            r"(?:itunes\s+)?sessions?\b.*|"
            r"radio\s+edit|single\s+edit|edit|"
            r"remix(?:ed)?|mix|mono|stereo"
            r")\b.*$",
            "",
            value,
            flags=re.IGNORECASE,
        )

        # Featured-credit suffix without punctuation.
        value = re.sub(
            r"\s+(?:feat(?:uring)?\.?|ft\.?)\s+.+$",
            "",
            value,
            flags=re.IGNORECASE,
        )

        return re.sub(r"\s+", " ", value).strip(" -:")

    @classmethod
    def _strip_trailing_parenthetical(cls, title: str) -> Tuple[str, bool]:
        """
        Return title without one arbitrary trailing (...) or [...] qualifier.

        This broad fallback is only compared when one side has the trailing
        qualifier and the other side does not. That avoids collapsing:
            Song (Part 1)
            Song (Part 2)
        into the same title.
        """
        value = cls._normalize_match_text(title)

        if not value:
            return "", False

        stripped = re.sub(
            r"\s*[\(\[][^)\]]+[\)\]]\s*$",
            "",
            value,
        ).strip()

        return stripped, stripped != value

    @classmethod
    def _title_score(cls, source_title: str, plex_title: str) -> Tuple[int, int]:
        """
        Return (best_title_score, raw_title_score).

        The best score considers:
        - literal titles;
        - safe metadata-stripped titles;
        - a one-sided arbitrary trailing-parenthetical fallback.

        The one-sided rule is what allows:
            Austin (Boots Stop Workin') <-> Austin
        without making:
            Song (Part 1) <-> Song (Part 2)
        an artificial 100% match.
        """
        source_raw = cls._normalize_match_text(source_title)
        plex_raw = cls._normalize_match_text(plex_title)

        raw_score = fuzz.token_sort_ratio(
            source_raw,
            plex_raw,
        )

        scores = [raw_score]

        source_meta = cls._strip_title_metadata(source_raw)
        plex_meta = cls._strip_title_metadata(plex_raw)

        if source_meta and plex_meta:
            scores.append(
                fuzz.token_sort_ratio(
                    source_meta,
                    plex_meta,
                )
            )

        if source_meta and plex_raw:
            scores.append(
                fuzz.token_sort_ratio(
                    source_meta,
                    plex_raw,
                )
            )

        if source_raw and plex_meta:
            scores.append(
                fuzz.token_sort_ratio(
                    source_raw,
                    plex_meta,
                )
            )

        source_base, source_had_trailing = (
            cls._strip_trailing_parenthetical(source_meta)
        )
        plex_base, plex_had_trailing = (
            cls._strip_trailing_parenthetical(plex_meta)
        )

        # Generic parenthetical fallback only if ONE side has it.
        if source_had_trailing and not plex_had_trailing:
            if source_base and plex_meta:
                scores.append(
                    fuzz.token_sort_ratio(
                        source_base,
                        plex_meta,
                    )
                )

        # Deliberately do NOT apply the arbitrary fallback in reverse.
        # A destination-only qualifier can identify a different recording or
        # arrangement, e.g.:
        #   Bring Me to Life -> Bring Me to Life (Synthesis)
        #
        # Known metadata such as feat/remaster/live/remix is already handled
        # by _strip_title_metadata() and the release-type penalties below.

        return max(scores), raw_score

    @classmethod
    def _title_remix_credit(cls, title: str) -> str:
        """
        Extract a named remix credit from a title.

        Example:
            Dracula (JENNIE Remix) -> jennie

        A generic "(Remix)" does not identify a collaborator and therefore
        returns an empty string.
        """
        value = cls._normalize_match_text(title)

        if not value:
            return ""

        match = re.search(
            r"[\(\[]\s*(.+?)\s+remix\s*[\)\]]",
            value,
            flags=re.IGNORECASE,
        )

        if not match:
            return ""

        credit = match.group(1).strip()

        if not credit or credit == "remix":
            return ""

        return credit

    @classmethod
    def _title_has_feature_credit(cls, title: str) -> bool:
        """Return True when a title explicitly identifies a featured guest."""
        value = cls._normalize_match_text(title)

        if not value:
            return False

        return bool(
            re.search(
                r"(?:^|[\s(\[\-:])"
                r"(?:feat(?:uring)?\.?|ft\.?|with)"
                r"\s+",
                value,
                flags=re.IGNORECASE,
            )
        )

    @classmethod
    def _artist_variants(
        cls,
        artist: str,
        allow_primary_collaborator: bool = False,
    ) -> List[str]:
        """
        Generate conservative artist variants.

        When the source title explicitly says "feat." (or equivalent), the
        first/primary portion of a collaboration string is also considered.
        This allows:
            AWOLNATION & Nothing But Thieves -> AWOLNATION
        for:
            Maniac (feat. Conor Mason of Nothing but Thieves)

        We only enable that behavior when the track title itself tells us the
        additional artist is a feature, so ordinary co-billed artists are not
        silently discarded.
        """
        value = cls._normalize_match_text(artist)

        if not value:
            return [""]

        variants = [value]

        # Artist-string feature syntax.
        primary = re.sub(
            r"\s+(?:feat(?:uring)?\.?|ft\.?|with)\s+.+$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

        if primary and primary not in variants:
            variants.append(primary)

        if allow_primary_collaborator:
            # Add progressively shorter collaboration prefixes. This is safer
            # than blindly taking only the first token because artist names
            # can themselves contain "&".
            for separator in (" & ", " x ", " and "):
                if separator not in value:
                    continue

                parts = value.split(separator)

                # All prefixes except the complete original value.
                for end in range(1, len(parts)):
                    candidate = separator.join(parts[:end]).strip()
                    if candidate and candidate not in variants:
                        variants.append(candidate)

        return variants

    @classmethod
    def _artist_score(
        cls,
        source_artist: str,
        plex_artist: str,
        source_title: str = "",
        plex_title: str = "",
    ) -> int:
        """Return the best conservative artist score."""
        remix_credit = cls._title_remix_credit(
            source_title
        )

        allow_source_primary = (
            cls._title_has_feature_credit(source_title)
            or (
                bool(remix_credit)
                and remix_credit
                in cls._normalize_match_text(source_artist)
            )
        )

        source_variants = cls._artist_variants(
            source_artist,
            allow_primary_collaborator=allow_source_primary,
        )

        plex_variants = cls._artist_variants(
            plex_artist,
            allow_primary_collaborator=cls._title_has_feature_credit(
                plex_title
            ),
        )

        return max(
            fuzz.ratio(source_variant, plex_variant)
            for source_variant in source_variants
            for plex_variant in plex_variants
        )


    @classmethod
    def _title_release_types(cls, title: str) -> set:
        """
        Detect explicit recording/version intent in a track title.

        Featured-artist credits are deliberately excluded because they may
        appear on only one service while still referring to the same track.
        """
        value = cls._normalize_match_text(title)

        if not value:
            return set()

        kinds = set()

        # Remix and named "Mix" variants.
        remix_patterns = (
            r"\bremix(?:ed|es)?\b",
            r"\bmixes\b",
            r"[\(\[][^)\]]+\s+mix\b[^)\]]*[\)\]]",
            r"\s[-:]\s*[^-:]*\bmix\b.*$",
        )

        if any(
            re.search(pattern, value, flags=re.IGNORECASE)
            for pattern in remix_patterns
        ):
            kinds.add("remix")

        # Live is deliberately conservative so a real title such as
        # "Live Through This" is not treated as a live recording.
        live_patterns = (
            r"[\(\[]\s*live\b[^)\]]*[\)\]]",
            r"\s[-:]\s*live(?:\s+(?:at|from|in|on)\b.*)?$",
            r"\blive\s+(?:at|from|in|on)\b",
            r"\bunplugged\b",
            r"\bin concert\b",
        )

        if any(
            re.search(pattern, value, flags=re.IGNORECASE)
            for pattern in live_patterns
        ):
            kinds.add("live")

        acoustic_patterns = (
            r"[\(\[][^)\]]*\bacoustic\b[^)\]]*[\)\]]",
            r"\s[-:]\s*[^-:]*\bacoustic\b.*$",
            r"[\(\[][^)\]]*\bstripped\b[^)\]]*[\)\]]",
            r"\s[-:]\s*[^-:]*\bstripped\b.*$",
        )

        if any(
            re.search(pattern, value, flags=re.IGNORECASE)
            for pattern in acoustic_patterns
        ):
            kinds.add("acoustic")

        demo_patterns = (
            r"[\(\[][^)\]]*\bdemo\b[^)\]]*[\)\]]",
            r"\s[-:]\s*[^-:]*\bdemo\b.*$",
        )

        if any(
            re.search(pattern, value, flags=re.IGNORECASE)
            for pattern in demo_patterns
        ):
            kinds.add("demo")

        # Generic album-era labels such as "(Evolver Sessions)" describe
        # provenance/outtake context and are not automatically a different
        # recording. Branded platform sessions are distinct performances.
        session_patterns = (
            r"[\(\[][^)\]]*\b"
            r"(?:itunes|apple(?:\s+music)?|spotify)\s+"
            r"(?:home\s+)?sessions?\b[^)\]]*[\)\]]",
            r"\s[-:]\s*[^-:]*\b"
            r"(?:itunes|apple(?:\s+music)?|spotify)\s+"
            r"(?:home\s+)?sessions?\b.*$",
        )

        if any(
            re.search(pattern, value, flags=re.IGNORECASE)
            for pattern in session_patterns
        ):
            kinds.add("session")

        return kinds

    @staticmethod
    def _normalize_album(album: str) -> str:
        """Normalize an album title for fuzzy album comparison."""
        if not album:
            return ""

        value = str(album).casefold()
        value = value.replace("’", "'").replace("–", "-").replace("—", "-")

        # Remove common edition qualifiers while keeping the core album name.
        value = re.sub(
            r"[\(\[][^)\]]*"
            r"(?:remaster(?:ed)?|deluxe|expanded|anniversary|"
            r"bonus|special edition|collector'?s edition)"
            r"[^)\]]*[\)\]]",
            " ",
            value,
            flags=re.IGNORECASE,
        )

        value = re.sub(r"[^a-z0-9]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _album_types(album: str) -> set:
        """
        Classify release types we normally want to rank below a studio album.

        The patterns are intentionally conservative so an album whose actual
        title happens to contain a word like "live" is less likely to be
        penalized accidentally.
        """
        if not album:
            return set()

        value = str(album).casefold()
        kinds = set()

        compilation_patterns = (
            r"\bgreatest hits\b",
            r"\bbest of\b",
            r"\bthe essential\b",
            r"\bessential[s]?\b",
            r"\banthology\b",
            r"\bsingles collection\b",
            r"\bcomplete collection\b",
            r"\bhits collection\b",
            r"\bcollected\b",
        )

        live_patterns = (
            r"^live$",
            r"\blive at\b",
            r"\blive from\b",
            r"\blive in\b",
            r"\blive on\b",
            r"\blive album\b",
            r"\bunplugged\b",
            r"\bin concert\b",
            r"\bconcert recording\b",
        )

        remix_patterns = (
            r"\bremix(?:es)?\b",
            r"\bremixed\b",
            r"\bmixes\b",
        )

        acoustic_patterns = (
            r"\bacoustic\b",
            r"\bstripped\b",
        )

        demo_patterns = (
            r"\bdemo(?:s)?\b",
        )

        session_patterns = (
            r"\b(?:itunes|apple(?:\s+music)?|spotify)\s+"
            r"(?:home\s+)?sessions?\b",
        )

        deluxe_patterns = (
            r"\bdeluxe\b",
            r"\bexpanded\b",
            r"\banniversary\b",
            r"\bbonus track\b",
            r"\bspecial edition\b",
            r"\bcollector'?s edition\b",
        )

        remaster_patterns = (
            r"\bremaster(?:ed)?\b",
            r"\b\d{4} remaster\b",
        )

        if any(re.search(p, value) for p in compilation_patterns):
            kinds.add("compilation")
        if any(re.search(p, value) for p in live_patterns):
            kinds.add("live")
        if any(re.search(p, value) for p in remix_patterns):
            kinds.add("remix")
        if any(re.search(p, value) for p in acoustic_patterns):
            kinds.add("acoustic")
        if any(re.search(p, value) for p in demo_patterns):
            kinds.add("demo")
        if any(re.search(p, value) for p in session_patterns):
            kinds.add("session")
        if any(re.search(p, value) for p in deluxe_patterns):
            kinds.add("deluxe")
        if any(re.search(p, value) for p in remaster_patterns):
            kinds.add("remaster")

        return kinds

    @classmethod
    def score_candidate(
        cls,
        source_track: dict,
        plex_track: dict,
    ) -> dict:
        """
        Score one Plex candidate.

        Title/artist determine identity. Album information only changes the
        ranking among plausible copies of the same song.

        This is deliberate: a Greatest Hits copy can still be used when it is
        the only copy in Plex, but a studio-album copy should win when both
        exist.
        """
        source_title = str(source_track.get("title", ""))
        source_artist = str(source_track.get("artist", ""))
        source_album = str(source_track.get("album", "") or "")

        plex_title = str(plex_track.get("title", ""))
        plex_artist = str(plex_track.get("artist", ""))
        plex_album = str(plex_track.get("album", "") or "")

        title_score, raw_title_score = cls._title_score(
            source_title,
            plex_title,
        )

        artist_score = cls._artist_score(
            source_artist,
            plex_artist,
            source_title=source_title,
            plex_title=plex_title,
        )

        # Preserve the existing strong artist penalty.
        weighted_artist = artist_score
        if artist_score < 70:
            weighted_artist *= 0.3

        identity_score = (
            title_score * 0.65
            + weighted_artist * 0.35
        )

        album_score = None
        album_bonus = 0.0

        if source_album and plex_album:
            source_album_norm = cls._normalize_album(source_album)
            plex_album_norm = cls._normalize_album(plex_album)

            if source_album_norm and plex_album_norm:
                album_score = fuzz.token_set_ratio(
                    source_album_norm,
                    plex_album_norm,
                )

                # Reward the intended album only after title identity is
                # already plausible. This prevents a wrong song by the same
                # artist on the same album from outranking the correct title.
                if title_score >= 95:
                    if album_score >= 95:
                        album_bonus = 12
                    elif album_score >= 85:
                        album_bonus = 8
                    elif album_score >= 70:
                        album_bonus = 4

                elif title_score >= 85:
                    # A moderate title match may receive only a small nudge.
                    if album_score >= 95:
                        album_bonus = 4
                    elif album_score >= 85:
                        album_bonus = 2

        source_types = cls._album_types(source_album)
        plex_types = cls._album_types(plex_album)

        source_title_types = cls._title_release_types(
            source_title
        )
        plex_title_types = cls._title_release_types(
            plex_title
        )

        # Recording/version markers in the SOURCE TITLE are explicit intent.
        #
        # Example:
        #   Dracula (JENNIE Remix)
        #
        # In that case a Plex remix copy is correct and should not receive
        # the normal remix penalty. The same applies to an explicitly live
        # source title.
        requested_variant_types = (
            source_title_types
            & cls.VERSION_TYPES
        )

        candidate_variant_types = (
            plex_title_types
            | plex_types
        ) & cls.VERSION_TYPES

        # Canonical-copy preference still applies to release types the source
        # did NOT explicitly request in its title.
        unwanted_plex_types = (
            plex_types - requested_variant_types
        )

        album_penalty = sum(
            cls.ALBUM_TYPE_PENALTIES[kind]
            for kind in unwanted_plex_types
        )

        # A destination title can reveal an unwanted version even when the
        # album does not. Avoid double-penalizing a type already caught by
        # the album classification.
        unwanted_title_variant_types = (
            (plex_title_types & cls.VERSION_TYPES)
            - requested_variant_types
            - unwanted_plex_types
        )

        title_variant_penalty = sum(
            cls.ALBUM_TYPE_PENALTIES[kind]
            for kind in unwanted_title_variant_types
        )

        # If the source explicitly asks for a recording variant, title-level evidence
        # is stronger than album-level evidence:
        #
        #   candidate title says Remix/Live -> no intent penalty
        #   only candidate album says it    -> half penalty
        #   neither says it                 -> full penalty
        #
        # This keeps "Dracula (JENNIE remix)" above plain "Dracula" even when
        # both Plex tracks happen to live on the same remix album.
        release_intent_penalty = 0

        for kind in requested_variant_types:
            full_penalty = cls.ALBUM_TYPE_PENALTIES[kind]

            if kind in plex_title_types:
                continue

            if kind in plex_types:
                release_intent_penalty += max(
                    1,
                    full_penalty // 2,
                )
            else:
                release_intent_penalty += full_penalty

        # Do not allow an album bonus to erase a missing title-level recording variant
        # marker. A plain track on a remix/live album remains viable but ranks
        # below a candidate whose title explicitly matches the source intent.
        missing_title_intent = (
            requested_variant_types - plex_title_types
        )

        if (
            unwanted_plex_types
            or unwanted_title_variant_types
            or missing_title_intent
        ):
            album_bonus = 0.0

        adjusted_score = max(
            0.0,
            min(
                100.0,
                identity_score
                + album_bonus
                - album_penalty
                - title_variant_penalty
                - release_intent_penalty,
            ),
        )

        return {
            "adjusted_score": adjusted_score,
            "identity_score": identity_score,
            "title_score": title_score,
            "raw_title_score": raw_title_score,
            "artist_score": artist_score,
            "album_score": album_score,
            "album_bonus": album_bonus,
            "album_penalty": album_penalty,
            "title_variant_penalty": title_variant_penalty,
            "release_intent_penalty": release_intent_penalty,
            "source_album_types": source_types,
            "plex_album_types": plex_types,
            "source_title_release_types": source_title_types,
            "plex_title_release_types": plex_title_types,
            "requested_variant_types": requested_variant_types,
            "candidate_variant_types": candidate_variant_types,
            "candidate_title_variant_types": (
                plex_title_types & cls.VERSION_TYPES
            ),
            "candidate_album_variant_types": (
                plex_types & cls.VERSION_TYPES
            ),
        }

    @classmethod
    def match_track(
        cls,
        source_track: dict,
        plex_library: List[dict],
        mapping_cache: dict = None,
    ) -> Optional[str]:
        """Match source track to Plex while preferring canonical album copies."""

        if mapping_cache is None:
            mapping_cache = {}

        search_key = (
            f"{source_track['title']}|{source_track['artist']}"
        )

        if search_key in mapping_cache:
            return mapping_cache[search_key]

        if not plex_library:
            return None

        scored = []

        for plex_track in plex_library:
            details = cls.score_candidate(
                source_track,
                plex_track,
            )
            scored.append(
                (details, plex_track)
            )

        if not scored:
            return None

        # First isolate strong title+artist identities. This prevents a
        # mediocre studio-album candidate from beating an exact song match
        # merely because the exact copy is on a compilation.
        strong_identity = [
            item
            for item in scored
            if (
                item[0]["title_score"] >= 95
                and item[0]["artist_score"] >= 85
            )
        ]

        candidate_pool = strong_identity or scored

        best_details, best_track = max(
            candidate_pool,
            key=lambda item: (
                item[0]["adjusted_score"],
                item[0]["identity_score"],
                item[0]["title_score"],
                item[0]["raw_title_score"],
            ),
        )

        # Automatic matching has two confidence paths:
        #
        # 1) Strong title/artist identity (original behavior).
        # 2) A near-exact normalized title with a strong final score.
        #
        # The second path keeps initial sync consistent with the score shown
        # in Option 5 when source-service artist credits differ, while the
        # strict title/artist gates prevent album metadata from rescuing a
        # clearly different song.
        missing_requested_variant_types = (
            best_details["requested_variant_types"]
            - best_details["candidate_variant_types"]
        )

        strong_identity_match = (
            best_details["identity_score"] >= cls.MATCH_THRESHOLD
            and best_details["title_score"] >= 75
            and not missing_requested_variant_types
        )

        strong_adjusted_match = (
            best_details["adjusted_score"] >= cls.MATCH_THRESHOLD
            and best_details["title_score"] >= 95
            and best_details["artist_score"] >= 70
            and not missing_requested_variant_types
        )

        if strong_identity_match or strong_adjusted_match:
            return best_track["plex_id"]

        return None

    @classmethod
    def candidate_score(
        cls,
        source_track: dict,
        plex_track: dict,
    ) -> int:
        """Convenience score for interactive candidate lists."""
        details = cls.score_candidate(
            source_track,
            plex_track,
        )
        return int(round(details["adjusted_score"]))

    @staticmethod
    def interactive_match(
        source_track: dict, candidates: List[dict]
    ) -> Optional[str]:
        """Interactive manual matching."""

        print(
            f"\nMatching: {source_track['title']} - "
            f"{source_track['artist']} {source_album_display(source_track)}"
        )
        for i, cand in enumerate(candidates[:5], 1):
            cand_album = cand.get("album", "")
            album_str = (
                f" ({cand_album})"
                if cand_album
                else ""
            )
            print(
                f"  [{i}] {cand['title']} - "
                f"{cand['artist']}{album_str}"
            )

        print("  [s] Skip this track")

        choice = input("Select: ").strip().lower()

        if choice == "s":
            return None

        try:
            idx = int(choice) - 1

            if 0 <= idx < len(candidates):
                return candidates[idx]["plex_id"]

        except ValueError:
            pass

        return None


class Syncer:
    """Main sync orchestration"""

    def __init__(self, config: Config):
        self.config = config
        self.plex = None

    def _get_match_metadata_bucket(
        self,
        mapping_key: str,
        create: bool = True,
    ) -> dict:
        """Return per-track provenance metadata for a playlist."""
        if create:
            return self.config.match_metadata.setdefault(
                mapping_key,
                {},
            )

        value = self.config.match_metadata.get(
            mapping_key,
            {},
        )
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _plex_match_snapshot(
        plex_track: dict,
        plex_id: str = None,
    ) -> dict:
        """Return the small Plex metadata snapshot used for LOST history."""
        if not isinstance(plex_track, dict):
            return {
                "plex_id": str(plex_id or ""),
                "title": "",
                "artist": "",
                "album": "",
            }

        return {
            "plex_id": str(
                plex_track.get("plex_id")
                or plex_id
                or ""
            ),
            "title": repair_text(
                plex_track.get("title", "")
            ),
            "artist": repair_text(
                plex_track.get("artist", "")
            ),
            "album": repair_text(
                plex_track.get("album", "")
            ),
        }

    def _remember_match_snapshot(
        self,
        mapping_key: str,
        search_key: str,
        plex_track: dict,
        plex_id: str = None,
    ):
        """
        Remember the last known Plex title/artist/album for a saved mapping.

        If the mapping predates provenance tracking, this enriches the legacy
        record without guessing whether it was automatic or manual.
        """
        bucket = self._get_match_metadata_bucket(
            mapping_key,
            create=True,
        )
        current = bucket.get(
            search_key,
            {},
        )

        if not isinstance(current, dict):
            current = {}

        current = dict(current)
        current["matched_track"] = (
            self._plex_match_snapshot(
                plex_track,
                plex_id,
            )
        )
        current["updated_at"] = (
            datetime.now().isoformat()
        )
        bucket[search_key] = current

    def _previous_match_snapshot(
        self,
        mapping_key: str,
        search_key: str,
        plex_id: str,
    ) -> dict:
        """Return the last known Plex metadata for a mapping that went stale."""
        record = self._get_match_metadata_bucket(
            mapping_key,
            create=False,
        ).get(search_key)

        if isinstance(record, dict):
            previous = record.get(
                "matched_track"
            )

            if isinstance(previous, dict):
                snapshot = {
                    "plex_id": str(
                        previous.get("plex_id")
                        or plex_id
                        or ""
                    ),
                    "title": repair_text(
                        previous.get("title", "")
                    ),
                    "artist": repair_text(
                        previous.get("artist", "")
                    ),
                    "album": repair_text(
                        previous.get("album", "")
                    ),
                }

                return snapshot

        # Existing 1.2 mappings do not yet have the last-known metadata
        # snapshot. Keep the old Plex ID so the LOST record still has a
        # concrete reference and can explain why details are unavailable.
        return {
            "plex_id": str(plex_id or ""),
            "title": "",
            "artist": "",
            "album": "",
        }

    def _set_match_provenance(
        self,
        mapping_key: str,
        search_key: str,
        provenance: str,
        matched_track: dict = None,
        plex_id: str = None,
    ):
        """Record mapping provenance and, when known, the Plex match snapshot."""
        bucket = self._get_match_metadata_bucket(
            mapping_key,
            create=True,
        )
        current = bucket.get(
            search_key,
            {},
        )

        if not isinstance(current, dict):
            current = {}

        current = dict(current)
        current["provenance"] = provenance
        current["updated_at"] = (
            datetime.now().isoformat()
        )

        if matched_track is not None:
            current["matched_track"] = (
                self._plex_match_snapshot(
                    matched_track,
                    plex_id,
                )
            )

        bucket[search_key] = current

    def _remove_match_provenance(
        self,
        mapping_key: str,
        search_key: str,
    ):
        """Remove provenance associated with one saved mapping."""
        bucket = self._get_match_metadata_bucket(
            mapping_key,
            create=False,
        )
        bucket.pop(search_key, None)

        if not bucket:
            self.config.match_metadata.pop(
                mapping_key,
                None,
            )

    def _get_match_provenance(
        self,
        mapping_key: str,
        search_key: str,
    ) -> str:
        """Return automatic/manual/legacy for a saved mapping."""
        record = self._get_match_metadata_bucket(
            mapping_key,
            create=False,
        ).get(search_key)

        if isinstance(record, dict):
            value = str(
                record.get("provenance", "")
            ).strip().lower()
            if value in ("automatic", "manual"):
                return value

        return "legacy"

    def _match_provenance_counts(
        self,
        mapping_key: str,
    ) -> dict:
        """Count automatic/manual/legacy mappings for one playlist."""
        mapping = self.config.mapping.get(
            mapping_key,
            {},
        )
        counts = {
            "automatic": 0,
            "manual": 0,
            "legacy": 0,
        }

        for search_key in mapping:
            provenance = self._get_match_provenance(
                mapping_key,
                search_key,
            )
            counts[provenance] += 1

        return counts

    @staticmethod
    def _source_track_snapshot_key(track: dict) -> str:
        """Return a stable source-track identity for sync-to-sync changes."""
        source_id = str(
            track.get("source_id", "") or ""
        ).strip()

        if source_id:
            return f"id:{source_id}"

        title = Matcher._normalize_match_text(
            track.get("title", "")
        )
        artist = Matcher._normalize_match_text(
            track.get("artist", "")
        )
        return f"meta:{title}|{artist}"

    @classmethod
    def _snapshot_entries(
        cls,
        tracks: List[dict],
    ) -> List[dict]:
        """Convert current source tracks to lightweight persistent entries."""
        entries = []

        for track in tracks:
            entries.append(
                {
                    "key": cls._source_track_snapshot_key(
                        track
                    ),
                    "source_id": str(
                        track.get("source_id", "") or ""
                    ),
                    "title": repair_text(
                        track.get("title", "")
                    ),
                    "artist": repair_text(
                        track.get("artist", "")
                    ),
                    "album": repair_text(
                        track.get("album", "")
                    ),
                }
            )

        return entries

    def _source_change_report(
        self,
        mapping_key: str,
        tracks: List[dict],
    ) -> dict:
        """
        Compare current source contents to the last successful snapshot.

        Counts duplicate occurrences correctly. On the first tracked sync,
        establish a baseline rather than labeling every track as ADDED.
        """
        current_entries = self._snapshot_entries(
            tracks
        )
        previous_entries = self.config.source_snapshots.get(
            mapping_key
        )

        if not isinstance(previous_entries, list):
            return {
                "baseline": True,
                "current_entries": current_entries,
                "added": [],
                "removed": [],
                "added_indices": set(),
            }

        previous_counts = Counter(
            str(entry.get("key", ""))
            for entry in previous_entries
        )
        current_counts = Counter(
            str(entry.get("key", ""))
            for entry in current_entries
        )

        added = []
        added_indices = set()
        seen_current = Counter()

        for index, entry in enumerate(
            current_entries
        ):
            key = str(entry.get("key", ""))
            seen_current[key] += 1

            if seen_current[key] > previous_counts[key]:
                added.append(entry)
                added_indices.add(index)

        removed = []
        seen_previous = Counter()

        for entry in previous_entries:
            key = str(entry.get("key", ""))
            seen_previous[key] += 1

            if seen_previous[key] > current_counts[key]:
                removed.append(entry)

        return {
            "baseline": False,
            "current_entries": current_entries,
            "added": added,
            "removed": removed,
            "added_indices": added_indices,
        }

    def _save_source_snapshot(
        self,
        mapping_key: str,
        tracks: List[dict],
    ):
        """Persist the latest source contents after a real sync."""
        self.config.source_snapshots[
            mapping_key
        ] = self._snapshot_entries(tracks)

    @staticmethod
    def _print_source_changes(change_report: dict):
        """Display source playlist additions/removals before matching."""
        if change_report.get("baseline"):
            print(
                "  Source change tracking: "
                "baseline will be created after this sync"
            )
            return

        added = change_report.get("added", [])
        removed = change_report.get(
            "removed",
            [],
        )

        if not added and not removed:
            print(
                "  Source changes since last sync: none"
            )
            return

        print("\nSource playlist changes:")

        for track in added:
            print(
                f"  ADDED   {track.get('title', '')} - "
                f"{track.get('artist', '')} "
                f"{source_album_display(track)}"
            )

        for track in removed:
            print(
                f"  REMOVED {track.get('title', '')} - "
                f"{track.get('artist', '')} "
                f"{source_album_display(track)}"
            )

    def _get_plex(self):
        """Get Plex instance, initialize if needed."""

        if self.plex is None:
            plex_cfg = self.config.get_plex()
            self.plex = PlexAPI(
                plex_cfg["url"],
                plex_cfg["token"],
            )

        return self.plex

    def _match_source_tracks(
        self,
        source_tracks: List[dict],
        mapping_key: str,
        plex_library: List[dict] = None,
        source_added_indices: set = None,
        record_provenance: bool = True,
        mark_new_matches: bool = True,
    ) -> Tuple[
        List[str],
        List[dict],
        dict,
        Optional[List[dict]],
        dict,
    ]:
        """
        Match source tracks against Plex.

        Returns:
            matched Plex IDs in source order,
            unmatched source tracks,
            updated playlist mapping,
            Plex library for reuse,
            match-change statistics.

        Cached/manual mappings are always respected when their Plex ID still
        exists. If a cached Plex ID disappeared, Playlist Bridge attempts a
        fresh automatic match; if that also fails, the track is marked LOST.
        """
        plex = self._get_plex()
        source_added_indices = (
            source_added_indices or set()
        )

        original_mapping = dict(
            self.config.mapping.get(
                mapping_key,
                {},
            )
        )
        playlist_mapping = dict(
            original_mapping
        )

        if plex_library is None:
            print("→ Scanning Plex library...")
            plex_library = plex.search_library("")

            if not plex_library:
                print("✗ No Plex music tracks were found.")
                return (
                    [],
                    source_tracks,
                    playlist_mapping,
                    plex_library,
                    {
                        "new_matches": [],
                        "lost_matches": [],
                        "stale_mappings": [],
                    },
                )

            print(
                f"  Found {len(plex_library)} tracks in Plex library"
            )

        plex_by_id = {
            str(track.get("plex_id")): track
            for track in plex_library
            if track.get("plex_id") is not None
        }

        print("→ Matching tracks...")

        matched_tracks = []
        unmatched = []
        new_matches = []
        lost_matches = []
        stale_mappings = []

        for i, track in enumerate(
            source_tracks,
            1,
        ):
            search_key = (
                f"{track['title']}|{track['artist']}"
            )
            was_mapped = search_key in original_mapping
            source_added = (
                i - 1
            ) in source_added_indices

            matched_track = None
            plex_id = None
            cached_valid = False
            stale_cached_mapping = False
            stale_provenance = "legacy"
            previous_match = {
                "plex_id": "",
                "title": "",
                "artist": "",
                "album": "",
            }
            allow_automatic_match = True

            if search_key in playlist_mapping:
                cached_id = str(
                    playlist_mapping[search_key]
                )
                matched_track = plex_by_id.get(
                    cached_id
                )

                if matched_track is not None:
                    plex_id = cached_id
                    cached_valid = True

                    if record_provenance:
                        self._remember_match_snapshot(
                            mapping_key,
                            search_key,
                            matched_track,
                            cached_id,
                        )
                else:
                    stale_cached_mapping = True

                    stale_provenance = (
                        self._get_match_provenance(
                            mapping_key,
                            search_key,
                        )
                    )
                    previous_match = (
                        self._previous_match_snapshot(
                            mapping_key,
                            search_key,
                            cached_id,
                        )
                    )
                    stale_mappings.append(
                        {
                            "source": dict(track),
                            "previous_match": previous_match,
                            "previous_provenance": stale_provenance,
                        }
                    )

                    # A stale mapping that was explicitly manual -- or a
                    # legacy mapping whose origin cannot be known -- should
                    # never be silently replaced by a fresh automatic choice.
                    # Surface it as LOST for human review instead.
                    if stale_provenance in (
                        "manual",
                        "legacy",
                    ):
                        allow_automatic_match = False

                    playlist_mapping.pop(
                        search_key,
                        None,
                    )

                    if record_provenance:
                        self._remove_match_provenance(
                            mapping_key,
                            search_key,
                        )

            if (
                not cached_valid
                and allow_automatic_match
            ):
                plex_id = Matcher.match_track(
                    track,
                    plex_library,
                    playlist_mapping,
                )

                if plex_id:
                    plex_id = str(plex_id)
                    playlist_mapping[
                        search_key
                    ] = plex_id
                    matched_track = plex_by_id.get(
                        plex_id
                    )

                    if record_provenance:
                        self._set_match_provenance(
                            mapping_key,
                            search_key,
                            "automatic",
                            matched_track=matched_track,
                            plex_id=plex_id,
                        )

            if plex_id:
                matched_tracks.append(
                    str(plex_id)
                )

                is_new_match = (
                    mark_new_matches
                    and not was_mapped
                )

                if is_new_match:
                    new_matches.append(track)

                status_bits = []

                if is_new_match:
                    status_bits.append(
                        colored("NEW", Colors.MAGENTA)
                    )

                if source_added:
                    status_bits.append(
                        colored("ADDED", Colors.BLUE)
                    )

                matched_info = ""

                if matched_track:
                    album = matched_track.get(
                        "album",
                        "",
                    )
                    matched_title = colored(
                        matched_track["title"],
                        Colors.CYAN,
                    )
                    matched_artist = colored(
                        matched_track["artist"],
                        Colors.GREEN,
                    )

                    if album:
                        album_str = colored(
                            f"({album})",
                            Colors.YELLOW,
                        )
                        matched_info = (
                            f" → {matched_title} - "
                            f"{matched_artist} {album_str}"
                        )
                    else:
                        matched_info = (
                            f" → {matched_title} - "
                            f"{matched_artist}"
                        )

                source_title = colored(
                    track["title"],
                    Colors.CYAN,
                )
                source_artist = colored(
                    track["artist"],
                    Colors.GREEN,
                )
                status_text = (
                    " " + " ".join(status_bits)
                    if status_bits
                    else ""
                )

                print(
                    f"  [{i}/{len(source_tracks)}] "
                    f"{colored('✓', Colors.GREEN)}"
                    f"{status_text} "
                    f"{source_title} - {source_artist} "
                    f"{source_album_display(track)}"
                    f"{matched_info}"
                )
                continue

            unmatched_track = dict(track)

            is_lost = (
                was_mapped
                and stale_cached_mapping
            )

            if is_lost:
                previous_provenance = (
                    stale_provenance
                )

                unmatched_track["status"] = "lost"
                unmatched_track["previous_match"] = (
                    previous_match
                )
                unmatched_track[
                    "previous_provenance"
                ] = previous_provenance
                lost_matches.append(
                    unmatched_track
                )

            unmatched.append(
                unmatched_track
            )

            source_title = colored(
                track["title"],
                Colors.CYAN,
            )
            source_artist = colored(
                track["artist"],
                Colors.GREEN,
            )

            status_bits = []

            if is_lost:
                status_bits.append(
                    colored("LOST", Colors.RED)
                )

            if source_added:
                status_bits.append(
                    colored("ADDED", Colors.BLUE)
                )

            status_text = (
                " " + " ".join(status_bits)
                if status_bits
                else ""
            )

            print(
                f"  [{i}/{len(source_tracks)}] "
                f"{colored('✗', Colors.RED)}"
                f"{status_text} "
                f"{source_title} - {source_artist} "
                f"{source_album_display(track)}"
            )

            if is_lost:
                previous_title = (
                    previous_match.get(
                        "title",
                        "",
                    )
                )
                previous_artist = (
                    previous_match.get(
                        "artist",
                        "",
                    )
                )
                previous_album = (
                    previous_match.get(
                        "album",
                        "",
                    )
                )
                previous_id = (
                    previous_match.get(
                        "plex_id",
                        "",
                    )
                )

                if previous_title or previous_artist:
                    previous_text = (
                        f"{previous_title} - "
                        f"{previous_artist}"
                    )

                    if previous_album:
                        previous_text += (
                            f" ({previous_album})"
                        )

                    print(
                        "      Previous Plex match: "
                        f"{previous_text} "
                        f"[{previous_provenance}]"
                    )
                elif previous_id:
                    print(
                        "      Previous Plex match: "
                        f"metadata unavailable "
                        f"(Plex ID {previous_id}) "
                        f"[{previous_provenance}]"
                    )

        return (
            matched_tracks,
            unmatched,
            playlist_mapping,
            plex_library,
            {
                "new_matches": new_matches,
                "lost_matches": lost_matches,
                "stale_mappings": stale_mappings,
            },
        )

    def _store_unmatched(
        self,
        mapping_key: str,
        unmatched: List[dict],
    ):
        """Store unmatched tracks."""

        if unmatched:
            stored_tracks = []

            for t in unmatched:
                stored = {
                    "title": t["title"],
                    "artist": t["artist"],
                    "album": t.get("album", ""),
                    "source_id": t.get("source_id", ""),
                }

                if t.get("status") == "lost":
                    stored["status"] = "lost"
                    stored["previous_match"] = dict(
                        t.get(
                            "previous_match",
                            {},
                        )
                    )
                    stored["previous_provenance"] = (
                        t.get(
                            "previous_provenance",
                            "legacy",
                        )
                    )

                stored_tracks.append(
                    stored
                )

            self.config.missing[
                mapping_key
            ] = stored_tracks

            print(
                f"\n⚠ {len(unmatched)} tracks unmatched"
            )
        else:
            # Clear stale missing-track records.
            self.config.missing.pop(mapping_key, None)

    def _build_new_plex_playlist(
        self,
        playlist_name: str,
        description: str,
        matched_tracks: List[str],
        artwork_url: str = None,
    ) -> Optional[str]:
        """
        Create a Plex playlist and populate it in source order.

        The first matched track is supplied during playlist creation
        because Plex requires a media URI when creating a normal
        audio playlist.
        """

        if not matched_tracks:
            print(
                "✗ Cannot create Plex playlist: "
                "no tracks matched to the Plex library."
            )
            return None

        plex = self._get_plex()

        print(
            f"\n→ Creating Plex playlist with "
            f"first matched track..."
        )

        playlist_id = plex.create_playlist(
            playlist_name,
            matched_tracks[0],
            description,
        )

        if not playlist_id:
            print("✗ Failed to create Plex playlist.")
            return None

        print(
            f"✓ Created Plex playlist "
            f"'{playlist_name}' (ID: {playlist_id})"
        )

        # The first track was already inserted by create_playlist.
        added = 1

        for plex_id in matched_tracks[1:]:
            if plex.add_to_playlist(playlist_id, plex_id):
                added += 1

        print(
            f"✓ Added {added}/{len(matched_tracks)} "
            "matched tracks"
        )

        if added != len(matched_tracks):
            print(
                "⚠ Some matched tracks could not be added "
                "to the Plex playlist."
            )

        # Update artwork if available
        if artwork_url:
            plex.update_playlist_metadata(
                playlist_id,
                playlist_name,
                description,
                artwork_url,
            )

        return playlist_id

    def add_source(self, source_url: str):
        """Add a new source playlist."""

        source_url = Config._normalize_url_input(source_url)

        if "spotify.com" in source_url.lower() or source_url.lower().startswith("spotify:playlist:"):
            source_type = "spotify"
        elif ("music.apple.com" in source_url or 
              "itunes.apple.com" in source_url):
            source_type = "applemusic"
        else:
            print(
                "✗ Invalid URL. Must be Spotify or Apple Music"
            )
            return

        if self.config.find_playlist(source_url):
            print("✗ This playlist is already being synced")
            return

        # Make sure Plex credentials work before doing the work.
        try:
            plex = self._get_plex()
        except Exception as e:
            print(f"✗ Plex connection failed: {e}")
            return

        if source_type == "spotify":
            api = SpotifyAPI()
        else:
            api = AppleMusicAPI()

        playlist_id = Config._extract_id(
            source_url,
            source_type,
        )

        if not playlist_id:
            print("✗ Could not extract playlist ID from URL")
            return

        print(
            f"Fetching {source_display_name(source_type)} playlist "
            f"(ID: {playlist_id})..."
        )

        try:
            # Pass the full source URL. SpotifyAPI normalizes it to the
            # canonical playlist ID internally, so query parameters are safe.
            if source_type == "applemusic":
                tracks, metadata = api.get_playlist_tracks(
                    source_url,
                    fetch_artwork=True,
                )
            else:
                tracks, metadata = api.get_playlist_tracks(
                    source_url,
                    fetch_artwork=True,
                )
        except Exception as e:
            print(f"✗ Failed to fetch playlist: {e}")
            return

        playlist_name = metadata.get(
            "name",
            "Unknown Playlist",
        )

        print(
            f"✓ Found playlist: {playlist_name} "
            f"({len(tracks)} tracks)"
        )

        # Match BEFORE creating the Plex playlist.
        mapping_key = f"{source_type}:{playlist_id}"

        (
            matched_tracks,
            unmatched,
            playlist_mapping,
            plex_library,
            match_stats,
        ) = self._match_source_tracks(
            tracks,
            mapping_key,
            mark_new_matches=False,
        )

        self._store_unmatched(
            mapping_key,
            unmatched,
        )

        # Persist matches/missing state even if creation fails.
        self.config.mapping[mapping_key] = playlist_mapping
        self.config.save()

        print(
            f"\n✓ Matched {len(matched_tracks)}/{len(tracks)} "
            "tracks"
        )

        if not matched_tracks:
            print(
                "\n✗ No tracks could be matched, so Plex "
                "playlist was not created."
            )
            print(
                "  Add/match the missing tracks, then run "
                "Resolve Missing."
            )
            return

        plex_playlist_id = self._build_new_plex_playlist(
            playlist_name,
            metadata.get("description", ""),
            matched_tracks,
            metadata.get("image_url", ""),
        )

        if not plex_playlist_id:
            return

        playlist_entry = self.config.add_playlist(
            source_url,
            source_type,
            playlist_name,
            plex_playlist_id,
        )
        playlist_entry["last_synced"] = datetime.now().isoformat()
        self._save_source_snapshot(
            mapping_key,
            tracks,
        )
        self.config.save()

        print(
            f"\n✓ Playlist '{playlist_name}' added to Plex "
            "and configured for sync!"
        )

        print("\n=== SYNC SUMMARY ===")
        print(f"Source tracks:   {len(tracks)}")
        print(f"Matched:         {len(matched_tracks)}")
        print("New matches:     baseline")
        print("Lost matches:    0")
        print("Source ADDED:    baseline")
        print("Source REMOVED:  baseline")
        print(f"Unresolved:      {len(unmatched)}")

        if unmatched:
            print(
                f"⚠ {len(unmatched)} tracks still need "
                "resolution."
            )

    def sync_playlist(
        self,
        playlist_entry: dict,
        dry_run: bool = False,
    ):
        """
        Sync a specific playlist.

        When dry_run=True, Playlist Bridge performs source fetching, Plex
        library scanning, and matching only. It does not:
          - modify the Plex playlist;
          - update playlist metadata/artwork;
          - write config.json, mapping.json, or missing_tracks.json;
          - update last_synced.
        """

        source_type = playlist_entry["source"]
        source_url = Config._normalize_url_input(
            playlist_entry["source_url"]
        )
        playlist_id = Config._extract_id(
            source_url,
            source_type,
        )

        if not playlist_id:
            print(
                f"✗ Could not extract playlist ID from stored URL: "
                f"{source_url}"
            )
            return

        canonical_url = Config._canonical_source_url(
            source_url,
            source_type,
        )

        # Normal syncs continue to repair older stored config entries.
        # Dry runs intentionally keep all local state untouched.
        if not dry_run:
            changed = False
            old_source_id = playlist_entry.get("source_id")

            if old_source_id != playlist_id:
                old_mapping_key = (
                    f"{source_type}:{old_source_id}"
                    if old_source_id
                    else None
                )
                new_mapping_key = (
                    f"{source_type}:{playlist_id}"
                )

                if (
                    old_mapping_key
                    and old_mapping_key != new_mapping_key
                ):
                    if old_mapping_key in self.config.mapping:
                        existing = self.config.mapping.pop(
                            old_mapping_key
                        )
                        self.config.mapping.setdefault(
                            new_mapping_key,
                            {},
                        ).update(existing)

                    if old_mapping_key in self.config.missing:
                        existing_missing = (
                            self.config.missing.pop(
                                old_mapping_key
                            )
                        )

                        if new_mapping_key not in self.config.missing:
                            self.config.missing[
                                new_mapping_key
                            ] = existing_missing

                    if old_mapping_key in self.config.match_metadata:
                        existing_metadata = (
                            self.config.match_metadata.pop(
                                old_mapping_key
                            )
                        )
                        self.config.match_metadata.setdefault(
                            new_mapping_key,
                            {},
                        ).update(existing_metadata)

                    if old_mapping_key in self.config.source_snapshots:
                        existing_snapshot = (
                            self.config.source_snapshots.pop(
                                old_mapping_key
                            )
                        )
                        if new_mapping_key not in self.config.source_snapshots:
                            self.config.source_snapshots[
                                new_mapping_key
                            ] = existing_snapshot

                playlist_entry["source_id"] = playlist_id
                changed = True

            if playlist_entry.get("source_url") != canonical_url:
                playlist_entry["source_url"] = canonical_url
                changed = True

            if changed:
                self.config.save()

        source_url = canonical_url

        plex_playlist_id = playlist_entry[
            "plex_playlist_id"
        ]
        playlist_name = playlist_entry[
            "plex_playlist_name"
        ]

        if source_type == "spotify":
            api = SpotifyAPI()
        else:
            api = AppleMusicAPI()

        plex = self._get_plex()

        if dry_run:
            print(
                f"\n=== DRY RUN: '{playlist_name}' "
                f"({source_display_name(source_type)}) ==="
            )
        else:
            print(
                f"\n→ Syncing '{playlist_name}' from "
                f"{source_display_name(source_type)}..."
            )

        try:
            source_tracks, metadata = api.get_playlist_tracks(
                source_url,
                # Artwork is irrelevant during a dry run and can involve
                # additional network work.
                fetch_artwork=not dry_run,
            )
        except Exception as e:
            print(f"✗ Failed to fetch: {e}")
            return

        print(
            f"  Found {len(source_tracks)} tracks"
        )

        mapping_key = (
            f"{source_type}:{playlist_id}"
        )

        source_changes = self._source_change_report(
            mapping_key,
            source_tracks,
        )
        self._print_source_changes(
            source_changes
        )

        (
            matched_tracks,
            unmatched,
            playlist_mapping,
            plex_library,
            match_stats,
        ) = self._match_source_tracks(
            source_tracks,
            mapping_key,
            source_added_indices=source_changes[
                "added_indices"
            ],
            record_provenance=not dry_run,
            mark_new_matches=True,
        )

        if dry_run:
            print("\n=== DRY RUN SUMMARY ===")
            print(
                f"Source tracks: {len(source_tracks)}"
            )
            print(
                f"Would match:    {len(matched_tracks)}"
            )
            print(
                f"New matches:    {len(match_stats['new_matches'])}"
            )
            print(
                f"Lost matches:   {len(match_stats['lost_matches'])}"
            )

            if source_changes["baseline"]:
                print("Source ADDED:   baseline")
                print("Source REMOVED: baseline")
            else:
                print(
                    f"Source ADDED:   {len(source_changes['added'])}"
                )
                print(
                    f"Source REMOVED: {len(source_changes['removed'])}"
                )

            print(
                f"Unmatched:      {len(unmatched)}"
            )

            if unmatched:
                print("\nUnmatched tracks:")
                for track in unmatched:
                    print(
                        f"  ✗ {track['title']} - "
                        f"{track['artist']} "
                        f"{source_album_display(track)}"
                    )

            print(
                "\n✓ DRY RUN complete. "
                "No changes were made to Plex."
            )
            print(
                "  config.json, mapping.json, missing_tracks.json, "
                "match_metadata.json, source_snapshots.json, schema state, "
                "and last sync times were also left unchanged."
            )
            return

        self._store_unmatched(
            mapping_key,
            unmatched,
        )

        self.config.mapping[mapping_key] = (
            playlist_mapping
        )

        print("\n→ Syncing to Plex...")

        if matched_tracks:
            print(
                "  Clearing existing Plex playlist..."
            )

            if not plex.clear_playlist(
                plex_playlist_id
            ):
                print(
                    "⚠ Some existing playlist items could not "
                    "be removed."
                )
        else:
            print(
                "⚠ No matched tracks - "
                "Plex playlist left unchanged"
            )

        if matched_tracks:
            added = 0

            for plex_id in matched_tracks:
                if plex.add_to_playlist(
                    plex_playlist_id,
                    plex_id,
                ):
                    added += 1

            print(
                f"✓ Added {added}/{len(matched_tracks)} "
                "matched tracks"
            )

        plex.update_playlist_metadata(
            plex_playlist_id,
            metadata.get("name", ""),
            metadata.get("description", ""),
            metadata.get("image_url", ""),
        )

        image_url = metadata.get(
            "image_url",
            "",
        )

        if image_url:
            print(
                "  → Artwork URL found in source"
            )
        else:
            print(
                "  ⚠ No artwork URL found in source"
            )

        playlist_entry["last_synced"] = (
            datetime.now().isoformat()
        )
        self._save_source_snapshot(
            mapping_key,
            source_tracks,
        )

        self.config.save()

        if matched_tracks:
            print("✓ Sync complete!")
        else:
            print(
                "✓ Sync complete "
                "(no changes - no matched tracks)"
            )

        if unmatched:
            print(
                f"⚠ {len(unmatched)} tracks were not "
                "added because they are unmatched."
            )

        print("\n=== SYNC SUMMARY ===")
        print(f"Source tracks:   {len(source_tracks)}")
        print(f"Matched:         {len(matched_tracks)}")
        print(
            f"New matches:     {len(match_stats['new_matches'])}"
        )
        print(
            f"Lost matches:    {len(match_stats['lost_matches'])}"
        )

        if source_changes["baseline"]:
            print("Source ADDED:    baseline")
            print("Source REMOVED:  baseline")
        else:
            print(
                f"Source ADDED:    {len(source_changes['added'])}"
            )
            print(
                f"Source REMOVED:  {len(source_changes['removed'])}"
            )

        print(f"Unresolved:      {len(unmatched)}")



    def sync_all(
        self,
        dry_run: bool = False,
    ):
        """Sync all registered playlists, or preview them in dry-run mode."""

        if not self.config.config["playlists"]:
            print("✗ No playlists registered")
            return

        if dry_run:
            print(
                "\n=== PLAYLIST BRIDGE DRY RUN ==="
            )
            print(
                "Matching will be tested against Plex, "
                "but nothing will be changed or saved.\n"
            )

        for playlist in self.config.config["playlists"]:
            self.sync_playlist(
                playlist,
                dry_run=dry_run,
            )

    def developer_menu_interactive(self):
        """Development/testing tools. Only exposed when -devmode is active."""

        while True:
            print("\nDeveloper tools:\n")
            print("[1] Dry run matching")
            print("[2] Check manual source track")
            print("[3] Albums with no playlist tracks")
            print("[b] Back")
            print("[x] Exit")

            choice = input(
                "\nSelect: "
            ).strip().lower()

            if choice in ("", "b"):
                return

            if choice == "x":
                sys.exit(0)

            if choice == "1":
                self.dry_run_interactive()
                continue

            if choice == "2":
                self.manual_match_check_interactive()
                continue

            if choice == "3":
                self.show_albums_without_playlist_tracks()
                continue

            print("✗ Invalid choice")

    def find_albums_without_playlist_tracks(
        self,
    ) -> dict:
        """
        Find Plex albums with zero tracks on any Plex audio playlist.

        "Any playlist" means every Plex audio playlist visible to the current
        Plex server/token, not only playlists registered with Playlist Bridge.

        Returns diagnostic data so the interactive view can remain simple and
        the logic can be regression-tested independently.
        """

        plex = self._get_plex()

        print("\n→ Scanning Plex music library...")
        plex_library = plex.search_library("")

        if not plex_library:
            return {
                "albums": [],
                "playlist_count": 0,
                "playlist_track_count": 0,
                "library_track_count": 0,
                "library_album_count": 0,
            }

        print(
            f"  Found {len(plex_library)} tracks in Plex library"
        )

        print("→ Scanning Plex audio playlists...")
        playlists = plex.get_audio_playlists()

        playlist_track_ids = set()

        for i, playlist in enumerate(
            playlists,
            1,
        ):
            playlist_id = playlist.get(
                "plex_id"
            )
            playlist_name = (
                playlist.get("title")
                or f"Playlist {playlist_id}"
            )

            print(
                f"  [{i}/{len(playlists)}] "
                f"{playlist_name}"
            )

            items = plex.get_playlist_items(
                str(playlist_id)
            )

            for item in items:
                plex_id = item.get(
                    "plex_id"
                )

                if plex_id is not None:
                    playlist_track_ids.add(
                        str(plex_id)
                    )

        albums = {}

        for track in plex_library:
            album = repair_text(
                track.get("album", "")
            ).strip()

            # A track with no Plex album metadata is not useful in an
            # album-level report.
            if not album:
                continue

            album_artist = repair_text(
                track.get("album_artist", "")
                or track.get("artist", "")
            ).strip()

            key = (
                album_artist.casefold(),
                album.casefold(),
            )

            if key not in albums:
                albums[key] = {
                    "artist": album_artist,
                    "album": album,
                    "track_count": 0,
                    "playlist_track_count": 0,
                }

            entry = albums[key]
            entry["track_count"] += 1

            plex_id = track.get(
                "plex_id"
            )

            if (
                plex_id is not None
                and str(plex_id)
                in playlist_track_ids
            ):
                entry[
                    "playlist_track_count"
                ] += 1

        unused_albums = [
            album
            for album in albums.values()
            if album["playlist_track_count"] == 0
        ]

        unused_albums.sort(
            key=lambda item: (
                item["artist"].casefold(),
                item["album"].casefold(),
            )
        )

        return {
            "albums": unused_albums,
            "playlist_count": len(playlists),
            "playlist_track_count": len(
                playlist_track_ids
            ),
            "library_track_count": len(
                plex_library
            ),
            "library_album_count": len(
                albums
            ),
        }

    def show_albums_without_playlist_tracks(
        self,
    ):
        """
        Read-only developer report of albums unused by every Plex playlist.
        """

        print(
            "\nAlbums with no tracks on any Plex playlist"
        )
        print(
            "This checks every Plex audio playlist visible to "
            "the current server/token."
        )

        result = (
            self.find_albums_without_playlist_tracks()
        )

        if not result["library_track_count"]:
            print("✗ No Plex music tracks were found.")
            return

        albums = result["albums"]

        print(
            "\n=== UNUSED ALBUM SUMMARY ==="
        )
        print(
            f"Library tracks:          "
            f"{result['library_track_count']}"
        )
        print(
            f"Library albums:          "
            f"{result['library_album_count']}"
        )
        print(
            f"Audio playlists scanned: "
            f"{result['playlist_count']}"
        )
        print(
            f"Unique playlist tracks:  "
            f"{result['playlist_track_count']}"
        )
        print(
            f"Albums with zero tracks "
            f"on any playlist: {len(albums)}"
        )

        if not albums:
            print(
                "\n✓ Every Plex album has at least one track "
                "on a Plex audio playlist."
            )
            return

        print(
            "\nAlbums with zero playlist coverage:\n"
        )

        for i, album in enumerate(
            albums,
            1,
        ):
            artist = (
                album["artist"]
                or "Unknown Artist"
            )

            print(
                f"[{i}] "
                f"{colored(artist, Colors.GREEN)} - "
                f"{colored(album['album'], Colors.YELLOW)} "
                f"({album['track_count']} tracks)"
            )

        print(
            "\n✓ Developer report complete. "
            "No Plex or local state was changed."
        )

    def manual_match_check_interactive(self):
        """
        Test one manually entered source track against the Plex library.

        This is read-only. It does not create mappings, modify playlists,
        update last-sync timestamps, or save any local state.
        """

        print(
            "\nManual source-track match check"
        )
        print(
            "Enter source metadata exactly as you want Playlist Bridge "
            "to evaluate it."
        )
        print(
            "Album is optional. Type [b] at the title prompt to go back."
        )

        title = input(
            "\nSource title: "
        ).strip()

        if title.casefold() == "b" or not title:
            return

        artist = input(
            "Source artist: "
        ).strip()

        if not artist:
            print("✗ Artist is required")
            return

        album = input(
            "Source album (optional): "
        ).strip()

        source_track = {
            "title": repair_text(title),
            "artist": repair_text(artist),
            "album": repair_text(album),
        }

        plex = self._get_plex()

        print("\n→ Scanning Plex library...")
        plex_library = plex.search_library("")

        if not plex_library:
            print("✗ No Plex music tracks were found.")
            return

        print(
            f"  Found {len(plex_library)} tracks in Plex library"
        )

        scored = []

        for plex_track in plex_library:
            details = Matcher.score_candidate(
                source_track,
                plex_track,
            )
            scored.append(
                (details, plex_track)
            )

        # Match the real automatic-selection behavior: if strong title/artist
        # identities exist, only those compete for the automatic winner.
        strong_identity = [
            item
            for item in scored
            if (
                item[0]["title_score"] >= 95
                and item[0]["artist_score"] >= 85
            )
        ]

        candidate_pool = strong_identity or scored

        candidate_pool.sort(
            key=lambda item: (
                item[0]["adjusted_score"],
                item[0]["identity_score"],
                item[0]["title_score"],
                item[0]["raw_title_score"],
            ),
            reverse=True,
        )

        auto_plex_id = Matcher.match_track(
            source_track,
            plex_library,
            {},
        )

        print(
            f"\nSource: "
            f"{colored(source_track['title'], Colors.CYAN)} - "
            f"{colored(source_track['artist'], Colors.GREEN)} "
            f"{source_album_display(source_track)}"
        )

        if auto_plex_id is None:
            print("\nAutomatic result: UNMATCHED")
        else:
            auto_track = next(
                (
                    track
                    for track in plex_library
                    if str(track.get("plex_id")) == str(auto_plex_id)
                ),
                None,
            )

            if auto_track:
                auto_album = auto_track.get("album", "")
                auto_album_text = (
                    f" ({auto_album})"
                    if auto_album
                    else ""
                )
                print(
                    "\nAutomatic result: "
                    f"{auto_track.get('title', '')} - "
                    f"{auto_track.get('artist', '')}"
                    f"{auto_album_text}"
                )
            else:
                print(
                    f"\nAutomatic result: Plex ID {auto_plex_id}"
                )

        print(
            "\nTop matcher candidates "
            f"({'strong-identity pool' if strong_identity else 'full library'}):\n"
        )

        displayed = candidate_pool[:10]

        for i, (details, candidate) in enumerate(
            displayed,
            1,
        ):
            candidate_album = candidate.get(
                "album",
                "",
            )
            album_text = (
                f" ({candidate_album})"
                if candidate_album
                else ""
            )

            marker = (
                " [AUTO]"
                if (
                    auto_plex_id is not None
                    and str(candidate.get("plex_id")) == str(auto_plex_id)
                )
                else ""
            )

            print(
                f"[{i}] "
                f"{candidate.get('title', '')} - "
                f"{candidate.get('artist', '')}"
                f"{album_text}"
                f"{marker}"
            )

            album_score = details["album_score"]
            album_score_text = (
                "N/A"
                if album_score is None
                else str(album_score)
            )

            print(
                "    "
                f"adjusted={details['adjusted_score']:.1f}% | "
                f"identity={details['identity_score']:.1f}% | "
                f"title={details['title_score']}% | "
                f"artist={details['artist_score']}% | "
                f"album={album_score_text}%"
            )

            effects = []

            if details["album_bonus"]:
                effects.append(
                    f"+{details['album_bonus']:.0f} album bonus"
                )

            if details["album_penalty"]:
                effects.append(
                    f"-{details['album_penalty']} album penalty"
                )

            if details["title_variant_penalty"]:
                effects.append(
                    f"-{details['title_variant_penalty']} title-version penalty"
                )

            if details["release_intent_penalty"]:
                effects.append(
                    f"-{details['release_intent_penalty']} "
                    "missing-version penalty"
                )

            missing_variants = (
                details["requested_variant_types"]
                - details["candidate_variant_types"]
            )

            if missing_variants:
                effects.append(
                    "missing requested "
                    + ", ".join(
                        sorted(missing_variants)
                    )
                )

            if effects:
                print(
                    "    "
                    + " | ".join(effects)
                )

        print(
            "\n✓ Match check complete. "
            "No Plex or local state was changed."
        )

    def dry_run_interactive(self):
        """Run matching without changing Plex or local matching state."""

        playlists = sorted(
            self.config.config.get(
                "playlists",
                [],
            ),
            key=lambda p: oldest_timestamp_sort_key(
                p,
                "last_synced",
            ),
        )

        if not playlists:
            print("✗ No playlists registered")
            return

        print("\nDry run matching:\n")

        for i, playlist in enumerate(
            playlists,
            1,
        ):
            print(
                f"[{i}] "
                f"{playlist['plex_playlist_name']} "
                f"({source_display_name(playlist['source'])}) "
                f"- Last sync: "
                f"{format_timestamp(playlist.get('last_synced'))}"
            )

        print("[a] All playlists")
        print("[b] Back")
        print("[x] Exit")

        choice = input(
            "\nSelect: "
        ).strip().lower()

        if choice in ("", "b"):
            return

        if choice == "x":
            sys.exit(0)

        if choice == "a":
            self.sync_all(
                dry_run=True,
            )
            return

        try:
            idx = int(choice) - 1
        except ValueError:
            print("✗ Invalid choice")
            return

        if not (0 <= idx < len(playlists)):
            print("✗ Invalid choice")
            return

        self.sync_playlist(
            playlists[idx],
            dry_run=True,
        )

    def edit_playlist_matches(self):
        """Edit existing matches for a playlist."""

        playlists = self.config.config["playlists"]

        if not playlists:
            print("✗ No playlists registered")
            return

        while True:
            print("\nSelect playlist to edit matches:\n")

            for i, p in enumerate(
                playlists,
                1,
            ):
                mapping_key = (
                    f"{p['source']}:{p['source_id']}"
                )
                match_count = len(
                    self.config.mapping.get(
                        mapping_key,
                        {},
                    )
                )
                provenance = (
                    self._match_provenance_counts(
                        mapping_key
                    )
                )

                print(
                    f"[{i}] {p['plex_playlist_name']} "
                    f"({source_display_name(p['source'])}) "
                    f"- {match_count} current matches "
                    f"({provenance['automatic']} auto, "
                    f"{provenance['manual']} manual, "
                    f"{provenance['legacy']} legacy)"
                )

            print("[b] Back")
            print("[x] Exit")

            choice = input(
                "\nSelect: "
            ).strip().lower()

            if choice in ("", "b"):
                return

            if choice == "x":
                sys.exit(0)

            try:
                idx = int(choice) - 1

                if 0 <= idx < len(playlists):
                    self._edit_playlist_matches_interactive(
                        playlists[idx]
                    )
                    continue

            except ValueError:
                pass

            print("✗ Invalid choice")

    def _edit_playlist_matches_interactive(
        self,
        playlist: dict,
    ):
        """Interactively edit saved matches for a playlist."""

        source_type = playlist["source"]
        source_url = Config._normalize_url_input(
            playlist["source_url"]
        )
        playlist_id = Config._extract_id(
            source_url,
            source_type,
        )

        if not playlist_id:
            print(
                f"✗ Could not extract playlist ID from: "
                f"{source_url}"
            )
            return

        mapping_key = f"{source_type}:{playlist_id}"

        api = (
            SpotifyAPI()
            if source_type == "spotify"
            else AppleMusicAPI()
        )

        print(
            f"\n→ Fetching "
            f"{source_display_name(source_type)} playlist..."
        )

        try:
            # Match editing does not need playlist artwork.
            if source_type == "applemusic":
                source_tracks, _ = api.get_playlist_tracks(
                    source_url,
                    fetch_artwork=False,
                )
            else:
                source_tracks, _ = api.get_playlist_tracks(
                    playlist_id,
                    fetch_artwork=False,
                )
        except Exception as e:
            print(f"✗ Failed to fetch: {e}")
            return

        plex = self._get_plex()
        plex_library = plex.search_library("")

        playlist_mapping = self.config.mapping.get(
            mapping_key,
            {},
        )

        print(f"\nFound {len(source_tracks)} tracks.\n")

        changes_made = False

        while True:
            matches_to_review = []

            for track in source_tracks:
                search_key = (
                    f"{track['title']}|{track['artist']}"
                )

                if search_key not in playlist_mapping:
                    continue

                plex_id = playlist_mapping[search_key]
                matched_track = next(
                    (
                        t
                        for t in plex_library
                        if t["plex_id"] == plex_id
                    ),
                    None,
                )

                if matched_track:
                    matches_to_review.append(
                        {
                            "source": track,
                            "matched": matched_track,
                            "plex_id": plex_id,
                            "search_key": search_key,
                        }
                    )

            if not matches_to_review:
                print("✗ No existing matches to edit")
                if changes_made:
                    self._prompt_sync_after_match_edits(
                        playlist
                    )
                return

            print(
                f"Showing all "
                f"{len(matches_to_review)} matches:\n"
            )

            for i, match in enumerate(
                matches_to_review,
                1,
            ):
                src = match["source"]
                matched = match["matched"]
                album = matched.get("album", "")
                album_str = (
                    f" {colored(f'({album})', Colors.YELLOW)}"
                    if album
                    else ""
                )

                src_title = colored(
                    src["title"],
                    Colors.CYAN,
                )
                src_artist = colored(
                    src["artist"],
                    Colors.GREEN,
                )
                matched_title = colored(
                    matched["title"],
                    Colors.CYAN,
                )
                matched_artist = colored(
                    matched["artist"],
                    Colors.GREEN,
                )

                print(
                    f"[{i}] {src_title} - "
                    f"{src_artist} "
                    f"{source_album_display(src)}"
                )
                provenance = self._get_match_provenance(
                    mapping_key,
                    match["search_key"],
                )

                print(
                    f"    → {matched_title} - "
                    f"{matched_artist}{album_str} "
                    f"[{provenance}]"
                )

            print("\n[b] Back")
            print("[x] Exit")

            choice = input(
                "\nEnter track number to fix: "
            ).strip().lower()

            if choice in ("", "b"):
                if changes_made:
                    self._prompt_sync_after_match_edits(
                        playlist
                    )
                return

            if choice == "x":
                if changes_made:
                    self._prompt_sync_after_match_edits(
                        playlist
                    )
                sys.exit(0)

            try:
                idx = int(choice) - 1

                if 0 <= idx < len(matches_to_review):
                    changed, exit_requested = self._fix_single_match(
                        matches_to_review[idx],
                        plex_library,
                        playlist_mapping,
                        mapping_key,
                    )

                    if changed:
                        changes_made = True

                    if exit_requested:
                        if changes_made:
                            self._prompt_sync_after_match_edits(
                                playlist
                            )
                        sys.exit(0)

                    continue

            except ValueError:
                pass

            print("✗ Invalid choice")

    def _prompt_sync_after_match_edits(
        self,
        playlist: dict,
    ):
        """Offer one full playlist sync after Option 6 edits."""

        sync_now = input(
            "\nSync this playlist to Plex now? (y/n): "
        ).strip().lower()

        if sync_now in ("y", "yes"):
            print(
                f"\n→ Syncing "
                f"'{playlist['plex_playlist_name']}' "
                "to Plex..."
            )
            self.sync_playlist(playlist)
        else:
            print(
                "✓ Match changes saved. "
                "Plex playlist was not synced."
            )

    def _fix_single_match(
        self,
        current_match: dict,
        plex_library: List[dict],
        playlist_mapping: dict,
        mapping_key: str,
    ) -> Tuple[bool, bool]:
        """
        Fix one saved match.

        Returns (changed, exit_requested). Plex itself is not modified here;
        Option 6 offers one full sync when editing is done.
        """

        src = current_match["source"]
        src_title = colored(src["title"], Colors.CYAN)
        src_artist = colored(src["artist"], Colors.GREEN)
        print(
            f"\n→ Fixing: {src_title} - {src_artist} "
            f"{source_album_display(src)}"
        )

        current = current_match["matched"]
        current_album = current.get("album", "")
        current_title = colored(current["title"], Colors.CYAN)
        current_artist = colored(current["artist"], Colors.GREEN)
        current_display = f"{current_title} - {current_artist}"
        if current_album:
            current_display += (
                f" {colored(f'({current_album})', Colors.YELLOW)}"
            )

        print(f"  Current match: {current_display}")

        candidates = []

        for plex_track in plex_library:
            score = Matcher.candidate_score(
                src,
                plex_track,
            )

            if score >= Matcher.MIN_DISPLAY_SCORE:
                candidates.append((score, plex_track))

        candidates.sort(key=lambda x: x[0], reverse=True)
        displayed_candidates = candidates[:10]

        print("\nTop Plex candidates:\n")

        for i, (score, cand) in enumerate(
            displayed_candidates,
            1,
        ):
            marker = (
                "→ "
                if cand["plex_id"] == current_match["plex_id"]
                else "  "
            )
            album = cand.get("album", "")
            cand_title = colored(cand["title"], Colors.CYAN)
            cand_artist = colored(cand["artist"], Colors.GREEN)
            album_str = (
                f" {colored(f'({album})', Colors.YELLOW)}"
                if album
                else ""
            )

            details = Matcher.score_candidate(src, cand)

            penalty_note = ""
            if details["album_penalty"]:
                kinds = ", ".join(
                    sorted(
                        details["plex_album_types"]
                        - details["requested_variant_types"]
                    )
                )
                penalty_note = (
                    f" [-{details['album_penalty']} {kinds}]"
                )

            title_variant_note = ""
            if details["title_variant_penalty"]:
                kinds = ", ".join(
                    sorted(
                        (
                            details["plex_title_release_types"]
                            & Matcher.VERSION_TYPES
                        )
                        - details["requested_variant_types"]
                    )
                )
                title_variant_note = (
                    f" [-{details['title_variant_penalty']} "
                    f"{kinds} title]"
                )

            intent_note = ""
            if details["release_intent_penalty"]:
                missing = ", ".join(
                    sorted(
                        details["requested_variant_types"]
                        - details["candidate_variant_types"]
                    )
                )
                intent_note = (
                    f" [-{details['release_intent_penalty']} "
                    f"title missing {missing}]"
                )

            print(
                f"{marker}[{i}] {cand_title} - "
                f"{cand_artist}{album_str} ({score}%)"
                f"{penalty_note}{title_variant_note}{intent_note}"
            )

        print("\n[s] Skip")
        print("[d] Unlink this match")
        print("[b] Back")
        print("[x] Exit")

        choice = input(
            "\nSelect correct match: "
        ).strip().lower()

        if choice in ("", "b"):
            return False, False
        if choice == "x":
            return False, True
        if choice == "s":
            return False, False

        if choice == "d":
            if current_match["search_key"] in playlist_mapping:
                del playlist_mapping[current_match["search_key"]]
                self._remove_match_provenance(
                    mapping_key,
                    current_match["search_key"],
                )
                self.config.mapping[mapping_key] = playlist_mapping
                self.config.save()
                print(
                    f"✓ Unlinked: {src_title} - {src_artist}"
                )
                return True, False
            return False, False

        try:
            ch = int(choice)

            if 1 <= ch <= len(displayed_candidates):
                selected = displayed_candidates[ch - 1][1]

                same_match = (
                    selected["plex_id"]
                    == current_match["plex_id"]
                )

                playlist_mapping[
                    current_match["search_key"]
                ] = selected["plex_id"]
                self._set_match_provenance(
                    mapping_key,
                    current_match["search_key"],
                    "manual",
                    matched_track=selected,
                    plex_id=selected.get("plex_id"),
                )
                self.config.mapping[mapping_key] = playlist_mapping
                self.config.save()

                if same_match:
                    print(
                        "✓ Match confirmed and marked manual"
                    )
                else:
                    print(
                        f"✓ Updated to: {selected['title']} - "
                        f"{selected['artist']} [manual]"
                    )

                return True, False

        except ValueError:
            pass

        print("✗ Invalid choice")
        return False, False

    def clear_playlist_matching_interactive(self):
        """
        Clear saved matching state for one registered playlist or all of them.

        This resets saved mappings and unresolved-track state only. It does
        not remove playlist registrations or modify Plex playlists.
        """

        playlists = self.config.config.get("playlists", [])

        if not playlists:
            print("✗ No playlists registered")
            return

        print("\nSelect playlist to clear matching:\n")

        for i, playlist in enumerate(playlists, 1):
            mapping_key = (
                f"{playlist['source']}:{playlist['source_id']}"
            )
            match_count = len(
                self.config.mapping.get(mapping_key, {})
            )
            missing_count = len(
                self.config.missing.get(mapping_key, [])
            )

            print(
                f"[{i}] {playlist['plex_playlist_name']} "
                f"({source_display_name(playlist['source'])}) "
                f"- {match_count} saved matches, "
                f"{missing_count} unresolved"
            )

        print("[a] All playlists")
        print("[b] Back")
        print("[x] Exit")

        choice = input("\nSelect: ").strip().lower()

        if choice in ("", "b"):
            return

        if choice == "x":
            sys.exit(0)

        if choice == "a":
            total_matches = 0
            total_missing = 0

            for playlist in playlists:
                mapping_key = (
                    f"{playlist['source']}:{playlist['source_id']}"
                )
                total_matches += len(
                    self.config.mapping.get(mapping_key, {})
                )
                total_missing += len(
                    self.config.missing.get(mapping_key, [])
                )

            confirm = input(
                f"\nClear all saved matching for ALL "
                f"{len(playlists)} playlists? "
                f"This will remove {total_matches} saved matches "
                f"and {total_missing} unresolved records. (y/n): "
            ).strip().lower()

            if confirm not in ("y", "yes"):
                print("✓ Matching was not changed")
                return

            for playlist in playlists:
                mapping_key = (
                    f"{playlist['source']}:{playlist['source_id']}"
                )
                self.config.mapping.pop(mapping_key, None)
                self.config.missing.pop(mapping_key, None)
                self.config.match_metadata.pop(
                    mapping_key,
                    None,
                )

            self.config.save()

            print(
                f"✓ Cleared matching for all "
                f"{len(playlists)} playlists "
                f"({total_matches} saved matches, "
                f"{total_missing} unresolved records)"
            )
            print(
                "  Registered playlists and Plex playlists "
                "were left unchanged."
            )
            print(
                "  The next sync will match every source track again."
            )
            return

        try:
            idx = int(choice) - 1
        except ValueError:
            print("✗ Invalid choice")
            return

        if not (0 <= idx < len(playlists)):
            print("✗ Invalid choice")
            return

        playlist = playlists[idx]
        mapping_key = (
            f"{playlist['source']}:{playlist['source_id']}"
        )

        confirm = input(
            f"\nClear all saved matching for "
            f"'{playlist['plex_playlist_name']}'? (y/n): "
        ).strip().lower()

        if confirm not in ("y", "yes"):
            print("✓ Matching was not changed")
            return

        removed_matches = len(
            self.config.mapping.get(mapping_key, {})
        )
        removed_missing = len(
            self.config.missing.get(mapping_key, [])
        )

        self.config.mapping.pop(mapping_key, None)
        self.config.missing.pop(mapping_key, None)
        self.config.match_metadata.pop(
            mapping_key,
            None,
        )
        self.config.save()

        print(
            f"✓ Cleared matching for "
            f"'{playlist['plex_playlist_name']}' "
            f"({removed_matches} saved matches, "
            f"{removed_missing} unresolved records)"
        )
        print(
            "  The registered playlist and Plex playlist "
            "were left unchanged."
        )
        print(
            "  The next sync will match every source track again."
        )

    def clear_automatic_matching_interactive(self):
        """
        Clear only mappings explicitly recorded as automatic.

        Manual mappings are preserved. Legacy mappings created before
        provenance tracking are also preserved because their origin cannot
        be known safely.
        """

        playlists = self.config.config.get(
            "playlists",
            [],
        )

        if not playlists:
            print("✗ No playlists registered")
            return

        print(
            "\nSelect playlist to clear automatic matches:\n"
        )

        rows = []

        for playlist in playlists:
            mapping_key = (
                f"{playlist['source']}:{playlist['source_id']}"
            )
            counts = self._match_provenance_counts(
                mapping_key
            )
            rows.append(
                (
                    playlist,
                    mapping_key,
                    counts,
                )
            )

        for i, (
            playlist,
            _mapping_key,
            counts,
        ) in enumerate(rows, 1):
            print(
                f"[{i}] {playlist['plex_playlist_name']} "
                f"({source_display_name(playlist['source'])}) "
                f"- {counts['automatic']} automatic, "
                f"{counts['manual']} manual, "
                f"{counts['legacy']} legacy"
            )

        print("[a] All playlists")
        print("[b] Back")
        print("[x] Exit")

        choice = input(
            "\nSelect: "
        ).strip().lower()

        if choice in ("", "b"):
            return

        if choice == "x":
            sys.exit(0)

        selected_rows = []

        if choice == "a":
            selected_rows = rows
            label = "ALL playlists"
        else:
            try:
                idx = int(choice) - 1
            except ValueError:
                print("✗ Invalid choice")
                return

            if not 0 <= idx < len(rows):
                print("✗ Invalid choice")
                return

            selected_rows = [rows[idx]]
            label = (
                f"'{rows[idx][0]['plex_playlist_name']}'"
            )

        automatic_total = sum(
            row[2]["automatic"]
            for row in selected_rows
        )

        if automatic_total == 0:
            print(
                "✓ No automatic matches to clear. "
                "Manual and legacy mappings were unchanged."
            )
            return

        confirm = input(
            f"\nClear {automatic_total} automatic matches "
            f"from {label}? Manual and legacy mappings "
            "will be preserved. (y/n): "
        ).strip().lower()

        if confirm not in ("y", "yes"):
            print("✓ Matching was not changed")
            return

        removed = 0

        for (
            _playlist,
            mapping_key,
            _counts,
        ) in selected_rows:
            mapping = self.config.mapping.get(
                mapping_key,
                {},
            )
            metadata = (
                self._get_match_metadata_bucket(
                    mapping_key,
                    create=False,
                )
            )

            automatic_keys = [
                search_key
                for search_key in list(mapping)
                if (
                    isinstance(
                        metadata.get(search_key),
                        dict,
                    )
                    and metadata[
                        search_key
                    ].get("provenance") == "automatic"
                )
            ]

            for search_key in automatic_keys:
                mapping.pop(search_key, None)
                metadata.pop(search_key, None)
                removed += 1

            if mapping:
                self.config.mapping[
                    mapping_key
                ] = mapping
            else:
                self.config.mapping.pop(
                    mapping_key,
                    None,
                )

            if not metadata:
                self.config.match_metadata.pop(
                    mapping_key,
                    None,
                )

        self.config.save()

        print(
            f"✓ Cleared {removed} automatic matches. "
            "Manual and legacy mappings were preserved."
        )
        print(
            "  Plex playlists were not modified. "
            "Cleared tracks will be matched again on the next sync."
        )

    def settings_interactive(self):
        """Settings submenu with predictable one-level Back behavior."""

        while True:
            print("\n[1] Configure Plex")
            print("[2] Clear all matching for a playlist")
            print("[3] Clear automatic matches")
            print("[b] Back")
            print("[x] Exit")

            choice = input(
                "Select: "
            ).strip().lower()

            if choice in ("", "b"):
                return

            if choice == "x":
                sys.exit(0)

            if choice == "1":
                self.config.setup_plex()
                self.plex = None
                continue

            if choice == "2":
                self.clear_playlist_matching_interactive()
                continue

            if choice == "3":
                self.clear_automatic_matching_interactive()
                continue

            print("✗ Invalid choice")

    @staticmethod
    def _print_previous_lost_match(
        track: dict,
        indent: str = "",
    ):
        """Display the previous Plex target stored with a LOST track."""
        if track.get("status") != "lost":
            return

        previous = track.get(
            "previous_match",
            {},
        )

        if not isinstance(previous, dict):
            previous = {}

        provenance = str(
            track.get(
                "previous_provenance",
                "legacy",
            )
        )

        title = repair_text(
            previous.get("title", "")
        ).strip()
        artist = repair_text(
            previous.get("artist", "")
        ).strip()
        album = repair_text(
            previous.get("album", "")
        ).strip()
        plex_id = str(
            previous.get("plex_id", "")
            or ""
        )

        if title or artist:
            text = (
                f"{title} - {artist}"
            ).strip(" -")

            if album:
                text += f" ({album})"

            print(
                f"{indent}Previous Plex match: "
                f"{text} [{provenance}]"
            )
            return

        if plex_id:
            print(
                f"{indent}Previous Plex match: "
                f"metadata unavailable "
                f"(Plex ID {plex_id}) "
                f"[{provenance}]"
            )
            return

        print(
            f"{indent}Previous Plex match: "
            "metadata unavailable"
        )

    def resolve_missing_interactive(self):
        """Interactive resolution of missing tracks."""

        playlists = self.config.config["playlists"]

        if not playlists:
            print("✗ No playlists registered")
            return

        while True:
            playlists_with_missing = []

            for i, p in enumerate(playlists):
                mapping_key = (
                    f"{p['source']}:{p['source_id']}"
                )
                unmatched = self.config.missing.get(
                    mapping_key,
                    [],
                )

                if unmatched:
                    playlists_with_missing.append(
                        (i, p, len(unmatched))
                    )

            if not playlists_with_missing:
                print("✓ No unmatched tracks to resolve")
                return

            def match_attempt_sort_key(item):
                """Never/invalid first, then oldest successful timestamp."""
                _list_idx, playlist, _count = item
                value = playlist.get("last_match_attempt")

                if not value:
                    return (0, datetime.min)

                try:
                    return (
                        1,
                        datetime.fromisoformat(value),
                    )
                except (TypeError, ValueError):
                    return (0, datetime.min)

            playlists_with_missing.sort(
                key=match_attempt_sort_key
            )

            print("\nPlaylists with unmatched tracks:\n")

            for display_idx, (
                _list_idx,
                playlist,
                unmatched_count,
            ) in enumerate(
                playlists_with_missing,
                1,
            ):
                last_attempt = playlist.get(
                    "last_match_attempt"
                )

                if last_attempt:
                    try:
                        attempt_dt = datetime.fromisoformat(
                            last_attempt
                        )
                        attempt_text = attempt_dt.strftime(
                            "%Y-%m-%d %H:%M"
                        )
                    except (TypeError, ValueError):
                        attempt_text = "Never"
                else:
                    attempt_text = "Never"

                print(
                    f"[{display_idx}] "
                    f"{playlist['plex_playlist_name']} "
                    f"({source_display_name(playlist['source'])}) "
                    f"- {unmatched_count} unmatched "
                    f"- Last match attempt: {attempt_text}"
                )

            print("[a] All missing tracks (deduped)")
            print("[b] Back")
            print("[x] Exit")

            choice = input(
                "\nSelect playlist: "
            ).strip().lower()

            if choice in ("", "b"):
                return

            if choice == "x":
                sys.exit(0)

            if choice == "a":
                self.show_all_missing_tracks_deduped()
                continue

            try:
                idx = int(choice)

                if 1 <= idx <= len(playlists_with_missing):
                    _list_idx, playlist, _count = (
                        playlists_with_missing[idx - 1]
                    )
                    self._resolve_playlist_missing(
                        playlist
                    )
                    continue

            except ValueError:
                pass

            print("✗ Invalid choice")

    def collect_all_missing_tracks_deduped(self):
        """
        Return a deduplicated list of unresolved tracks across all playlists.

        Tracks are deduplicated by normalized title + artist. Album is shown
        when available, preferring a non-empty/non-N/A album from any
        occurrence. The result is sorted by artist, then title.
        """

        playlists = self.config.config.get(
            "playlists",
            [],
        )

        deduped = {}

        for playlist in playlists:
            mapping_key = (
                f"{playlist['source']}:{playlist['source_id']}"
            )
            unresolved = self.config.missing.get(
                mapping_key,
                [],
            )

            for track in unresolved:
                title = repair_text(
                    track.get("title", "")
                ).strip()
                artist = repair_text(
                    track.get("artist", "")
                ).strip()
                album = repair_text(
                    track.get("album", "")
                ).strip()

                key = (
                    title.casefold(),
                    artist.casefold(),
                )

                if key not in deduped:
                    deduped[key] = {
                        "title": title,
                        "artist": artist,
                        "album": album,
                        "playlists": [],
                        "playlist_count": 0,
                        "occurrence_count": 0,
                        "lost_occurrence_count": 0,
                    }

                entry = deduped[key]
                entry["occurrence_count"] += 1

                if track.get("status") == "lost":
                    entry[
                        "lost_occurrence_count"
                    ] += 1

                if album and album.casefold() != "n/a":
                    current_album = (
                        entry.get("album", "").strip()
                    )

                    if (
                        not current_album
                        or current_album.casefold() == "n/a"
                    ):
                        entry["album"] = album

                playlist_name = playlist[
                    "plex_playlist_name"
                ]

                if playlist_name not in entry["playlists"]:
                    entry["playlists"].append(
                        playlist_name
                    )
                    entry["playlist_count"] += 1

        results = list(deduped.values())
        results.sort(
            key=lambda item: (
                item["artist"].casefold(),
                item["title"].casefold(),
                item["album"].casefold(),
            )
        )
        return results

    def show_all_missing_tracks_deduped(self):
        """Display all unresolved tracks across all playlists."""

        deduped = self.collect_all_missing_tracks_deduped()

        if not deduped:
            print("✓ No unmatched tracks to display")
            return

        print(
            f"\nAll missing tracks across playlists "
            f"({len(deduped)} unique):\n"
        )

        for i, track in enumerate(
            deduped,
            1,
        ):
            lost_prefix = ""

            if track.get(
                "lost_occurrence_count",
                0,
            ):
                lost_prefix = (
                    f"{colored('LOST', Colors.RED)} "
                )

            print(
                f"[{i}] "
                f"{lost_prefix}"
                f"{colored(track['title'], Colors.CYAN)} - "
                f"{colored(track['artist'], Colors.GREEN)} "
                f"{source_album_display(track)}"
            )

            playlist_word = (
                "playlist"
                if track["playlist_count"] == 1
                else "playlists"
            )
            occurrence_word = (
                "occurrence"
                if track["occurrence_count"] == 1
                else "occurrences"
            )

            print(
                f"    Appears in "
                f"{track['playlist_count']} {playlist_word}, "
                f"{track['occurrence_count']} unresolved "
                f"{occurrence_word}"
            )
            if track.get(
                "lost_occurrence_count",
                0,
            ):
                print(
                    f"    LOST occurrences: "
                    f"{track['lost_occurrence_count']}"
                )

            print(
                f"    Playlists: "
                f"{', '.join(track['playlists'])}"
            )

        print("\n[b] Back")
        print("[x] Exit")

        while True:
            choice = input(
                "\nSelect: "
            ).strip().lower()

            if choice in ("", "b"):
                return

            if choice == "x":
                sys.exit(0)

            print("✗ Invalid choice")


    def _resolve_playlist_missing(
        self,
        playlist: dict,
    ):
        """
        Resolve missing tracks for a specific playlist.

        Always show the top five Plex candidates with scores, even when all
        candidates are below PROMPT_THRESHOLD. Automatic matching remains
        conservative; this is only for human review.
        """

        mapping_key = (
            f"{playlist['source']}:{playlist['source_id']}"
        )

        unmatched = list(
            self.config.missing.get(
                mapping_key,
                [],
            )
        )

        if not unmatched:
            print("✓ No unmatched tracks")
            return

        # Show the complete list before doing any Plex scan or source refresh.
        # This lets the user review what is missing and back out immediately.
        print(
            f"\nMissing tracks for "
            f"'{playlist['plex_playlist_name']}' "
            f"({len(unmatched)} total):\n"
        )

        for i, track in enumerate(unmatched, 1):
            lost_prefix = ""

            if track.get("status") == "lost":
                lost_prefix = (
                    f"{colored('LOST', Colors.RED)} "
                )

            print(
                f"[{i}] "
                f"{lost_prefix}"
                f"{colored(track['title'], Colors.CYAN)} - "
                f"{colored(track['artist'], Colors.GREEN)} "
                f"{source_album_display(track)}"
            )

            if track.get("status") == "lost":
                self._print_previous_lost_match(
                    track,
                    indent="    ",
                )

        print("\n[t] Start triage")
        print("[b] Back")
        print("[x] Exit")

        triage_choice = input(
            "\nSelect: "
        ).strip().lower()

        if triage_choice in ("", "b"):
            return

        if triage_choice == "x":
            sys.exit(0)

        if triage_choice != "t":
            print("✗ Invalid choice")
            return

        # Count this as a match-fixing attempt only after the user explicitly
        # starts triage. Simply viewing the missing-track list does not update
        # the timestamp.
        playlist["last_match_attempt"] = (
            datetime.now().isoformat()
        )
        self.config.save()

        plex = self._get_plex()

        playlist_mapping = self.config.mapping.get(
            mapping_key,
            {},
        )

        plex_library = plex.search_library("")

        if not plex_library:
            print("✗ No Plex music tracks found")
            return

        # Older missing_tracks.json entries only stored title/artist.
        # Re-fetch the source playlist once so we can recover album metadata
        # before ranking candidates. If the source fetch fails, Option 5
        # still works using title/artist only.
        try:
            source_type = playlist["source"]
            source_url = playlist.get("source_url", "")
            source_id = playlist.get("source_id", "")

            api = (
                SpotifyAPI()
                if source_type == "spotify"
                else AppleMusicAPI()
            )

            source_tracks, _ = api.get_playlist_tracks(
                source_url
                if source_type in ("spotify", "applemusic")
                else source_id,
                fetch_artwork=False,
            )

            source_lookup = {
                (
                    str(t.get("title", "")).casefold().strip(),
                    str(t.get("artist", "")).casefold().strip(),
                ): t
                for t in source_tracks
            }

            recovered = 0

            for track in unmatched:
                if track.get("album"):
                    continue

                key = (
                    str(track.get("title", "")).casefold().strip(),
                    str(track.get("artist", "")).casefold().strip(),
                )

                source_track = source_lookup.get(key)

                if source_track:
                    if source_track.get("album"):
                        track["album"] = source_track.get("album", "")
                        recovered += 1

                    if source_track.get("source_id"):
                        track["source_id"] = source_track.get(
                            "source_id",
                            "",
                        )

            if recovered:
                print(
                    f"  ✓ Recovered album metadata for "
                    f"{recovered} missing tracks"
                )

        except Exception as e:
            print(
                f"  ⚠ Could not refresh source metadata for "
                f"Option 5: {e}"
            )

        print(
            f"\nResolving {len(unmatched)} "
            "unmatched tracks:\n"
        )

        still_unmatched = []
        track_index = 0

        while track_index < len(unmatched):
            track = unmatched[track_index]

            # Score EVERY Plex track. This is intentionally different from
            # automatic matching: the user asked to see the best available
            # choices even when none reaches the normal confidence threshold.
            candidates = []

            for plex_track in plex_library:
                details = Matcher.score_candidate(
                    track,
                    plex_track,
                )

                score = int(
                    round(details["adjusted_score"])
                )

                if score >= Matcher.MIN_DISPLAY_SCORE:
                    candidates.append(
                        (
                            score,
                            details["identity_score"],
                            details,
                            plex_track,
                        )
                    )

            candidates.sort(
                key=lambda item: (
                    item[0],  # adjusted score
                    item[1],  # raw title/artist identity
                    item[2]["title_score"],
                    item[2]["raw_title_score"],
                    item[2]["artist_score"],
                ),
                reverse=True,
            )

            displayed_candidates = candidates[:5]

            lost_prefix = ""

            if track.get("status") == "lost":
                lost_prefix = (
                    f"{colored('LOST', Colors.RED)} "
                )

            print(
                f"\n[{track_index + 1}/{len(unmatched)}] "
                f"{lost_prefix}"
                f"{colored(track['title'], Colors.CYAN)} - "
                f"{colored(track['artist'], Colors.GREEN)} "
                f"{source_album_display(track)}"
            )

            if track.get("status") == "lost":
                self._print_previous_lost_match(
                    track,
                    indent="  ",
                )

            print("\n  Best Plex candidates:")

            if displayed_candidates:
                for i, (
                    score,
                    identity_score,
                    details,
                    cand,
                ) in enumerate(
                    displayed_candidates,
                    1,
                ):
                    album = cand.get("album", "")
                    cand_title = colored(
                        cand["title"],
                        Colors.CYAN,
                    )
                    cand_artist = colored(
                        cand["artist"],
                        Colors.GREEN,
                    )
                    album_str = (
                        f" {colored(f'({album})', Colors.YELLOW)}"
                        if album
                        else ""
                    )

                    confidence_note = ""
                    if identity_score < Matcher.PROMPT_THRESHOLD:
                        confidence_note = " [LOW CONFIDENCE]"

                    penalty_note = ""
                    if details["album_penalty"]:
                        kinds = ", ".join(
                            sorted(
                                details["plex_album_types"]
                                - details["requested_variant_types"]
                            )
                        )
                        penalty_note = (
                            f" [-{details['album_penalty']} "
                            f"{kinds}]"
                        )

                    title_variant_note = ""
                    if details["title_variant_penalty"]:
                        kinds = ", ".join(
                            sorted(
                                (
                                    details["plex_title_release_types"]
                                    & Matcher.VERSION_TYPES
                                )
                                - details["requested_variant_types"]
                            )
                        )
                        title_variant_note = (
                            f" [-{details['title_variant_penalty']} "
                            f"{kinds} title]"
                        )

                    intent_note = ""
                    if details["release_intent_penalty"]:
                        missing = ", ".join(
                            sorted(
                                details["requested_variant_types"]
                                - details["candidate_variant_types"]
                            )
                        )
                        intent_note = (
                            f" [-{details['release_intent_penalty']} "
                            f"title missing {missing}]"
                        )

                    print(
                        f"  [{i}] {cand_title} - "
                        f"{cand_artist}{album_str} "
                        f"({score}%){penalty_note}{title_variant_note}{intent_note}"
                        f"{confidence_note}"
                    )
            else:
                print("      No Plex tracks available.")

            print("  [s] Skip")
            print("  [m] Manual search")
            print("  [f] Finish triage & sync now")
            print("  [x] Exit")

            choice = input(
                "  Select: "
            ).strip().lower()

            if choice == "f":
                # End this triage session without losing our place.
                # Keep the current track plus everything not yet reviewed.
                still_unmatched.extend(
                    unmatched[track_index:]
                )

                # Persist all mappings and remaining unmatched tracks BEFORE
                # starting the Plex sync.
                self.config.mapping[mapping_key] = (
                    playlist_mapping
                )

                if still_unmatched:
                    self.config.missing[mapping_key] = (
                        still_unmatched
                    )
                else:
                    self.config.missing.pop(
                        mapping_key,
                        None,
                    )

                self.config.save()

                print(
                    f"\n✓ Triage progress saved. "
                    f"{len(still_unmatched)} tracks remain unmatched."
                )

                print(
                    f"\n→ Syncing "
                    f"'{playlist['plex_playlist_name']}' "
                    "to Plex now..."
                )

                self.sync_playlist(playlist)

                print(
                    "\n✓ Triage session finished. "
                    "You can return to Option 5 later "
                    "to continue the remaining tracks."
                )
                return

            if choice == "x":
                # Save any matches already made in this session before exit.
                still_unmatched.extend(
                    unmatched[track_index:]
                )
                self.config.mapping[mapping_key] = (
                    playlist_mapping
                )
                self.config.missing[mapping_key] = (
                    still_unmatched
                )
                self.config.save()
                sys.exit(0)

            if choice == "m":
                manual_choice = input(
                    "  Search Plex title, artist, or album: "
                ).strip().lower()

                if not manual_choice:
                    still_unmatched.append(track)
                    track_index += 1
                    continue

                manual_candidates = []

                for plex_track in plex_library:
                    haystack = (
                        f"{plex_track.get('title', '')} "
                        f"{plex_track.get('artist', '')} "
                        f"{plex_track.get('album', '')}"
                    ).casefold()

                    if manual_choice not in haystack:
                        continue

                    details = Matcher.score_candidate(
                        track,
                        plex_track,
                    )

                    manual_score = int(
                        round(details["adjusted_score"])
                    )

                    if manual_score < Matcher.MIN_DISPLAY_SCORE:
                        continue

                    manual_candidates.append(
                        (
                            manual_score,
                            details["identity_score"],
                            details,
                            plex_track,
                        )
                    )

                manual_candidates.sort(
                    key=lambda item: (
                        item[0],
                        item[1],
                        item[2]["title_score"],
                        item[2]["artist_score"],
                    ),
                    reverse=True,
                )

                displayed_manual = (
                    manual_candidates[:10]
                )

                if displayed_manual:
                    print(
                        f"\n  Found "
                        f"{len(manual_candidates)} "
                        f"Plex matches:\n"
                    )

                    for i, (
                        score,
                        identity_score,
                        details,
                        match,
                    ) in enumerate(
                        displayed_manual,
                        1,
                    ):
                        album = match.get(
                            "album",
                            "",
                        )
                        match_title = colored(
                            match["title"],
                            Colors.CYAN,
                        )
                        match_artist = colored(
                            match["artist"],
                            Colors.GREEN,
                        )
                        album_str = (
                            f" "
                            f"{colored(f'({album})', Colors.YELLOW)}"
                            if album
                            else ""
                        )

                        confidence_note = ""
                        if (
                            identity_score
                            < Matcher.PROMPT_THRESHOLD
                        ):
                            confidence_note = (
                                " [LOW CONFIDENCE]"
                            )

                        penalty_note = ""
                        if details["album_penalty"]:
                            kinds = ", ".join(
                                sorted(
                                    details["plex_album_types"]
                                    - details["requested_variant_types"]
                                )
                            )
                            penalty_note = (
                                f" [-"
                                f"{details['album_penalty']} "
                                f"{kinds}]"
                            )

                        title_variant_note = ""
                        if details["title_variant_penalty"]:
                            kinds = ", ".join(
                                sorted(
                                    (
                                        details["plex_title_release_types"]
                                        & Matcher.VERSION_TYPES
                                    )
                                    - details["requested_variant_types"]
                                )
                            )
                            title_variant_note = (
                                f" [-{details['title_variant_penalty']} "
                                f"{kinds} title]"
                            )

                        intent_note = ""
                        if details["release_intent_penalty"]:
                            missing = ", ".join(
                                sorted(
                                    details["requested_variant_types"]
                                    - details["candidate_variant_types"]
                                )
                            )
                            intent_note = (
                                f" [-{details['release_intent_penalty']} "
                                f"title missing {missing}]"
                            )

                        print(
                            f"    [{i}] "
                            f"{match_title} - "
                            f"{match_artist}"
                            f"{album_str} "
                            f"({score}%)"
                            f"{penalty_note}"
                            f"{title_variant_note}"
                            f"{intent_note}"
                            f"{confidence_note}"
                        )

                    print(
                        "    [c] Cancel manual search"
                    )

                    sub_choice = input(
                        "    Select: "
                    ).strip().lower()

                    if sub_choice == "c":
                        still_unmatched.append(track)
                        track_index += 1
                        continue

                    try:
                        sub_ch = int(sub_choice)

                        if (
                            1
                            <= sub_ch
                            <= len(displayed_manual)
                        ):
                            selected = (
                                displayed_manual[
                                    sub_ch - 1
                                ][3]
                            )

                            search_key = (
                                f"{track['title']}|"
                                f"{track['artist']}"
                            )

                            playlist_mapping[
                                search_key
                            ] = selected["plex_id"]
                            self._set_match_provenance(
                                mapping_key,
                                search_key,
                                "manual",
                                matched_track=selected,
                                plex_id=selected.get("plex_id"),
                            )

                            print(
                                f"    ✓ Matched to: "
                                f"{selected['title']} - "
                                f"{selected['artist']}"
                            )
                        else:
                            print(
                                "    ✗ Invalid selection"
                            )
                            still_unmatched.append(
                                track
                            )

                    except ValueError:
                        print(
                            "    ✗ Invalid selection"
                        )
                        still_unmatched.append(track)

                else:
                    print(
                        "  ✗ No Plex matches found "
                        "for that search"
                    )
                    still_unmatched.append(track)

                track_index += 1
                continue

            if choice == "s":
                still_unmatched.append(track)
                track_index += 1
                continue

            try:
                ch = int(choice)

                if (
                    1
                    <= ch
                    <= len(displayed_candidates)
                ):
                    selected = (
                        displayed_candidates[
                            ch - 1
                        ][3]
                    )

                    search_key = (
                        f"{track['title']}|"
                        f"{track['artist']}"
                    )

                    playlist_mapping[
                        search_key
                    ] = selected["plex_id"]
                    self._set_match_provenance(
                        mapping_key,
                        search_key,
                        "manual",
                        matched_track=selected,
                        plex_id=selected.get("plex_id"),
                    )

                    print(
                        f"  ✓ Matched to: "
                        f"{selected['title']} - "
                        f"{selected['artist']}"
                    )

                else:
                    print(
                        "  ✗ Invalid selection; "
                        "track left unmatched"
                    )
                    still_unmatched.append(track)

            except ValueError:
                print(
                    "  ✗ Invalid selection; "
                    "track left unmatched"
                )
                still_unmatched.append(track)

            track_index += 1

        self.config.mapping[mapping_key] = (
            playlist_mapping
        )

        if still_unmatched:
            self.config.missing[mapping_key] = (
                still_unmatched
            )
        else:
            self.config.missing.pop(
                mapping_key,
                None,
            )

        self.config.save()

        print("\n✓ Saved matches")

        if still_unmatched:
            print(
                f"⚠ {len(still_unmatched)} tracks "
                "remain unmatched"
            )
        else:
            print(
                "✓ All previously unmatched tracks "
                "have been resolved"
            )

        # Offer to immediately rebuild the Plex playlist using the mappings
        # that were just saved in Option 5.
        sync_now = input(
            "\nSync this playlist to Plex now? (y/n): "
        ).strip().lower()

        if sync_now in ("y", "yes"):
            print(
                f"\n→ Syncing "
                f"'{playlist['plex_playlist_name']}' "
                "to Plex..."
            )
            self.sync_playlist(playlist)
        else:
            print(
                "✓ Matches saved. Plex playlist was not synced."
            )


def print_menu(
    dev_mode: bool = False,
):
    """Print main menu."""

    print("\n" + "=" * 50)
    print(
        f"{APP_NAME} v{VERSION} - Spotify/Apple Music to Plex"
    )
    print("=" * 50)
    print(
        "[1] Add new Spotify/Apple Music playlist"
    )
    print("[2] Sync all playlists")
    print("[3] Sync specific playlist")
    print("[4] View registered playlists")
    print("[5] Resolve missing tracks")
    print("[6] Edit playlist matches")
    print("[7] Sync history")
    print("[8] Remove playlist")
    print("[9] Settings")

    if dev_mode:
        print("[10] Developer tools")

    print("[x] Exit")
    print("=" * 50)


def show_playlists(config: Config):
    """Show registered playlists, oldest last-sync first."""

    playlists = sorted(
        config.config["playlists"],
        key=lambda p: oldest_timestamp_sort_key(
            p,
            "last_synced",
        ),
    )

    if not playlists:
        print("\n✗ No playlists registered")
        return

    print("\nRegistered playlists:\n")

    for i, p in enumerate(playlists, 1):
        print(
            f"[{i}] {p['plex_playlist_name']}"
        )
        print(
            f"    Source: {source_display_name(p['source'])}"
        )
        print(
            f"    URL: {p['source_url'][:60]}..."
        )
        print(
            f"    Last sync: "
            f"{format_timestamp(p.get('last_synced'))}\n"
        )


def show_sync_history(config: Config):
    """Show sync history."""

    playlists = config.config["playlists"]

    history = []

    for p in playlists:
        if p.get("last_synced"):
            history.append(
                {
                    "name": p[
                        "plex_playlist_name"
                    ],
                    "time": datetime.fromisoformat(
                        p["last_synced"]
                    ),
                }
            )

    if not history:
        print("\n✗ No sync history")
        return

    history.sort(
        key=lambda x: x["time"],
        reverse=True,
    )

    print(
        "\nSync history (most recent first):\n"
    )

    for i, h in enumerate(history[:10], 1):
        print(
            f"{i}. {h['name']} - "
            f"{h['time'].strftime('%Y-%m-%d %H:%M')}"
        )


def pick_playlist(
    config: Config,
    action: str = "sync",
):
    """Let user pick one playlist."""

    playlists = list(
        config.config["playlists"]
    )

    if action == "sync":
        playlists.sort(
            key=lambda p: oldest_timestamp_sort_key(
                p,
                "last_synced",
            )
        )

    if not playlists:
        print("\n✗ No playlists registered")
        return None

    print(
        f"\nSelect playlist to {action}:\n"
    )

    for i, p in enumerate(playlists, 1):
        line = (
            f"[{i}] {p['plex_playlist_name']} "
            f"({source_display_name(p['source'])})"
        )

        if action == "sync":
            line += (
                f" - Last sync: "
                f"{format_timestamp(p.get('last_synced'))}"
            )

        print(line)

    print("[b] Back")
    print("[x] Exit")

    choice = input(
        "\nSelect: "
    ).strip().lower()

    if choice in ("", "b"):
        return None

    if choice == "x":
        sys.exit(0)

    try:
        idx = int(choice)

        if 1 <= idx <= len(playlists):
            return playlists[idx - 1]

    except ValueError:
        pass

    print("✗ Invalid choice")
    return None


def pick_playlists_to_sync(
    config: Config,
) -> List[dict]:
    """Select one or more playlists, oldest last-sync first."""

    playlists = sorted(
        config.config["playlists"],
        key=lambda p: oldest_timestamp_sort_key(
            p,
            "last_synced",
        ),
    )

    if not playlists:
        print("\n✗ No playlists registered")
        return []

    print(
        "\nSelect one or more playlists to sync:\n"
    )

    for i, playlist in enumerate(
        playlists,
        1,
    ):
        print(
            f"[{i}] {playlist['plex_playlist_name']} "
            f"({source_display_name(playlist['source'])}) "
            f"- Last sync: "
            f"{format_timestamp(playlist.get('last_synced'))}"
        )

    print(
        "\nEnter selections separated by commas "
        "(example: 1,3,5). Ranges such as 1-3 also work."
    )
    print("[b] Back")
    print("[x] Exit")

    choice = input(
        "\nSelect: "
    ).strip().lower()

    if choice in ("", "b"):
        return []

    if choice == "x":
        sys.exit(0)

    try:
        indices = parse_index_selection(
            choice,
            len(playlists),
        )
    except ValueError:
        print("✗ Invalid selection")
        return []

    return [
        playlists[index]
        for index in indices
    ]


def interactive_menu(
    dev_mode: bool = False,
):
    """Main interactive menu."""

    config = Config()
    syncer = Syncer(config)

    while True:
        print_menu(
            dev_mode=dev_mode,
        )

        choice = input(
            "Enter choice: "
        ).strip().lower()

        if not choice:
            print("✗ Please enter a valid option")
            continue

        if choice == "1":
            url = input(
                "\nPaste playlist URL "
                "(Spotify or Apple Music): "
            ).strip()

            if url:
                syncer.add_source(url)
            else:
                print("✗ No URL provided")

        elif choice == "2":
            syncer.sync_all()

        elif choice == "3":
            selected_playlists = (
                pick_playlists_to_sync(
                    config
                )
            )

            for playlist in selected_playlists:
                syncer.sync_playlist(
                    playlist
                )

        elif choice == "4":
            show_playlists(config)

        elif choice == "5":
            syncer.resolve_missing_interactive()

        elif choice == "6":
            syncer.edit_playlist_matches()

        elif choice == "7":
            show_sync_history(config)

        elif choice == "8":
            playlist = pick_playlist(
                config,
                "remove",
            )

            if playlist:
                confirm = (
                    input(
                        f"\nRemove "
                        f"'{playlist['plex_playlist_name']}'?"
                        " (y/n): "
                    )
                    .strip()
                    .lower()
                )

                if confirm == "y":
                    idx = config.config[
                        "playlists"
                    ].index(playlist)

                    config.remove_playlist(idx)
                    print("✓ Removed")

        elif choice == "9":
            syncer.settings_interactive()

        elif choice == "10" and dev_mode:
            syncer.developer_menu_interactive()

        elif choice == "x":
            print("\nGoodbye!")
            sys.exit(0)

        else:
            print("✗ Invalid choice")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(
        description=(
            f"{APP_NAME} v{VERSION} - Sync Spotify and Apple Music "
            "playlists to Plex. Run without arguments for the "
            "interactive menu."
        )
    )

    parser.add_argument(
        "--sync-all",
        action="store_true",
        help=(
            "Sync all registered playlists to Plex non-interactively "
            "using saved mappings."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "With --sync-all, test source fetching and matching without "
            "changing Plex or saving local matching state."
        ),
    )

    parser.add_argument(
        "-devmode",
        "--devmode",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Run either the automated CLI action or the interactive menu."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.dry_run and not args.sync_all:
        parser.error(
            "--dry-run must be used with --sync-all"
        )

    if args.sync_all:
        config = Config()

        # --sync-all must remain fully automated. Avoid Config.get_plex()
        # here because it can launch the interactive Plex setup flow.
        plex_cfg = config.config.get("plex", {})

        if not plex_cfg.get("url") or not plex_cfg.get("token"):
            print(
                "✗ Plex is not configured. "
                "Run without arguments and configure Plex first."
            )
            return 1

        if not config.config.get("playlists"):
            print("✗ No playlists registered")
            return 1

        syncer = Syncer(config)
        syncer.sync_all(
            dry_run=args.dry_run,
        )
        return 0

    interactive_menu(
        dev_mode=args.devmode,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())