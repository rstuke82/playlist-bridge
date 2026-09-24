# Playlist Bridge 2.2 Beta 2

Package/image version: `2.2.0-beta.2`. Default port: 8173. Beta channel only; main/latest remain on 2.1.0.

- Persistent full Plex and Lidarr inventories, service-scoped caching, and read-only availability reconciliation.
- Separate scan and missing-match retry tasks; scan preferences live under their service settings.
- Requests require a download queue entry for In Progress; added but unimported albums without downloads need attention.
- Durable, latest-value-wins playlist setting changes avoid lock errors during active jobs.
- Per-playlist weekly schedules, server timezone, overlap prevention, and unchanged schedules after manual runs.
- Include/exclude/off filters and Ready to Sync for pending match changes.
- Conservative matching normalization for standalone ampersands, leading artist “The”, apostrophes, and Unicode accents. Recording-version safeguards and thresholds remain intact.

SQLite schema 4 and existing data mounts remain compatible. CLI, port 8173, and Docker architecture are retained. Backups and runtime data are excluded from publishing. No live Plex or Lidarr writes are used in validation.
