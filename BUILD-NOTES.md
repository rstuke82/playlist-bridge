# v2.0.0-beta.1 — build 20260908.6

This build adds SQLite storage, persistent playlist health, and playlist details with Fix Match. The version stays exactly 2.0.0-beta.1. Docker/GHCR layout and port 8173 remain unchanged.

## Storage

`playlist_bridge/storage.py` provides a transactional repository. Schema 1 uses a namespaced state table (one row per legacy top-level key), a health history table, and durable migration backups. Nested records retain their existing shapes to preserve matching/CLI compatibility. Config is the compatibility facade used by the existing sync engine; runtime reads/writes now go through the repository.

Legacy JSON import validates exact decoded data equality in one transaction. Failed imports roll back and can be retried. Successful imports preserve original bytes in SQLite and `.pre-sqlite.bak` files. Legacy state files are no longer live. Startup config retains only Plex/server/data directory settings. Missing, blank, empty-object and partial config launch successfully.

Health writes touch only health records/history. Sync, mapping, missing, provenance, snapshot and last-synced state are unchanged by health checks. First startup initializes/migrates storage, including when invoked through CLI dry-run.

## Interface

Each playlist has collapsible health metrics, placeholders, and Last updated. Dashboard checks update one playlist at a time and persist across navigation/refresh/restarts. Playlist-name links open source tracks and current saved Plex matches, with provenance/status. Fix Match and Review Match support ranked candidates and manual text search. Fixes retain manual provenance and sync only the current/selected affected playlists.

## Validation

- Python compile and 9 backend regression tests passed, including seven empty/partial-config cases.
- Disposable schema-wrapped and plain legacy fixtures: exact value preservation, 10 state rows, integrity check, backups, idempotence, and failure/retry passed.
- Health non-mutation test used the real matcher and deterministic source/Plex fixtures.
- Playlist detail and manual replacement tests passed, including selected unresolved occurrences and exclusion of unaffected playlists.
- Browser verified placeholders, populated health timestamp, detail view, candidate selection, changed Plex display, Manual provenance, and persistence after refresh/navigation.
- Frontend TypeScript/Vite production build passed.
- Docker Compose configuration and Docker multi-stage build passed. Two disposable containers verified empty-config startup and health persistence across container recreation using the same `/data` mount.

Live Spotify/Apple Music/Plex network integration was not exercised against a personal server. Service fixtures were used for behavioral tests. No GHCR image was published by this build.
