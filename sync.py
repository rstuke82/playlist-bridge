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
import sys
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
VERSION = "1.0"

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
    album = str(track.get("album", "") or "").strip()

    if album:
        return colored(f"({album})", Colors.YELLOW)

    return "(N/A)"


# Config file locations - stored in project root
CONFIG_DIR = Path.cwd()
CONFIG_FILE = CONFIG_DIR / "config.json"
MAPPING_FILE = CONFIG_DIR / "mapping.json"
MISSING_FILE = CONFIG_DIR / "missing_tracks.json"

# Requested square Apple Music playlist artwork size for Plex.
APPLE_ARTWORK_SIZE = 3000


class Config:
    """Handle configuration file management"""

    def __init__(self):
        CONFIG_DIR.mkdir(exist_ok=True)
        self.config = self._load_config()
        self.mapping = self._load_mapping()
        self.missing = self._load_missing()

    def _load_config(self) -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return {"plex": {}, "playlists": []}

    def _load_mapping(self) -> dict:
        if MAPPING_FILE.exists():
            with open(MAPPING_FILE) as f:
                return json.load(f)
        return {}

    def _load_missing(self) -> dict:
        if MISSING_FILE.exists():
            with open(MISSING_FILE) as f:
                return json.load(f)
        return {}

    def save(self):
        """Save all config files"""
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

        with open(MAPPING_FILE, "w") as f:
            json.dump(self.mapping, f, indent=2)

        with open(MISSING_FILE, "w") as f:
            json.dump(self.missing, f, indent=2)

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
        self, playlist_id: str
    ) -> Tuple[List[dict], dict]:
        """Fetch a public Spotify playlist from a raw ID or full URL."""

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

            name = entity.get("name", "Unknown Playlist")
            description = entity.get("description", "")

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

                track_list.append(
                    {
                        "title": title,
                        "artist": artist_names,
                        "album": album_name,
                        "source_id": track.get("id", ""),
                        "uri": track.get("uri", ""),
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
            "name": name or "Apple Music Playlist",
            "description": description,
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
            "title": title.strip(),
            "artist": artist.strip(),
            "album": album.strip() if isinstance(album, str) else "",
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

    def get_playlist_tracks(
        self, playlist_url: str
    ) -> Tuple[List[dict], dict]:
        """Fetch tracks and metadata from a public Apple Music playlist."""

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

            metadata = self._extract_metadata(
                data,
                soup,
            )

            tracks = self._extract_tracks(data)

            if not tracks:
                raise Exception(
                    "Apple Music page loaded, but no playlist tracks "
                    "could be extracted from serialized-server-data"
                )

            if not metadata.get("image_url"):
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
                    "title": t.get("title", ""),
                    "artist": t.get("grandparentTitle", ""),
                    "album": t.get("parentTitle", ""),
                    "plex_id": str(t.get("ratingKey")),
                    "key": t.get("key"),
                }
                for t in tracks
                if t.get("ratingKey")
            ]

        except Exception as e:
            print(f"Error searching library: {e}")
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
            params = {
                "title": title,
                "summary": description or "",
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

    # These are ranking penalties, not hard exclusions. If the only copy
    # available is on a compilation/live/deluxe release, it can still match.
    ALBUM_TYPE_PENALTIES = {
        "compilation": 14,
        "live": 16,
        "remix": 14,
        "acoustic": 10,
        "deluxe": 7,
        "remaster": 5,
    }

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
        source_title = str(source_track.get("title", "")).casefold()
        source_artist = str(source_track.get("artist", "")).casefold()
        source_album = str(source_track.get("album", "") or "")

        plex_title = str(plex_track.get("title", "")).casefold()
        plex_artist = str(plex_track.get("artist", "")).casefold()
        plex_album = str(plex_track.get("album", "") or "")

        title_score = fuzz.token_sort_ratio(
            source_title,
            plex_title,
        )

        artist_score = fuzz.ratio(
            source_artist,
            plex_artist,
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

                # Reward the intended album, but don't let album metadata
                # overpower title/artist identity.
                if album_score >= 95:
                    album_bonus = 12
                elif album_score >= 85:
                    album_bonus = 8
                elif album_score >= 70:
                    album_bonus = 4

        source_types = cls._album_types(source_album)
        plex_types = cls._album_types(plex_album)

        # Canonical-copy preference:
        #
        # Streaming services frequently point a playlist entry at a
        # compilation/remaster/live/deluxe release even when the same song
        # exists on its original studio album in Plex. We therefore penalize
        # special-release Plex copies regardless of the source album type.
        #
        # This remains a ranking preference rather than a hard exclusion:
        # if the special-release copy is the only strong title/artist match,
        # match_track() can still use it.
        album_penalty = sum(
            cls.ALBUM_TYPE_PENALTIES[kind]
            for kind in plex_types
        )

        # Do not reward an exact album-name match when that album itself is
        # one of the non-canonical release types we're trying to de-prioritize.
        # Example: Spotify says Greatest Hits, but Plex also has Transistor.
        if source_types or plex_types:
            if plex_types:
                album_bonus = 0.0

        adjusted_score = max(
            0.0,
            min(
                100.0,
                identity_score
                + album_bonus
                - album_penalty,
            ),
        )

        return {
            "adjusted_score": adjusted_score,
            "identity_score": identity_score,
            "title_score": title_score,
            "artist_score": artist_score,
            "album_score": album_score,
            "album_bonus": album_bonus,
            "album_penalty": album_penalty,
            "source_album_types": source_types,
            "plex_album_types": plex_types,
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
            ),
        )

        # Album penalties affect which copy wins, not whether a confident
        # title/artist identity is allowed to match.
        if (
            best_details["identity_score"] >= cls.MATCH_THRESHOLD
            and best_details["title_score"] >= 75
        ):
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
    ) -> Tuple[List[str], List[dict], dict, Optional[List[dict]]]:
        """
        Match source tracks against Plex.

        Returns:
            matched Plex IDs in source order,
            unmatched source tracks,
            updated playlist mapping,
            plex_library for reuse.
        """

        plex = self._get_plex()

        playlist_mapping = self.config.mapping.get(
            mapping_key, {}
        )

        if plex_library is None:
            print("→ Scanning Plex library...")
            plex_library = plex.search_library("")

            if not plex_library:
                print("✗ No Plex music tracks were found.")
                return [], source_tracks, playlist_mapping, plex_library

            print(
                f"  Found {len(plex_library)} tracks in Plex library"
            )

        print("→ Matching tracks...")

        matched_tracks = []
        unmatched = []
        match_details = []

        for i, track in enumerate(source_tracks, 1):
            search_key = (
                f"{track['title']}|{track['artist']}"
            )

            if search_key in playlist_mapping:
                plex_id = playlist_mapping[search_key]
                matched_track = next(
                    (t for t in plex_library if t["plex_id"] == plex_id),
                    None
                )

                matched_tracks.append(str(plex_id))
                match_details.append({
                    'source': track,
                    'matched': matched_track,
                    'plex_id': str(plex_id),
                    'cached': True,
                })

                matched_info = ""
                if matched_track:
                    album = matched_track.get("album", "")
                    matched_title = colored(matched_track['title'], Colors.CYAN)
                    matched_artist = colored(matched_track['artist'], Colors.GREEN)
                    if album:
                        album_str = colored(f"({album})", Colors.YELLOW)
                        matched_info = f" → {matched_title} - {matched_artist} {album_str}"
                    else:
                        matched_info = f" → {matched_title} - {matched_artist}"
                
                source_title = colored(track['title'], Colors.CYAN)
                source_artist = colored(track['artist'], Colors.GREEN)
                print(
                    f"  [{i}/{len(source_tracks)}] "
                    f"{colored('✓', Colors.GREEN)} "
                    f"{source_title} - {source_artist} "
                    f"{source_album_display(track)}"
                    f"{matched_info}"
                )
                continue

            plex_id = Matcher.match_track(
                track,
                plex_library,
                playlist_mapping,
            )

            if plex_id:
                playlist_mapping[search_key] = str(plex_id)
                matched_tracks.append(str(plex_id))
                matched_track = next(
                    (t for t in plex_library if t["plex_id"] == plex_id),
                    None
                )
                match_details.append({
                    'source': track,
                    'matched': matched_track,
                    'plex_id': str(plex_id),
                    'cached': False,
                })

                matched_info = ""
                if matched_track:
                    album = matched_track.get("album", "")
                    matched_title = colored(matched_track['title'], Colors.CYAN)
                    matched_artist = colored(matched_track['artist'], Colors.GREEN)
                    if album:
                        album_str = colored(f"({album})", Colors.YELLOW)
                        matched_info = f" → {matched_title} - {matched_artist} {album_str}"
                    else:
                        matched_info = f" → {matched_title} - {matched_artist}"
                
                source_title = colored(track['title'], Colors.CYAN)
                source_artist = colored(track['artist'], Colors.GREEN)
                print(
                    f"  [{i}/{len(source_tracks)}] "
                    f"{colored('✓', Colors.GREEN)} "
                    f"{source_title} - {source_artist} "
                    f"{source_album_display(track)}"
                    f"{matched_info}"
                )
            else:
                unmatched.append(track)
                match_details.append({
                    'source': track,
                    'matched': None,
                    'plex_id': None,
                    'cached': False,
                })

                source_title = colored(track['title'], Colors.CYAN)
                source_artist = colored(track['artist'], Colors.GREEN)
                print(
                    f"  [{i}/{len(source_tracks)}] "
                    f"{colored('✗', Colors.RED)} "
                    f"{source_title} - {source_artist} "
                    f"{source_album_display(track)}"
                )

        return matched_tracks, unmatched, playlist_mapping, plex_library

    def _store_unmatched(
        self,
        mapping_key: str,
        unmatched: List[dict],
    ):
        """Store unmatched tracks."""

        if unmatched:
            self.config.missing[mapping_key] = [
                {
                    "title": t["title"],
                    "artist": t["artist"],
                    "album": t.get("album", ""),
                    "source_id": t.get("source_id", ""),
                }
                for t in unmatched
            ]

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
                tracks, metadata = api.get_playlist_tracks(source_url)
            else:
                tracks, metadata = api.get_playlist_tracks(source_url)
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

        matched_tracks, unmatched, playlist_mapping, plex_library = (
            self._match_source_tracks(
                tracks,
                mapping_key,
            )
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
        self.config.save()

        print(
            f"\n✓ Playlist '{playlist_name}' added to Plex "
            "and configured for sync!"
        )

        if unmatched:
            print(
                f"⚠ {len(unmatched)} tracks still need "
                "resolution."
            )

    def sync_playlist(
        self,
        playlist_entry: dict,
    ):
        """Sync a specific playlist."""

        source_type = playlist_entry["source"]
        source_url = Config._normalize_url_input(playlist_entry["source_url"])
        playlist_id = Config._extract_id(source_url, source_type)

        if not playlist_id:
            print(
                f"✗ Could not extract playlist ID from stored URL: "
                f"{source_url}"
            )
            return

        # Repair older config entries automatically. This path is used by
        # both option 2 (sync all) and option 3 (sync specific playlist).
        canonical_url = Config._canonical_source_url(source_url, source_type)
        changed = False
        old_source_id = playlist_entry.get("source_id")
        if old_source_id != playlist_id:
            old_mapping_key = (
                f"{source_type}:{old_source_id}"
                if old_source_id
                else None
            )
            new_mapping_key = f"{source_type}:{playlist_id}"

            # Preserve existing match/missing caches when repairing an
            # older or malformed stored source_id.
            if old_mapping_key and old_mapping_key != new_mapping_key:
                if old_mapping_key in self.config.mapping:
                    existing = self.config.mapping.pop(old_mapping_key)
                    self.config.mapping.setdefault(new_mapping_key, {}).update(existing)
                if old_mapping_key in self.config.missing:
                    existing_missing = self.config.missing.pop(old_mapping_key)
                    if new_mapping_key not in self.config.missing:
                        self.config.missing[new_mapping_key] = existing_missing

            playlist_entry["source_id"] = playlist_id
            changed = True
        if playlist_entry.get("source_url") != canonical_url:
            playlist_entry["source_url"] = canonical_url
            source_url = canonical_url
            changed = True
        if changed:
            self.config.save()

        plex_playlist_id = playlist_entry["plex_playlist_id"]
        playlist_name = playlist_entry["plex_playlist_name"]

        if source_type == "spotify":
            api = SpotifyAPI()
        else:
            api = AppleMusicAPI()

        plex = self._get_plex()

        print(
            f"\n→ Syncing '{playlist_name}' from {source_display_name(source_type)}..."
        )

        try:
            # Pass the stored/canonical URL to both sources. SpotifyAPI
            # extracts the playlist ID from the URL itself.
            source_tracks, metadata = api.get_playlist_tracks(source_url)
        except Exception as e:
            print(f"✗ Failed to fetch: {e}")
            return

        print(
            f"  Found {len(source_tracks)} tracks"
        )

        mapping_key = (
            f"{source_type}:{playlist_id}"
        )

        matched_tracks, unmatched, playlist_mapping, plex_library = (
            self._match_source_tracks(
                source_tracks,
                mapping_key,
            )
        )

        self._store_unmatched(
            mapping_key,
            unmatched,
        )

        self.config.mapping[mapping_key] = playlist_mapping

        print("\n→ Syncing to Plex...")

        # Only clear and rebuild if we have matched tracks
        if matched_tracks:
            # Rebuild the playlist in source order.
            # This guarantees that additions/removals/reordering
            # in the source playlist are reflected in Plex.
            print("  Clearing existing Plex playlist...")

            if not plex.clear_playlist(plex_playlist_id):
                print(
                    "⚠ Some existing playlist items could not "
                    "be removed."
                )
        else:
            print("⚠ No matched tracks - Plex playlist left unchanged")

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

        # Check if artwork URL was available
        image_url = metadata.get("image_url", "")
        if image_url:
            print("  → Artwork URL found in source")
        else:
            print("  ⚠ No artwork URL found in source")

        playlist_entry["last_synced"] = (
            datetime.now().isoformat()
        )

        self.config.save()

        if matched_tracks:
            print(
                f"✓ Sync complete!"
            )
        else:
            print("✓ Sync complete (no changes - no matched tracks)")

        if unmatched:
            print(
                f"⚠ {len(unmatched)} tracks were not "
                "added because they are unmatched."
            )



    def sync_all(self):
        """Sync all registered playlists."""

        if not self.config.config["playlists"]:
            print("✗ No playlists registered")
            return

        for playlist in self.config.config["playlists"]:
            self.sync_playlist(playlist)

    def edit_playlist_matches(self):
        """Edit existing matches for a playlist."""

        playlists = self.config.config["playlists"]

        if not playlists:
            print("✗ No playlists registered")
            return

        print("\nSelect playlist to edit matches:\n")

        for i, p in enumerate(playlists, 1):
            print(
                f"[{i}] {p['plex_playlist_name']} "
                f"({source_display_name(p['source'])})"
            )

        print("[b] Back")

        choice = input("\nSelect: ").strip().lower()

        if choice == "b":
            return

        try:
            idx = int(choice) - 1

            if 0 <= idx < len(playlists):
                self._edit_playlist_matches_interactive(
                    playlists[idx]
                )
                return

        except ValueError:
            pass

        print("✗ Invalid choice")

    def _edit_playlist_matches_interactive(
        self,
        playlist: dict,
    ):
        """Interactively edit matches for a playlist."""

        source_type = playlist["source"]
        source_url = Config._normalize_url_input(playlist["source_url"])
        playlist_id = Config._extract_id(source_url, source_type)

        if not playlist_id:
            print(f"✗ Could not extract playlist ID from: {source_url}")
            return

        mapping_key = f"{source_type}:{playlist_id}"

        if source_type == "spotify":
            api = SpotifyAPI()
        else:
            api = AppleMusicAPI()

        print(f"\n→ Fetching {source_display_name(source_type)} playlist...")

        try:
            # For Apple Music, pass the full URL; for Spotify, pass the ID
            if source_type == "applemusic":
                source_tracks, metadata = api.get_playlist_tracks(source_url)
            else:
                source_tracks, metadata = api.get_playlist_tracks(playlist_id)
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

        # Show current matches
        while True:
            matches_to_review = []

            for track in source_tracks:
                search_key = f"{track['title']}|{track['artist']}"

                if search_key in playlist_mapping:
                    plex_id = playlist_mapping[search_key]
                    matched_track = next(
                        (t for t in plex_library if t["plex_id"] == plex_id),
                        None
                    )

                    if matched_track:
                        matches_to_review.append({
                            'source': track,
                            'matched': matched_track,
                            'plex_id': plex_id,
                            'search_key': search_key,
                        })

            if not matches_to_review:
                print("✗ No existing matches to edit")
                return

            print(f"Showing all {len(matches_to_review)} matches:\n")

            for i, match in enumerate(matches_to_review, 1):
                src = match['source']
                matched = match['matched']
                album = matched.get("album", "")
                album_str = f" {colored(f'({album})', Colors.YELLOW)}" if album else ""
                
                src_title = colored(src['title'], Colors.CYAN)
                src_artist = colored(src['artist'], Colors.GREEN)
                matched_title = colored(matched['title'], Colors.CYAN)
                matched_artist = colored(matched['artist'], Colors.GREEN)
                
                print(
                    f"[{i}] {src_title} - {src_artist} {source_album_display(src)}"
                )

                print(
                    f"    → {matched_title} - {matched_artist}{album_str}"
                )

            print("\n[b] Back")
            print("[x] Exit")

            choice = input("\nEnter track number to fix: ").strip().lower()

            if choice == "b":
                return
            if choice == "x":
                sys.exit(0)

            try:
                idx = int(choice) - 1

                if 0 <= idx < len(matches_to_review):
                    match_to_fix = matches_to_review[idx]
                    self._fix_single_match(
                        match_to_fix,
                        plex_library,
                        playlist_mapping,
                        mapping_key,
                        playlist,
                    )
                    # Loop continues to show matches again
                    continue

            except ValueError:
                pass

            print("✗ Invalid choice")

    def _fix_single_match(
        self,
        current_match: dict,
        plex_library: List[dict],
        playlist_mapping: dict,
        mapping_key: str,
        playlist: dict,
    ):
        """Fix a single track match and sync to Plex immediately."""

        src = current_match['source']
        src_title = colored(src['title'], Colors.CYAN)
        src_artist = colored(src['artist'], Colors.GREEN)
        print(
            f"\n→ Fixing: {src_title} - {src_artist} {source_album_display(src)}"
        )
        
        current = current_match['matched']
        current_album = current.get("album", "")
        current_title = colored(current['title'], Colors.CYAN)
        current_artist = colored(current['artist'], Colors.GREEN)
        current_display = f"{current_title} - {current_artist}"
        if current_album:
            current_display += f" {colored(f'({current_album})', Colors.YELLOW)}"
        
        print(
            f"  Current match: {current_display}"
        )

        # Find candidates using fuzzy matching
        candidates = []

        for plex_track in plex_library:
            score = Matcher.candidate_score(
                src,
                plex_track,
            )

            candidates.append((score, plex_track))

        candidates.sort(key=lambda x: x[0], reverse=True)

        print("\nTop Plex candidates:\n")

        for i, (score, cand) in enumerate(candidates[:10], 1):
            marker = "→ " if cand["plex_id"] == current_match["plex_id"] else "  "
            album = cand.get("album", "")
            cand_title = colored(cand['title'], Colors.CYAN)
            cand_artist = colored(cand['artist'], Colors.GREEN)
            album_str = f" {colored(f'({album})', Colors.YELLOW)}" if album else ""

            score_details = Matcher.score_candidate(
                src,
                cand,
            )

            penalty_note = ""
            if score_details["album_penalty"]:
                kinds = ", ".join(
                    sorted(score_details["plex_album_types"])
                )
                penalty_note = (
                    f" [-{score_details['album_penalty']} {kinds}]"
                )

            print(
                f"{marker}[{i}] {cand_title} - {cand_artist}{album_str} "
                f"({score}%){penalty_note}"
            )

        print("\n[s] Skip")
        print("[d] Unlink this match")
        print("[b] Back")
        print("[x] Exit")

        choice = input("\nSelect correct match: ").strip().lower()

        if choice == "b":
            return
        if choice == "x":
            sys.exit(0)
        if choice == "s":
            return
        elif choice == "d":
            # Delete/unlink the match
            del self.config.mapping[mapping_key][current_match['search_key']]
            self.config.save()
            print(f"✓ Unlinked: {src_title} - {src_artist}")
            return

        try:
            ch = int(choice)

            if 1 <= ch <= len(candidates):
                selected = candidates[ch - 1][1]
                self.config.mapping[mapping_key][
                    current_match['search_key']
                ] = selected["plex_id"]
                self.config.save()

                print(
                    f"✓ Updated to: {selected['title']} - "
                    f"{selected['artist']}"
                )
                
                # Immediately sync this match to the Plex playlist
                plex = self._get_plex()
                if plex.add_to_playlist(playlist["plex_playlist_id"], selected["plex_id"]):
                    print(f"  ✓ Added to Plex playlist")
                else:
                    print(f"  ⚠ Could not add to Plex (may already exist)")

        except ValueError:
            print("✗ Invalid choice")

    def resolve_missing_interactive(self):
        """Interactive resolution of missing tracks."""

        playlists = self.config.config["playlists"]

        if not playlists:
            print("✗ No playlists registered")
            return

        playlists_with_missing = []

        for i, p in enumerate(playlists):
            mapping_key = (
                f"{p['source']}:{p['source_id']}"
            )

            if (
                mapping_key in self.config.missing
                and self.config.missing[mapping_key]
            ):
                playlists_with_missing.append((i, p))

        if not playlists_with_missing:
            print(
                "✓ No playlists with unmatched tracks"
            )
            return

        print(
            "\nPlaylists with unmatched tracks:\n"
        )

        for idx, (list_idx, p) in enumerate(
            playlists_with_missing,
            1,
        ):
            mapping_key = (
                f"{p['source']}:{p['source_id']}"
            )

            missing_count = len(
                self.config.missing[mapping_key]
            )

            print(
                f"[{idx}] {p['plex_playlist_name']} "
                f"({source_display_name(p['source'])}) - "
                f"{missing_count} unmatched"
            )

        print("\n[b] Back")
        print("[x] Exit")

        choice = input(
            "\nSelect playlist: "
        ).strip().lower()

        if choice == "b":
            return
        if choice == "x":
            sys.exit(0)

        try:
            idx = int(choice)

            if 1 <= idx <= len(playlists_with_missing):
                list_idx, playlist = (
                    playlists_with_missing[idx - 1]
                )
                self._resolve_playlist_missing(
                    playlist
                )
                return

        except ValueError:
            pass

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
                else source_id
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
                    item[2]["artist_score"],
                ),
                reverse=True,
            )

            displayed_candidates = candidates[:5]

            print(
                f"\n[{track_index + 1}/{len(unmatched)}] "
                f"{colored(track['title'], Colors.CYAN)} - "
                f"{colored(track['artist'], Colors.GREEN)} "
                f"{source_album_display(track)}"
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
                                details[
                                    "plex_album_types"
                                ]
                            )
                        )
                        penalty_note = (
                            f" [-{details['album_penalty']} "
                            f"{kinds}]"
                        )

                    print(
                        f"  [{i}] {cand_title} - "
                        f"{cand_artist}{album_str} "
                        f"({score}%){penalty_note}"
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

                    manual_candidates.append(
                        (
                            int(
                                round(
                                    details[
                                        "adjusted_score"
                                    ]
                                )
                            ),
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
                                    details[
                                        "plex_album_types"
                                    ]
                                )
                            )
                            penalty_note = (
                                f" [-"
                                f"{details['album_penalty']} "
                                f"{kinds}]"
                            )

                        print(
                            f"    [{i}] "
                            f"{match_title} - "
                            f"{match_artist}"
                            f"{album_str} "
                            f"({score}%)"
                            f"{penalty_note}"
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


def print_menu():
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
    print("[x] Exit")
    print("=" * 50)


def show_playlists(config: Config):
    """Show all registered playlists."""

    playlists = config.config["playlists"]

    if not playlists:
        print("\n✗ No playlists registered")
        return

    print("\nRegistered playlists:\n")

    for i, p in enumerate(playlists, 1):
        last_synced = p.get("last_synced")

        if last_synced:
            dt = datetime.fromisoformat(
                last_synced
            )
            sync_time = dt.strftime(
                "%Y-%m-%d %H:%M"
            )
        else:
            sync_time = "Never"

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
            f"    Last sync: {sync_time}\n"
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
    """Let user pick a playlist."""

    playlists = config.config["playlists"]

    if not playlists:
        print("\n✗ No playlists registered")
        return None

    print(
        f"\nSelect playlist to {action}:\n"
    )

    for i, p in enumerate(playlists, 1):
        print(
            f"[{i}] {p['plex_playlist_name']} "
            f"({source_display_name(p['source'])})"
        )

    print("[b] Back")
    print("[x] Exit")

    choice = input(
        "\nSelect: "
    ).strip().lower()

    if choice == "b":
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


def interactive_menu():
    """Main interactive menu."""

    config = Config()
    syncer = Syncer(config)

    while True:
        print_menu()

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
            playlist = pick_playlist(
                config,
                "sync",
            )

            if playlist:
                syncer.sync_playlist(playlist)

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
            print("\n[1] Reconfigure Plex")
            print("[b] Back")
            print("[x] Exit")

            settings_choice = input(
                "Select: "
            ).strip().lower()

            if settings_choice == "b":
                continue
            elif settings_choice == "x":
                sys.exit(0)
            elif settings_choice == "1":
                # Reconfigure only. This does not remove
                # existing playlist mappings.
                config.setup_plex()

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

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Run either the automated CLI action or the interactive menu."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

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
        syncer.sync_all()
        return 0

    interactive_menu()
    return 0


if __name__ == "__main__":
    sys.exit(main())