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
