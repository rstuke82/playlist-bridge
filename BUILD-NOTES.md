# v2.0.0-beta.2 — build 20260908.7

## Changes

- Health checks show a spinner, per-playlist running message, numbered Check All progress, and completion/failure counts. Progress survives page navigation and each result appears when finished.
- Plex connectivity, invalid URL, timeout, TLS, authentication, wrong-server response, and missing-resource failures have actionable messages. Health errors link to Settings and persist across refresh/restarts. Last successful metrics remain intact and are explicitly labeled.
- Strict Plex reads are used for health checks so an HTTP failure cannot masquerade as an empty destination playlist. The default CLI read behavior and matching heuristics remain unchanged.
- Settings now includes persistent application logs with Refresh and level filters. It retains the newest 1,000 entries and shows up to 200. Captured web sync output and health diagnostics are included; recognized credentials and Plex tokens are redacted. It is not an importer for historical CLI or Docker console logs.
- Match selection now has a separate Save Match step. Cancel and Close remain visible outside the scrolling candidate list. Escape and backdrop dismissal work before save, including while candidates load. Once Save Match is submitted, controls indicate saving/syncing until the operation finishes.
- Both Missing and playlist details use the shared match picker. Selected/all unresolved occurrences and manual provenance are preserved.
- Playlist details consistently highlight Playlists in the sidebar, and Back to playlists returns to the registered list. Hash routes support refresh, browser history, and old beta 1 detail bookmarks.

## Upgrade and deployment

Version: 2.0.0-beta.2. Build: 20260908.7. Docker port remains 8173 and persistent data remains under /data. Docker/GHCR structure is unchanged. No image was published to GHCR.

SQLite schema 2 adds the application_logs table. Existing beta 1 state, health results and legacy migration backups are preserved. Failed health attempts live in a separate state namespace and do not change sync state. Stop the app and back up the complete data directory before upgrading. Beta 1 cannot open schema 2; restoring the backup is required for rollback.

## Validation

- Python compile and 17 regression tests passed.
- Tests cover empty/partial config, legacy import, beta 1 database upgrade, retained mappings/snapshots/last_synced, failed health persistence, recovery, HTTP authentication/resource errors, connection/timeout/TLS diagnostics, wrong-server responses, log redaction/filtering/retention, and existing manual-match behavior.
- Frontend TypeScript/Vite production build passed.
- Browser verified running indicators, numbered incremental batch progress across navigation, actionable wrong-URL errors and Settings logs, configuration recovery, persistent timestamps, Cancel during candidate loading, unsaved candidate selection, Escape dismissal, and correct back-link/sidebar behavior.
- Docker Compose configuration and the local multi-stage Docker image build passed.
- Container smoke tests verify HTTP startup on 8173, beta 1 SQLite upgrade, and logs/failed health attempts across recreation with the same disposable /data mount.

Service behavior was tested using deterministic fixtures, not personal Plex/Spotify/Apple Music accounts. The locally built Docker image targets the host architecture; a public multi-platform build is a separate publishing step.

The full archive includes source, compiled frontend assets, Docker files, documentation and tests. It excludes personal data and development dependencies.
