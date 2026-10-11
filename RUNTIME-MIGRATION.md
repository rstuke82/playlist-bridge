# Web-only runtime migration

Released as build 20261011.1, based on build 20261010.12.
This report records the completed migration and validation.

## Final result

`playlist_bridge/legacy.py` and `sync.py` are deleted. The initially extracted
`cli.py` and `cli_syncer.py` are also deleted. Production code and tests now import
canonical domain modules directly. No implementation or compatibility facade
remains in legacy.py, and no interactive command-line workflow is shipped.

The existing `python -m playlist_bridge web` launcher and installed-version
command remain for Docker/native service operation. Docker and source packaging
no longer require sync.py. README instructions describe web-based operations.

## Removed interactive code

- All 25 methods from CLISyncer and the terminal menus/argument parser.
- Config._prompt_for_music_library, Config.ensure_plex_music_library and
  Config.setup_plex.
- Syncer.add_source (the old interactive addition path).
- Syncer._find_album_playlist_coverage, find_albums_without_playlist_tracks,
  find_albums_with_playlist_tracks and _artist_alias_owner (CLI-only helpers).
- Matcher.interactive_match and its unused candidate_score convenience method.
- Terminal index selection/favorite marker helpers and CLI-only timestamp helpers.

Config.get_plex now delegates to the existing validate_plex_config diagnostic
validator. Missing/invalid saved settings raise a useful Settings → Plex error,
without prompts, discovery calls, writes or credential disclosure. Syncing no
longer auto-selects a music library through this path; library selection happens
in Settings. Config._get_plex_music_libraries remains because the web Settings
page uses it for Test & Discover Libraries.

Web playlist addition/recreation, individual/all/favorite syncs, scheduling,
matching, aliases, job output and account isolation remain. SQLite schema and
old JSON import/backups are unchanged; those data migrations are unrelated to
the removed source compatibility module. Terminal formatting remains only for
shared background job output.

## Canonical modules

- `playlist_bridge/bootstrap.py`: Startup dependency validation.
- `playlist_bridge/runtime_paths.py`: Data paths and persisted schema identifiers.
- `playlist_bridge/atomic_files.py`: Durable atomic file writes.
- `playlist_bridge/process_lock.py`: Account-aware, cancellable locks for background work.
- `playlist_bridge/runtime_output.py`: Shared console and job output routing.
- `playlist_bridge/terminal.py`: Formatting retained for background job output; no interactive workflows.
- `playlist_bridge/text_utils.py`: Text repair and source labels.
- `playlist_bridge/config.py`: Account-scoped configuration and saved playlist state.
- `playlist_bridge/spotify_source.py`: Spotify playlist metadata and track extraction.
- `playlist_bridge/apple_music_source.py`: Apple Music playlist metadata and track extraction.
- `playlist_bridge/plex_client.py`: Plex library and playlist client.
- `playlist_bridge/matching.py`: Scoring, artist aliases, version guards and automatic matching.
- `playlist_bridge/sync_engine.py`: Playlist synchronization and saved matching state.

## Validation

- 644 backend tests passed: the 634 existing tests plus 10 runtime migration guards.
- All 8 frontend regression scripts passed.
- TypeScript/Vite production build passed; the existing >500 kB bundle warning remains.
- AST comparison against the released baseline verified 109 retained methods
  without implementation changes. Config.get_plex is the deliberate behavior
  change described above; sync_favorites also has a CLI reference removed from
  its docstring. Interactive methods were intentionally deleted.
- Guards verify no source/test imports of the deleted modules, no shipped CLI
  files or interactive helpers, no input() calls in the runtime, fresh-interpreter
  web startup, canonical class identity, saved Plex settings without discovery or
  writes, safe configuration errors without prompts, the web/version launcher,
  shared job output, and atomic-write failure recovery.
- Existing tests now import canonical classes/network helpers and patch the
  actual dependency-owning modules. Their prior assertions were retained.
