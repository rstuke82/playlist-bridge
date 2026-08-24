# Changelog

All notable changes to Playlist Bridge are documented here.

## [1.3] - 2026-08-24

### Added

- Added per-playlist permanent track ignores in Option 5 and Option 6.
- Added `[i] Ignore permanently` while resolving missing tracks or editing an existing match.
- Added `ignored_tracks.json` for persistent per-playlist ignore state.
- Added Settings → **Manage ignored tracks** to restore individual ignored tracks or all ignored tracks for a playlist.
- Added per-playlist `Auto sync` ON/OFF state.
- Added Settings → **Manage auto-sync**.
- Added one-time/manual-only playlist behavior while keeping the playlist fully registered.
- New playlists now ask whether they should participate in automatic `--sync-all` / cron runs.
- Added Auto sync status to registered-playlist and manual-sync displays.
- Added `Ignored` count to sync summaries.

### Changed

- Automated `python sync.py --sync-all` now skips playlists whose Auto sync setting is OFF.
- Interactive **Sync all playlists** remains an explicit manual action and continues to sync every registered playlist.
- Interactive **Sync specific playlist** remains available regardless of Auto sync state.
- Existing playlists with no `auto_sync` field default to Auto sync ON.
- Permanently ignored tracks no longer participate in matching, unresolved lists, or destination Plex playlist construction.
- Ignoring an already-matched track removes its saved mapping and provenance.
- Restoring an ignored track makes it eligible for normal matching on the next sync.
- State schema advanced from 1 to 2.
- Schema 2 adds ignored-track state and optional per-playlist automatic-sync state.
- Existing schema-0 and schema-1 state migrate to schema 2 using the existing one-time backup mechanism.
- Dry run remains fully read-only, including ignored-track state and schema migration.

### Compatibility

- No reset is required when upgrading.
- Existing playlists default to Auto sync ON.
- Existing matching, missing-track, provenance, and source-snapshot data remains compatible.
- Older state files receive `.pre-schema-2.bak` backups before the first schema-2 rewrite.

## [1.22] - 2026-08-24

### Added

- LOST tracks now retain the previous Plex track ID and, when known, previous title, artist, album, and provenance.
- LOST status and previous-match details remain visible during manual unmatched-track review.
- Existing valid mappings learn a destination metadata snapshot for future LOST reporting.
- Added a read-only Developer Tools report for Plex albums with zero tracks on any Plex audio playlist.

### Changed

- Legacy mapping validation now runs only for mappings whose provenance is actually `legacy`.
- When the current automatic matcher independently chooses the exact same Plex track as a valid legacy mapping, that mapping is promoted to `automatic`.
- Legacy mappings remain unchanged when the current matcher disagrees or cannot confidently match.
- Manual and already-automatic mappings are not reclassified by the legacy-validation path.
- Dry run does not promote legacy mappings or write provenance changes.

## [1.2] - 2026-08-22

### Added

- Added sync-to-sync source playlist tracking with `ADDED` and `REMOVED` reporting.
- Added mapping-state tracking with visible `NEW` and `LOST` markers.
- Added an end-of-sync summary showing source tracks, matched tracks, new matches, lost matches, source additions/removals, and unresolved tracks.
- Added lightweight persistent source snapshots in `source_snapshots.json`.
- Added match provenance in `match_metadata.json` with `automatic`, `manual`, and protected `legacy` states.
- Added **Clear automatic matches** in Settings, preserving manual and legacy mappings.
- Added a deduplicated **All missing tracks** view across all registered playlists.
- Added **Last match attempt** timestamps to Option 5 and sort unresolved-playlist triage oldest first, with `Never` first.
- Added multi-playlist selection to Option 3 using comma-separated selections and ranges such as `1,3,5` or `1-3`.
- Added `--sync-all --dry-run` for read-only source fetching, Plex scanning, matching analysis, and change reporting.
- Added persistent JSON schema versioning independent of the application version.
- Added automatic schema-0-to-schema-1 migration for existing unversioned state.
- Added one-time pre-migration backups such as `mapping.json.pre-schema-1.bak`.
- Added protection against loading/writing state created by a newer unsupported schema.
- Added Spotify public-track ID fallback using the track URI when an explicit track ID is absent.

### Changed

- Playlists shown with **Last sync** are sorted `Never` first, then oldest to newest.
- Registered playlist display is also ordered oldest-last-sync first.
- Option 5 Back now returns to the unresolved-playlist list instead of the main menu.
- Submenus that show `[b] Back` also treat an empty Enter as Back.
- Option 6 now displays automatic/manual/legacy provenance counts and per-track provenance.
- Explicit candidate choices and confirmations in Options 5 and 6 are stored as manual mappings.
- Stale manual and legacy mappings are no longer silently replaced by a new automatic guess.
- Improved matching for explicit demo, acoustic, live, remix/mix, and branded session recordings.
- Branded iTunes, Apple Music, and Spotify sessions are treated as distinct recording intent.
- Generic album-era labels such as `Evolver Sessions` are treated as provenance rather than automatically as branded-session recording intent.
- Featured-artist metadata remains symmetric and does not by itself create recording-version intent.
- Prevented album bonuses from canceling unwanted title-level recording-version penalties.
- Playlist metadata text is repaired before being sent to Plex.
- Meaningful source playlist descriptions are preserved, while generic descriptions such as `Playlist · 86 Songs` are omitted.
- Source snapshots and match metadata participate in stored-state migration and normal saves.
- Dry runs remain fully read-only, including schema migration state.

### Fixed

- Fixed cases where a plain featured-artist recording could tie with or lose to an unwanted acoustic copy because an album bonus canceled the acoustic penalty.
- Fixed explicit demo requests collapsing to standard studio versions.
- Fixed branded session requests collapsing to studio recordings.
- Fixed named mix/remix and acoustic intent collapsing to plain recordings.
- Fixed generic `Sessions` text being over-classified as a distinct branded session recording.
- Fixed common playlist-description mojibake such as `Playlist Â· 86 Songs`.
- Fixed Option 5 submenu navigation returning too far up the menu hierarchy.

### Compatibility

- Existing 1.1 `config.json`, `mapping.json`, and `missing_tracks.json` files load without reset.
- Existing saved mappings are treated as `legacy` because pre-1.2 state did not record provenance.
- Legacy JSON is migrated only on the next normal save; dry run does not rewrite it.
- Existing state files receive one-time pre-schema-1 backups before migration.

### Notes

- `--sync-all` remains fully non-interactive.
- Public `--help` advertises `--sync-all` and `--dry-run`.
- Public Spotify and Apple Music playlist support remains API-key-free.
- Playlist Bridge remains licensed under GPL-2.0-only.

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
