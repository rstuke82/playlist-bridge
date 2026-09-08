# v2.0.0-beta.3

This release uses the version alone; there is no separate build number.

- Dashboard overview and statistics, bulk sync actions, and Add Playlist with durable progress and error feedback.
- Playlist filters, sorting, last sync/health timestamps, named health drift details, and global/local track search.
- Missing-track sorting, linked playlist memberships, explained counts, and selected or universal ignore rules with restoration.
- Persistent background jobs, manual execution, cron schedules with timezones, cancellation, and partial results.
- Settings General / Logs / Jobs sections, action filters and clear logs.

SQLite schema 3 preserves existing state and adds jobs and schedules. Stop the app and back up the complete data directory before upgrading. Restore that backup to roll back to beta 2. Docker continues to use port 8173 and /data. No image is published by this archive.

Cancellation stops at safe checkpoints and retains completed changes. The web service must remain running for schedules. Queued jobs resume after restart; interrupted running jobs are not replayed automatically. Matching heuristics and CLI behavior are preserved.

## Validation

- Python compilation and all 33 regression tests passed, including legacy JSON migration/counts, beta database upgrades, empty config, persisted read-only health, manual provenance, universal ignore, job cancellation/partial results, cron timing, and verified/partial add behavior.
- Frontend TypeScript/Vite production build passed.
- Browser checks covered dashboard statistics, incremental health results, named drift, favorite filters, ignore/restore, linked memberships, schedule creation/pause, background cancellation, add analysis/completion, and saved manual match replacement.
- Docker Compose configuration and local ARM64 multi-stage image build passed. Disposable containers verified port 8173 startup, beta 2 SQLite upgrade, and persisted health errors/logs after recreation with the same /data. Empty configuration initialized successfully.

Validation used deterministic service fixtures, not personal Plex or source-service accounts. The local image is playlist-bridge:2.0.0-beta.3; GHCR publishing and a multi-platform image are separate steps.

The archive includes complete project source, compiled frontend, Docker files, documentation and tests. Local test Python files remain gitignored as requested. Personal data and development dependencies are excluded.
