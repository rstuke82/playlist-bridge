# Beta 7 implemented

- MusicBrainz lookup logging: persist INFO events for lookup start (artist, track/album, recording versus release-group), cache hit/miss/bypass, each attempt and retry delay, HTTP status/duration, candidate count, and applied release priorities. Log failures at ERROR with the upstream reason and request correlation; keep raw payloads/tracebacks at DEBUG with secrets redacted. Distinguish direct MusicBrainz lookups from normal Lidarr searches in Settings logs.
- Playlist Details filters: keep Needs Attention and restore Ignored, Manual, and Automatic. Clear filters shows all tracks. Do not restore separate Missing, LOST, or Legacy choices.
- Playlists page sorting: provide ascending and descending directions for each sort field, including the new Missing track count sort (ascending = fewest missing first; descending = most missing first).
- Add an album-specific Lidarr action beside the selected song preview, such as Add Dare to Lidarr. Open the shared Lidarr dialog and automatically search using the selected preview's artist and album (for example, The Human League - Dare), rather than the original source track's album. Keep album review before adding; do not change the source metadata or saved match.
- Preserve the selected preview, page filters, and scroll position when opening and closing the Lidarr dialog. Reuse the existing Lidarr request/status display rather than adding a duplicate status feature.
- Extend existing Lidarr request status with album-level download feedback: Searching, Waiting for download, Downloading (percentage and remaining size when available), Importing, Imported into Lidarr, and Blocked/Failed with the actual reported reason. Keep Imported separate from verified Available in Plex. Refresh visible active requests with shared, non-overlapping polling and slow down when idle; do not invent progress when Lidarr provides none.
- Add album-level download controls through Lidarr: Cancel download removes the selected download from the client without requesting an immediate replacement; Find another download removes and blocklists the failed release and searches for a replacement; Retry search starts a new search when no download is active. Confirm cancellation/replacement with the affected album and download clearly identified. Recheck current queue state before acting, prevent duplicate submissions, retain useful operation/error logs, and refresh status after the action. Cancellation does not unmonitor the album or guarantee it can never be grabbed later.
- Treat import failures separately from download failures: show Lidarr's reported cause and an Open in Lidarr action rather than automatically downloading again. Preserve already imported music and the album's registration when cancelling a queued download.

# Beta 6 implemented

- Apply saved release priority and studio preference consistently to both Lidarr and MusicBrainz results before limiting results.
- Label MusicBrainz as Advanced Lookup and offer reviewed Apple Music album suggestions when source album metadata is unavailable; never overwrite source metadata or automatically accept cross-service matches.

- Fix Track Details return navigation for every track entry point, not just previews: replace the hard-coded Back to Search link with the actual originating page (including the specific playlist). Restore that page's filters and scroll position. Preserve origin through preview/matching actions and refresh where possible, support browser Back, and use Search only as a fallback for direct links with no recorded origin.
- Make Track Details actions consistent with Missing and Playlist Details: add Ignore with explicit selected-playlist/universal scope, Add Album to Lidarr using the shared dialog, and persistent request status. Album lookup/preview should not require playlist selection. Explain why matching actions are disabled (loading versus no selected playlists), place selection guidance beside the actions, and preselect the sole playlist when only one membership exists; keep multi-playlist scope explicit to prevent unintended global edits.
- Simplify playlist-detail filtering to All and Needs Attention only, consistent with the other playlist views. Needs Attention includes actionable missing/LOST and applicable error or mismatch states; ignored tracks are not attention items merely because they are ignored.
- Fix song-preview navigation: opening a preview must keep the user in their originating playlist/detail/match context instead of stranding them on Search. Preserve originating route, filters, scroll position and selected track; provide a reliable return action wherever navigation is necessary, including browser Back behavior.
- Improve song preview placement: put a Preview action near the source track heading in match review instead of below the candidate list. Open catalog choices and the player in an inline expandable panel directly below that heading, with a compact mobile sheet if space requires it. Keep preview controls accessible without scrolling through candidates, preserve candidate selection and scroll position, and stop/unmount playback when closed or changing tracks. Avoid stacking another modal over the match dialog. No matching changes.

# Beta 5 implemented

- Prefill Lidarr album search with Artist - Album when album metadata is available; fall back to Artist - Track when it is unavailable.
- Add a per-search bypass-cache option to request fresh results from the selected search service instead of Playlist Bridge's cached results. Preserve normal caching by default and respect service rate limits; this cannot bypass caches controlled by Lidarr or upstream providers.
- Add Playlist Bridge branding to the header and sidebar: musical-note bridge mark, compact sidebar icon and header wordmark, with accessible light/dark contrast and small-size legibility. Production mark implemented as an SVG component from the saved concept.
- Enrich Already in Lidarr results with monitored status and offer Search Album directly.
- Collapse root folder, profiles, monitoring and tags under Options, using Settings defaults.
- Keep search results visible during retries with inline search progress.
- Improve Plex sync verification diagnostics: report missing track titles/artists alongside Plex IDs and expected/retained occurrence counts; capture relevant Plex response details with credentials redacted. Clearly distinguish saved match edits from a failed follow-up sync, and duplicate collapse from entirely absent tracks. The observed HTTP 400 cannot be attributed to a specific server cause from the old log; future failures now include response details. Unmatched source tracks remain non-fatal.

Beta 4 prioritizes persistent Requested in Lidarr indicators and accurate partial-success handling with Retry Search.

# 2.2 multi-user plan

- Support individual Plex accounts with access to the configured server; no managed Plex Home users.
- Users authenticate through Plex sign-in (PIN/token flow); no user-entered MusicBrainz or Lidarr credentials/settings.
- MusicBrainz cache is server-wide and shared across users. MusicBrainz and Lidarr settings are admin-only, hidden from ordinary users and excluded from their API responses.
- Each user owns their playlists. Scheduling is server-wide and admin-controlled: Sync Auto Sync Playlists processes enabled playlists across all users, using each owner's Plex account. No personal schedules.
- Present album acquisition as Request Album, with helper text explaining it requests addition to the Plex library. Keep Lidarr implementation/configuration behind the scenes; admin controls request permissions.
