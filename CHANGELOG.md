# Changelog

All notable changes to Playlist Bridge are documented here.

## [1.1] - 2026-08-20

### Added

- Option 3 now shows the last sync time beside each registered playlist.
- Option 5 now shows the full unresolved-track list before triage starts.
- Option 6 now shows the current saved-match count beside each playlist.
- Settings now includes **Clear matching for a playlist**.
- Matching can be cleared for one playlist or for **all playlists** with explicit confirmation and a summary of how many saved matches and unresolved records will be removed.

### Changed

- Renamed **Reconfigure Plex** to **Configure Plex**.
- Option 6 now saves match edits first and offers one full playlist sync when editing is complete instead of modifying Plex one corrected track at a time.
- Artwork discovery/fetching is skipped during Options 5 and 6 and runs only during actual playlist creation or synchronization.
- Clearing matching resets entries in `mapping.json` and `missing_tracks.json` while leaving playlist registrations and Plex playlists unchanged.

### Notes

- `--sync-all` remains fully non-interactive.
- Existing saved mappings continue to be respected unless they are explicitly cleared.
- Playlist Bridge remains API-key-free for public Spotify and Apple Music playlists.

## [1.01] - 2026-08-20

### Added and improved

- Improved parenthetical-title handling.
- Improved featured-artist and collaborator normalization.
- Added remix/live title intent handling.
- Improved soundtrack and `Various Artists` track-artist matching.
- Added common mojibake/text-encoding repair.
- Hid interactive candidates scoring below 50%.
- Improved preference for canonical studio-album copies.
- Kept automatic and manual match scoring more consistent.

This was the first formal GitHub release of Playlist Bridge.
