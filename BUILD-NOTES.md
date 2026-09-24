# Playlist Bridge 2.2 Beta 3

Package/image version: `2.2.0-beta.3`. Beta channel only; default port 8173. Stable main/latest remain on 2.1.0.

- One global Sync Playlists task and one all-playlist, read-only Health Check task.
- Server schedule, Custom schedule, or Manual only per playlist. Custom runs remain independent when the global task is disabled.
- Favorites and Auto Sync flags removed from the web interface. Explicit Sync Now, Sync Selected, and Sync Filtered actions retain manual control.
- Retry Missing Matches marks Ready to Sync and follows the configured schedule instead of creating another automatic sync path.
- Rename playlists in Bridge and Plex, preserve custom names across syncs, restore source names, and choose a destination name when adding. Duplicate titles remain separate by source and Plex IDs.
- Plex descriptions retain source text and include one replaceable successful-sync summary with the source link, timestamp, and track counts.
- Stale Lidarr album IDs are cleared or relinked by release-group identity. Missing albums offer Add Album Again instead of a stale Open/Retry link.

Upgrade: custom schedules and disabled playlists are preserved. Use an enabled general sync frequency, otherwise an enabled Auto Sync frequency; favorites-only tasks do not enable the new global task. Retire scoped health tasks and retain an existing all-playlist health frequency. Conflicts appear as migration notes in Tasks. Job history and SQLite schema compatibility are preserved.

No personal paths, backups, credentials, or runtime databases are included in release artifacts. No live Plex/Lidarr writes are used for validation.

Validation: 54 focused backend tests, fresh-database startup and task/API checks, Python compilation, and the production frontend build passed.
