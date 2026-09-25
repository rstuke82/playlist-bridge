# Playlist Bridge 3.0 Beta 1

Package/image version: `3.0.0-beta.1`. Beta channel only. Default port: 8173.

- Plex PIN sign-in with server-owner bootstrap, individual-account access checks, opaque sessions and request forgery protection. Managed users are excluded.
- Separate SQLite playlist, matching, blocklist and job state for each account. Existing 2.x data stays with the server owner. Server tasks include member accounts and use their Plex tokens.
- Last.fm Discover, album search and top-album review, with shared metadata caching and saved-library availability checks. Add the server API key in Settings.
- Admin-controlled users, request permissions and opt-in shared playlist sources. Ordinary requests use the server's Lidarr defaults; service settings and credentials are not exposed.
- Admin Library comparison with scan times, album identity status, independent track counts and Plex/Lidarr links. Plex-only albums need attention once both scans exist.
- Separate artist, album and song fields for Lidarr lookup; selected-album MusicBrainz review link; recording search falls back to release dates when release-group dates are absent.
- Missing Plex destination preflight and strict read failures prevent destructive writes after a failed read. Explicit replacement preserves registration state and requires a confirmed missing destination and an available saved match.
- Backups include personal databases; restored sessions are invalidated and unfinished restored jobs are interrupted.

Upgrade: keep the existing data mount and configured Plex connection. The server owner signs in first. Last.fm requires an administrator-supplied API key. Personal user stores are under the same data mount. Back up the whole volume before upgrading or reverting to a 2.x image.

Scope: Last.fm review is album-based in this beta. Album identity and count checks are not proof of identical recordings. File deduplication/conversion is not implemented. External sign-in and services are mocked during automated validation and require a live smoke check on your server.

No backup folders, runtime databases, credentials or personal paths are included in published source/image/archive artifacts.

Validation: 69 focused backend tests cover account isolation, role/CSRF enforcement, cross-account job access, scheduled ownership, backups, year fallback and existing sync/Lidarr behavior. Production frontend build, Docker startup/authentication checks and admin/member browser smoke checks used temporary data. No live Plex/Lidarr writes were performed.
