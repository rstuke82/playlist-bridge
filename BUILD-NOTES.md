# Playlist Bridge 2.0 Beta 7

Based on the current Beta 6 source, including the playlist-loading terminal correction. Human-facing release name: **Playlist Bridge 2.0 Beta 7**. Browser title: **Playlist Bridge**. No build number appears in the UI or ZIP filename. Package/image tag: `2.0.0-beta.7`.

## Included changes

Playlist Bridge 2.0 Beta 7 brings a consistent glass-style interface and clearer matching workflows.

- Desktop sidebar and floating mobile navigation, with accent colors and Light, Dark or Follow System appearance in General settings. Preferences are saved in your browser.
- One job terminal with timestamped progress. Playlist page loading uses a temporary status line that disappears when ready. Copy uses the native clipboard; Raw opens selectable text in the same panel, and Download saves the full log. Clipboard access requires browser support and a secure context; Raw remains available on plain HTTP.
- Unresolved source tracks produce completed-with-missing results. Actual Plex write/verification failures remain errors. Duplicate source occurrences are submitted in order using Plex's play queue support; if Plex collapses duplicate occurrences, the job warns and completes when the remaining distinct tracks and order are correct.
- Playlist filter, sort, refresh and Compact/Expanded icon controls sit together. Filters include Favorites, Needs Attention, 100% Matched, Has Manual Matches, Auto Sync, Missing, LOST and Never Synced. Multiple filters use AND; removable chips and Clear Filters reset them.
- Select multiple playlists for Sync / Refresh or removal. Sync acts on selected playlists, or the filtered set when none are selected. Removal asks whether to leave Plex playlists untouched (the default) or delete them too. Historical job output stays available, and unrelated registrations and mappings are preserved.
- Saved-match counts distinguish Auto, Manual and Legacy. Track names open Track Details with known playlist memberships, occurrence counts and current matches. Select playlists, preview a fresh automatic match or manual replacement, then apply and sync those playlists. Ignored occurrences are skipped; an unsuccessful automatic retry leaves existing matches unchanged.
- Accepting an automatic suggestion records Auto provenance; choosing a manual candidate records Manual. Existing matching rules and thresholds remain unchanged.
- A version-adjacent update indicator checks the public GHCR beta image every six hours. General settings includes Check Now. Updates are never installed automatically.
- Global search remains on its own page; page-local search fields filter the current page. The browser title is Playlist Bridge and the sidebar release label has no build number.

Earlier behavior remains: SQLite job-event history, sync-derived health, cached list rows, short-lived Analyze → Add reuse, and one generated schedule per action/scope. Standalone health checks remain read-only with respect to Plex and sync/matching state.

## Compatibility and limitations

SQLite schema remains 4; no new schema is required. Update-check state uses the existing state table. Existing Beta 4–6 databases retain their migration path, job history, schedules and scoped mappings. Keep your data mount and existing environment file. The archive excludes runtime data, credentials, dependencies and caches; it includes frontend source and production assets.

Track membership uses saved source snapshots/health results. Playlists with incomplete cached data are identified; refresh those playlists for current membership. Track-match previews expire after ten minutes and on backend restart, and are rejected if relevant saved state changes. Applying a preview saves the selected mappings and then syncs affected playlists; a later sync failure is reported without hiding that the mappings were saved.

Duplicate support depends on Plex. The writer prepares an ordered audio play queue for repeated entries and falls back to standard playlist insertion if needed. Verification accepts only missing repeat occurrences when every expected distinct track remains and relative order is preserved. Other mismatches remain errors. See the [official Plex API documentation](https://developer.plex.tv/pms/) for play queues and playlist item updates.

Update checking reads the public GHCR `beta` image version label and compares release versions. It does not detect rebuilds with the same version, install updates, or require registry credentials. A failed check retains the last known result. Native clipboard copying has no fallback injection; use Raw for keyboard copying when unavailable.

Python source syntax compilation and the React production build succeeded. Automated tests, live Plex/service exercises and Docker builds were not run, as requested. Prior test sources are included but have not been comprehensively updated for Beta 7. No image was published from this task.

## Publish on the build machine

From the extracted source folder:

```sh
docker buildx use playlist-bridge-builder
docker buildx inspect --bootstrap
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/rstuke82/playlist-bridge:2.0.0-beta.7 \
  -t ghcr.io/rstuke82/playlist-bridge:beta --push .
```

If the builder does not exist, use `docker buildx create --name playlist-bridge-builder --use` instead of the first command.

## Update the server

From the existing Compose directory:

```sh
docker compose pull
docker compose up -d --no-build
```

If your environment pins a version, set `PLAYLIST_BRIDGE_IMAGE=ghcr.io/rstuke82/playlist-bridge:2.0.0-beta.7`; otherwise the default `beta` tag selects this release after publication. Default port remains 8173; CLI support and the existing Docker architecture are retained.
