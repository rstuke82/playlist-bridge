# Playlist Bridge 3.0 Beta 5

Package/image version: `3.0.0-beta.5`. Default port: 8173. Beta channel only.

## Local music library preview

- Opt-in, read-only scanning of mounted music folders, independent of Lidarr.
- Scheduled Local Music Library Scan task, disabled by default.
- Reuse unchanged file metadata; retain the previous inventory if a root becomes inaccessible.
- Unified local albums and explicitly loaded MusicBrainz artist catalogs, with release-type and availability filters.
- Review album editions and individual recording associations without altering file tags.
- Completeness checks use recording/edition identities rather than file counts alone.
- Optional path mappings connect local files to account-visible Plex tracks.
- Local-mode matching, Discover and Requests availability use the local inventory; existing playlist mappings remain intact.

## MusicBrainz edition preferences

Rank release countries (for example US, XE, XW) and media formats (Digital Media, CD), with an optional official-release preference. Release-group priorities remain separate. These are soft preferences: alternatives remain available and existing files are not relabeled.

## Upgrade and setup

1. Update the Docker beta image normally; SQLite state is retained.
2. To use local mode, set `MUSIC_LIBRARY_PATH` to a host music folder in your private `.env`, then start with `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d`.
3. In Settings → Local Library, add `/music`, optionally map its Plex path, enable local mode, and save.
4. Run Scan Local Music Library and Scan Plex Library under Settings → Tasks.
5. Load MusicBrainz artist/edition metadata from Library when needed. Unidentified files appear under Needs Attention.

Lidarr remains the default until local mode is enabled. This preview does not import downloads, move files, rewrite tags, or provide native Soulseek downloading. The Users-page redesign and other queued UI work are not included in this release.

## Validation

Five focused local-library checks passed, including read-only scanning, metadata reuse, failed-root preservation, edition ranking and identity-based completeness. Python compilation and the production frontend build passed. No full regression or live-library/service testing was performed.

Images: `ghcr.io/rstuke82/playlist-bridge:beta` and `:3.0.0-beta.5` (AMD64 and ARM64). Stable main/latest are unchanged. Backups and runtime databases are excluded from artifacts.
