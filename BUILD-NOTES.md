# Playlist Bridge 3.0 Beta 3

Package/image version: `3.0.0-beta.3`. Beta channel only; port 8173 unchanged.

- Discover shows saved-user top albums and Trending as separate sections. Both apply artist blocks and Hide Available Albums.
- Lidarr album identifiers take priority over title matching. Administrators can link a Discover album to an existing scanned Lidarr album; links apply across accounts. Plex remains the playback/track-match check. Availability is still a snapshot, not a live guarantee of edition completeness.
- Playlist sorting includes Date Added and Reverse Sort. Three-dot and bulk actions offer Follow Server Schedule and Manual Only; selected schedules update without waiting for a running sync. Existing custom schedules are replaced only for selected playlists.
- Shared playlists are visible to users, with read-only source previews and album availability. Already subscribed or queued sources are hidden per account; the user section disappears when empty. Publishing remains administrator-only.
- Apple Music service names decode correctly and lose the service suffix. Known automatic names are cleaned; custom names are preserved. Older shared entries without naming provenance receive display-only cleanup.
- Selected album results include an inline request button. User request dialogs close after submission and track details update their request status.
- Settings → Users supports administrator promotion, playlist/request permissions, automatic approval, download visibility and download management. Promoted users retain their own playlists and Plex credentials. The owner cannot be demoted/disabled, and the last administrator is protected. Download visibility/management grants access to server request downloads; integration credentials/settings stay private.
- Administrators can approve/decline pending requests and remove completed/inactive Bridge request records. Removal leaves Lidarr albums, files and downloads intact. Active Bridge request jobs must finish first.
- Duplicate-track play queues use the ordered-list URI supported by PlexAPI with an explicit client identifier, avoiding one queue-add call per occurrence. The returned order/count is verified before use; unsupported responses fall back to standard additions. Detailed fallback diagnostics stay in DEBUG. Plex may still collapse duplicates.

Upgrade: retain the existing data mount. SQLite schema remains compatible; new preferences and associations use existing state tables. Existing user permissions keep their previous behavior until edited. CLI and stable main/latest remain unchanged.

Validation: Python compilation and frontend production build; seven focused checks for account isolation, permissions, schedule selection, shared-source visibility, name cleanup, manual linking and safe request deletion. External media changes were not exercised. Full regression, browser and container smoke-test suites were intentionally skipped for this beta.

No backups, runtime databases, credentials or personal paths are included in published artifacts.
