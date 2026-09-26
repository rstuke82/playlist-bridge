# Playlist Bridge 3.0 Beta 2

Package/image version: `3.0.0-beta.2`. Beta channel only. Default port: 8173.

- Admin Activity shows all users’ jobs, owner filters, detailed output and cancellation. Independent account jobs run with a maximum of two workers; the same account or actual Plex playlist is serialized. Maintenance/restore jobs remain exclusive.
- Settings → Users consolidates permission controls and imports eligible full Plex accounts as pending users. Users authenticate with their own Plex credentials; imports never inherit the administrator’s token.
- Sync Now applies the selected playlists’ queued match edits first and syncs each destination once. Validation uses a fresh Plex snapshot reused by the ensuing sync. Stored mappings and last-validated health counts have distinct labels.
- Plex snapshots remain cached separately by credentials/library. Network reads for independent accounts no longer hold a global cache lock. Bounded normalization caches reduce repeated matcher work; live/remix safeguards and thresholds remain intact.
- Plex scans detect changed inventory and queue one missing-match retry, respecting service preferences. Successful matching marks playlists Ready to Sync for their normal schedule/manual sync.
- Persistent Source History records detected additions/removals and occurrence-count changes after an initial baseline. Failed and empty source responses retain the baseline.
- Saved Last.fm usernames use the shared server key. Discover spreads trending albums across more artists, remembers Hide Available Albums and excludes blocked artists from fresh/cached results. Blocklist is the single ignored-track/artist management location.
- Clickable artists and albums open internal details with return navigation, availability explanations, available Lidarr release-selection metadata and service links. Album cards use compact status icons and tighter spacing. Uncertain associations and stale scans remain explicit.
- Candidate query-match percentages preserve edition qualifiers. MusicBrainz release-group links sit at the top right of album results for admin and regular-user request flows. Server settings support a custom MusicBrainz URL with separate caches.
- Configurable global task start times, scheduled backup retention of 1/3/7, and confirmed backup deletion. Plex descriptions show readable successful-sync timestamps and next scheduled sync; schedule edits queue description-only updates without changing the last sync time.
- Shared-source form alignment and source-name lookup, readable radio/checkbox labels, and specific View Activity links. Polling backs off quietly after transient failures. Job submission receipts reconcile a lost response without resubmitting the operation.
- Conservative primary-artist collaboration matching handles the reviewed Zedd/Maren Morris/Grey single example when title and album support it; artist-credit reasoning is exposed with candidate diagnostics.

Upgrade: retain the existing data mount and Plex settings. Existing SQLite schema 4 is preserved; new state uses its existing tables. The server owner signs in first after a pre-3.0 upgrade. Backups include personal databases; restore invalidates sessions. CLI, Docker/GHCR and port 8173 remain supported.

Limits: external services are mocked during automated checks, so live Plex sign-in/import and real Lidarr/Plex changes still need validation on your server. Availability is based on completed scans and conservative artist/album associations, not proof of an identical recording or downloaded edition. Artist exclusions use identities and credits supplied by the source. Source History cannot reconstruct older changes, and empty source responses are intentionally not treated as removals. Further candidate indexing, explicit album associations, full Last.fm history import and file management remain future work.

No backups, runtime databases, credentials or personal paths are included in published artifacts.

Validation: Python compilation, production frontend build and 84 focused backend checks passed. Browser checks covered phone-width Discover/task layouts and regular-user navigation using isolated fixture data. External services were mocked; no real Plex/Lidarr media was changed.
