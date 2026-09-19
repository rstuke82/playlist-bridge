# Roadmap

Planned future changes. Completed release details are documented in [CHANGELOG.md](CHANGELOG.md).

## Next version — Media availability checks and faster playlist updates

- Add a scheduled Check Media Availability task to bridge the gap between Imported into Lidarr and Available in Plex. Default to hourly, aligned to midnight, with the existing task controls and manual Run Now action. Manual runs do not shift the schedule; skip overlapping runs.
- Refresh statuses for requested albums and check missing tracks against the Plex library, reusing one library load across the run. Retry the existing automatic matcher without changing thresholds, preserve manual matches, and send uncertain candidates to review.
- Batch newly matched tracks into one queued sync per affected Auto Sync playlist. Mark other affected playlists Ready to Sync rather than syncing them automatically.
- Distinguish an imported album from an available requested track: imports may be incomplete or contain a different recording. Confirm track availability in Plex before marking it available.

- Make playlist sync reuse availability results and a shared Plex library cache, with freshness checks and invalidation for deleted or changed Plex items. Scheduling availability checks alone must not be treated as a performance improvement without this reuse.
- Reuse validated saved matches and match only new, changed, or previously missing tracks. Check each unique missing track once across playlists while preserving playlist-specific mappings and manual selections.
- Continue fetching source playlists to detect additions, removals, reordering, and duplicate occurrences. Skip Plex writes only when the desired contents and order already match, respecting existing duplicate handling.
- Measure source fetching, Plex library loading, matching, and playlist writes before and after the changes. Use those measurements to confirm routine-sync improvements without promising a fixed speedup or sacrificing correctness.

## 3.0

### Multi-user support

- Support individual Plex accounts with access to the configured server; no managed Plex Home users.
- Users authenticate through Plex sign-in (PIN/token flow); no user-entered MusicBrainz or Lidarr credentials/settings.
- MusicBrainz cache is server-wide and shared across users. MusicBrainz and Lidarr settings are admin-only, hidden from ordinary users and excluded from their API responses.
- Each user owns their playlists. Scheduling is server-wide and admin-controlled: Sync Auto Sync Playlists processes enabled playlists across all users, using each owner's Plex account. No personal schedules.
- Present album acquisition as Request Album, with helper text explaining it requests addition to the Plex library. Keep Lidarr implementation/configuration behind the scenes; admin controls request permissions.

- Add admin-managed universal playlists available across users, using server-controlled sync. Decide automatic assignment versus opt-in before implementing distribution.

### Last.fm discovery

- Import music from Last.fm to identify gaps in the user's Plex music library. Decide which Last.fm collections/history and import ranges to support during feature design.
- Match imported tracks against the configured Plex library and existing saved matches before presenting missing music. Reuse track identity, version handling, and manual-match rules; distinguish confirmed Plex matches, uncertain candidates requiring review, and missing tracks. Do not treat incomplete Last.fm album metadata as proof that music is missing.
- Deduplicate imported entries for missing-music review while retaining their Last.fm origin. Allow users to review or fix matches and request missing albums through the existing acquisition workflow; importing alone must not automatically request downloads.
