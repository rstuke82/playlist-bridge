# Roadmap

Planned future changes. Completed release details are documented in [CHANGELOG.md](CHANGELOG.md).

## 2.2 — Multi-user support

- Support individual Plex accounts with access to the configured server; no managed Plex Home users.
- Users authenticate through Plex sign-in (PIN/token flow); no user-entered MusicBrainz or Lidarr credentials/settings.
- MusicBrainz cache is server-wide and shared across users. MusicBrainz and Lidarr settings are admin-only, hidden from ordinary users and excluded from their API responses.
- Each user owns their playlists. Scheduling is server-wide and admin-controlled: Sync Auto Sync Playlists processes enabled playlists across all users, using each owner's Plex account. No personal schedules.
- Present album acquisition as Request Album, with helper text explaining it requests addition to the Plex library. Keep Lidarr implementation/configuration behind the scenes; admin controls request permissions.

- Add admin-managed universal playlists available across users, using server-controlled sync. Decide automatic assignment versus opt-in before implementing distribution.

## 3.0 — Last.fm discovery

- Import music from Last.fm to identify gaps in the user's Plex music library. Decide which Last.fm collections/history and import ranges to support during feature design.
- Match imported tracks against the configured Plex library and existing saved matches before presenting missing music. Reuse track identity, version handling, and manual-match rules; distinguish confirmed Plex matches, uncertain candidates requiring review, and missing tracks. Do not treat incomplete Last.fm album metadata as proof that music is missing.
- Deduplicate imported entries for missing-music review while retaining their Last.fm origin. Allow users to review or fix matches and request missing albums through the existing acquisition workflow; importing alone must not automatically request downloads.
