# Playlist Bridge 2.2 Beta 1

Package/image version: `2.2.0-beta.1`. Default port: 8173. Published to beta only; main/latest remain on 2.1.0.

- Configurable hourly media availability scans with manual Run Now, midnight-aligned schedules, and overlap prevention.
- Fresh Plex library scans, shared short-lived snapshots for routine sync, deduplicated missing-track lookups, preserved manual matches and ignored tracks.
- Batched updates for affected Auto Sync playlists; Ready to Sync for other playlists.
- Requested-track availability distinguished from Lidarr import status.
- Requests navigation moved below Dashboard with its own icon; album-result alignment and Lidarr album/download links improved.
- Unchanged track order skips Plex track-list writes. Source fetching, metadata updates, and destination verification remain active.

SQLite uses existing state storage; existing schedules retain their settings and gain one availability task. Existing data mounts, CLI support, and matching thresholds are retained. Runtime data and backups are excluded from published artifacts.

Frontend and Python syntax checks and focused availability, scheduling, cache, match-workflow and Lidarr tests passed. No live Plex/Lidarr writes were used for validation. Measure timings on your library before assuming a particular speedup.

The historical Beta 4 suite is not a passing validation for this build: it still expects schema 3 instead of the existing schema 4, and its detail-handler mock has an outdated function signature. The stalled historical test was stopped.