- The no-prompt guard caught a leftover Matcher.interactive_match method in the
  first cleanup run. It was removed; the full backend rerun passed.
- Public source packaging was checked for integrity and absence of all four
  removed files, runtime databases, bytecode, node_modules and compiled assets.

Isolated Docker web startup, health and frontend serving passed on both published
architectures; all 644 backend tests also passed using the published ARM64 image.
External services, actual Plex synchronization and real-device/browser behavior
have not been exercised. The web engine remains
about 2,500 lines; additional domain decomposition can be considered separately.

## Exact source changes relative to released build 20261010.12

Added:

- `RUNTIME-MIGRATION.md`
- `playlist_bridge/apple_music_source.py`
- `playlist_bridge/atomic_files.py`
- `playlist_bridge/bootstrap.py`
- `playlist_bridge/config.py`
- `playlist_bridge/matching.py`
- `playlist_bridge/plex_client.py`
- `playlist_bridge/process_lock.py`
- `playlist_bridge/runtime_output.py`
- `playlist_bridge/runtime_paths.py`
- `playlist_bridge/spotify_source.py`
- `playlist_bridge/sync_engine.py`
- `playlist_bridge/terminal.py`
- `playlist_bridge/text_utils.py`
- `tests/test_runtime_migration.py`

Modified:

- `.dockerignore`
- `Dockerfile`
- `README.md`
- `playlist_bridge/__main__.py`
- `playlist_bridge/accounts.py`
- `playlist_bridge/album_finalize.py`
- `playlist_bridge/api.py`
- `playlist_bridge/availability.py`
- `playlist_bridge/backups.py`
- `playlist_bridge/description_refresh.py`
- `playlist_bridge/discover.py`
- `playlist_bridge/factory_reset.py`
- `playlist_bridge/inventory.py`
- `playlist_bridge/job_locks.py`
- `playlist_bridge/jobs.py`
- `playlist_bridge/library.py`
- `playlist_bridge/lidarr_requests.py`
- `playlist_bridge/local_library.py`
- `playlist_bridge/match_queue.py`
- `playlist_bridge/playlist_overlays.py`
- `playlist_bridge/queued_settings.py`
- `playlist_bridge/recreate.py`
- `playlist_bridge/settings_routes.py`
- `playlist_bridge/shared_playlists.py`
- `playlist_bridge/storage.py`
- `playlist_bridge/text_playlists.py`
- `playlist_bridge/track_bridge.py`
- `playlist_bridge/track_routes.py`
- `playlist_bridge/updates.py`
- `playlist_bridge/user_preferences.py`
- `scripts/package_source.py`
- `tests/test_22_beta2.py`
- `tests/test_22_beta3.py`
- `tests/test_30.py`
- `tests/test_30_beta2.py`
- `tests/test_30_beta3.py`
- `tests/test_30_beta4.py`
- `tests/test_availability.py`
- `tests/test_beta10.py`
- `tests/test_beta11.py`
- `tests/test_beta16.py`
- `tests/test_beta_workflows.py`
- `tests/test_build_20261008_13.py`
- `tests/test_credit_duration.py`
- `tests/test_discover_shelves.py`
- `tests/test_duration_recording.py`
- `tests/test_health_membership_fixes.py`
- `tests/test_history_request_links.py`
- `tests/test_match_choice_details.py`
- `tests/test_overlay_source_metadata.py`
- `tests/test_playlist_url_security.py`
- `tests/test_plex_import_recovery.py`
- `tests/test_recreate.py`
- `tests/test_request_album_availability.py`
- `tests/test_saved_inventory_reads.py`

Deleted:

- `playlist_bridge/legacy.py`
- `sync.py`

The intermediate cli.py and cli_syncer.py modules did not exist in the released
baseline; both were removed from this working migration. Synced sources and
existing released directories were untouched.
