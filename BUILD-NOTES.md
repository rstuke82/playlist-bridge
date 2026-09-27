# Playlist Bridge 3.0 Beta 4

Package/image version: `3.0.0-beta.4`. Default port: 8173. Beta channel only.

## Upgrade step

Run **Settings → Tasks → Lidarr Library Scan** after upgrading. This collects track and imported-file identities in addition to albums. Run a Plex Library Scan to refresh paths and playback links. New automatic matches wait for a current Lidarr track snapshot (up to 24 hours old). Existing saved playlist mappings, including manual choices, remain intact. When Lidarr is disabled, the original Plex matcher remains available.

## Changes

- **Create from Text** accepts numbered/plain lists, artist-first or song-first lines, optional albums, and Song by Artist. Users review editable rows, fix ambiguous lines, remove headings, and name the playlist before Save & Sync. Text is treated as data, not instructions. Source order and duplicates remain intact.
- Custom sources persist in each account's SQLite store and can be edited from Playlist Details. Revision checks prevent overwriting newer edits. Registration survives zero matches so Missing, review and request workflows can be used before a Plex copy exists. Sync creates the Plex copy when playable tracks become available. Existing ignores and blocked artist names apply to text playlists. Custom Playlist is labeled consistently in lists and Missing filters.
- New automatic matching follows source metadata → Lidarr track identity → imported-file/Plex link. Existing recording/version thresholds and live safeguards are reused. An identified but undownloaded or unlinked track stays missing. Ambiguous identities require review.
- Lidarr scans collect tracks and files per artist, then replace the snapshot only after successful completion. Plex scans retain file paths and GUIDs. Links prefer exact file paths, with unique exact artist/album/title metadata as a fallback. Only imported Lidarr files qualify for automatic playback links. Matching reuses the loaded catalog and persists validated source identities and links in SQLite.
- **Music Library** browses Lidarr artists, albums with artwork, and tracks, including selected-release information, search, status filters, reverse sorting, and service links. Available, Partially Available, Downloading, Awaiting Download, Awaiting Plex, and Scan Pending are distinct.
- **Needs Attention** shows Plex tracks not linked to Lidarr, plus imported Lidarr albums awaiting Plex. A missing association is explicitly distinguished from proof that an album is absent from Lidarr.
- Administrators can review and correct track-to-Plex associations. Associations are server/library scoped and shared across accounts, but are reused only when the Plex item is visible and its identity remains unchanged for the current account. Existing playlist manual matches are not overwritten.
- Discover checks playback availability through these track links when the new inventory exists. Playlist Details displays the saved Lidarr identification state.

## Limits and validation

Library scans are snapshots, not live download guarantees. Different mount paths can use unique exact metadata or a reviewed manual association; automatic path-prefix mapping is not included. Existing saved Plex matches are preserved during this transition rather than mass-rewritten. Artist credits from pasted text are not enriched with external identities. The application name remains Playlist Bridge pending a final naming decision.

Python syntax, frontend production build, and six focused checks passed (parsing, account isolation, catalog/version matching, ambiguous links, and zero-match source preservation). Full regression, browser and live Plex/Lidarr tests were intentionally skipped for this beta. No real library files were modified during validation.

SQLite uses existing state tables; retain the data mount. Backups and runtime data are excluded from release artifacts. CLI support and stable main/latest remain unchanged.
