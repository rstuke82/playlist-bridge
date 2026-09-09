# Playlist Bridge 2.0 Beta 6

Based on the delivered Beta 5 source. Human-facing release label: **Playlist Bridge 2.0 Beta 6**. Browser title: **Playlist Bridge**. Build numbers are omitted from the UI and release filename. Internal package/image version: `2.0.0-beta.6`.

## Changes

- One persistent activity view across pages, automatically opened by queued actions. It can collapse to a sticky activity bar; finished results stay until dismissed. Jobs and Recent Activity reopen this same view instead of starting duplicate detail pollers.
- Terminal-style timestamped output, automatic following that pauses on scroll-up, Copy Log with an HTTP-compatible selectable-text fallback, and full log downloads. The visible terminal limits rendering to the latest 1,000 lines; copying/downloading includes full saved output.
- Structured per-playlist activity snapshots with actual matching/Plex-update totals, current stage, elapsed time, and waiting states around HTTP requests. HTTP instrumentation preserves request parameters and timeouts without globally patching requests. Concurrent health output identifies its playlist.
- Completed, failed and not-started summaries, available matched/missing/LOST totals, retained errors and explicit cancellation checkpoint wording. Failed match-replacement syncs report failure while explaining that the mapping was saved.
- Three quick filters: All, Favorites, Needs Attention. More Filters contains Auto Sync, Missing, LOST and Never Synced. Active extra filters become removable chips and use AND semantics. Opposite Auto Sync choices are mutually exclusive. Sync / Refresh submits only visible keys.
- A single layout icon toggles Compact/Expanded and retains the existing browser preference. Compact rows use accessible health icons/tooltips, including amber attention, red check failure and muted not-checked states.
- One visible sync action per playlist; three-dot menus contain Auto Sync and Remove. Playlist names open details. Relative sync times offer exact timestamps on hover. Added dates and Last added sorting are gone.
- Dedicated global Search navigation; page-local text fields are labeled as filters. Empty list/filter states have Add Playlist or Clear Filter actions. Routine success banners are removed in favor of the activity view.
- Responsive navigation and controls, consistent Auto Sync labels, and a simpler detail-status selector.

## Compatibility and packaging

SQLite schema remains 4; activity snapshots use the existing state table. Existing jobs/events, schedules, mappings, CLI support and matching thresholds are preserved. Default Docker port remains 8173. The ZIP excludes runtime data, credentials, backups and dependencies; retain the existing data directory and .env.

The React production build and Python source syntax compilation succeeded. Automated regression tests, live-service exercises and Docker builds were not run, following the user's earlier preference. Prior regression-test sources are included but have not been comprehensively updated for Beta 6. No image was published from this task.

## Publish on the build machine

From the extracted source folder:

```sh
docker buildx use playlist-bridge-builder
docker buildx inspect --bootstrap
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/rstuke82/playlist-bridge:2.0.0-beta.6 \
  -t ghcr.io/rstuke82/playlist-bridge:beta --push .
```

If the builder is missing, replace the first command with `docker buildx create --name playlist-bridge-builder --use`.

## Update the server

From the existing Compose directory:

```sh
docker compose pull
docker compose up -d --no-build
```

Keep the data mount and existing environment file. If your environment pins a versioned image, change it to `ghcr.io/rstuke82/playlist-bridge:2.0.0-beta.6` before pulling; otherwise the default `beta` tag selects this release after publication.
