# Playlist Bridge 2.0

Package/image version: `2.0.0`. Human-facing release: **Playlist Bridge 2.0**. Browser title: **Playlist Bridge**. No build number is displayed in the application or ZIP filename.

## Final-release changes

Playlist Bridge 2.0 is the final release of the web application, with SQLite persistence, Docker deployment and the existing CLI and matching engine.

- Dashboard cards open their corresponding pages. Playlist cards apply the exact matching filter, clear previous search/filter state and remember the resulting view. Health Drift and Health Errors use the same predicates as their dashboard counts.
- Quick Actions has a pencil editor for up to five actions, including sync scopes, Health Check, Back Up Now and Check for Updates. Selection and display order are remembered in the browser.
- Add Playlist is one action: paste a public Spotify or Apple Music URL, choose Favorite and Auto Sync, and add it. Invalid or already registered URLs are rejected inline before queuing. Fetching, matching and Plex creation run as a background job with Activity details. The analysis API remains compatible for existing clients.
- All dialogs render above the application panels, centered in the visible viewport even after scrolling. Dialog content scrolls internally, controls remain reachable on mobile, keyboard focus stays within the dialog and returns to the trigger when closed. This includes Ignore, Fix Match, removal, backup restore, log clearing and Quick Actions.
- Match labels are consistently Auto, Manual, Saved, Missing, LOST and Ignored. Saved means an older match whose origin is unknown; it is not relabeled as Auto or Manual. Existing mappings and internal field names are preserved. Sorting uses Last synced.
- Activity has permanent desktop and mobile navigation, full job history and retained logs. Playlist filters, bulk Auto Sync, consistent Settings pages, daily backups, restore and midnight-aligned recurring tasks from Beta 8 are included.
- Git branches main and beta and Docker image tags main, beta and 2.0.0 receive the same final release. The default Compose image and update channel are main. Set PLAYLIST_BRIDGE_UPDATE_CHANNEL=beta to follow beta update notifications instead.

## Compatibility

SQLite schema remains 4, and Beta 4–8 databases retain their migration path and match provenance. The final release includes Beta 8 task scheduling and backup behavior. Existing custom schedules align to midnight on first upgrade; unsupported intervals become Daily. Original definitions remain in SQLite for diagnostics. Review Settings → Tasks and its displayed timezone after upgrading.

Tasks offer Disabled, Every hour, Every 3 hours, Every 6 hours, Every 12 hours and Daily. Run Now does not shift boundaries. A due occurrence is skipped when the same task is queued or running. Set TZ in the Compose environment for the desired scheduling timezone. Backup defaults to Daily, retains 14 scheduled copies and creates a safety copy before restoring. Backups include credentials and app state, not Plex music, host environment files or browser-local preferences.

Port 8173, CLI support, matching thresholds, duplicate handling, scoped removal, read-only health behavior and Docker architecture are unchanged. The downloadable archive includes source and compiled frontend assets, without runtime data, credentials, dependencies or the git directory.

## Validation

The React production build and Python source compilation passed. A disposable browser preview verified the Ignore dialog at the bottom of a long Missing page, focus restoration without jumping the scroll position, mobile dialog sizing, the five-action selection limit and saved Quick Actions. The Favorites dashboard card opened the matching filtered set. No live Plex playlists were used for these checks.

## Publish the final release

The repository release commit is intended for both main and beta. Push both branches together without rewriting history:

```sh
git push --atomic origin HEAD:main HEAD:beta
```

Publish one multi-platform image under all three tags:

```sh
docker buildx use playlist-bridge-builder
docker buildx inspect --bootstrap
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/rstuke82/playlist-bridge:2.0.0 \
  -t ghcr.io/rstuke82/playlist-bridge:main \
  -t ghcr.io/rstuke82/playlist-bridge:beta --push .
```

From the existing server Compose directory:

```sh
docker compose pull
docker compose up -d --no-build
```

Retain the existing data mount and environment file. To use the stable image explicitly, set PLAYLIST_BRIDGE_IMAGE=ghcr.io/rstuke82/playlist-bridge:main. The final release is also published to beta for existing beta installations. Update checks default to main; use PLAYLIST_BRIDGE_UPDATE_CHANNEL=beta if following that channel.
