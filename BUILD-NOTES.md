# Playlist Bridge 2.1

Package/image version: `2.1.0`. Human-facing release: **Playlist Bridge 2.1**. Browser title: **Playlist Bridge**. No build number is displayed in the application or ZIP filename.

## Final-release changes

- Includes the 2.1 beta improvements to Lidarr integration, MusicBrainz lookup, logging, previews, matching workflows, filtering and bulk Ignore.
- Requests has its own navigation entry and retains album request history. Activity Downloads focuses on active downloads and requests awaiting import.
- Missing tracks have aligned selection, track information and action controls, with Artist and Album sorting and the shared Reverse sort option.
- Search supports standalone Lidarr album lookup and requests. Lidarr candidates show album artwork when supplied by the service.
- Advanced MusicBrainz lookup has separate Recording, Artist and Album fields, prefilled where possible. Searches use the edited values and omit cleared fields, supporting album-only searches for soundtracks and compilations.
- Universal playlist distribution remains planned with the 2.2 multi-user work; it is not part of 2.1.

## Compatibility and packaging

Existing SQLite persistence, migration paths, CLI support, Docker deployment and default port 8173 are retained. Keep the existing data mount and environment settings when upgrading. Backups, runtime databases, credentials, dependencies and Git metadata are excluded from the downloadable release archive; it includes source and compiled frontend assets.

The default Compose image is `latest` and the default update channel is `main`. Existing beta installations can use the `beta` image, which also points to this final release. An explicit environment setting continues to override these defaults.

## Validation

The React production build, Python source compilation, four MusicBrainz tests and 21 Lidarr tests passed for the final changes. Docker images built for linux/amd64 and linux/arm64. Live Plex, Lidarr and MusicBrainz services were not tested for this release; upstream availability remains independent of the application build.

## Publish the final release

Publish source to both branches without rewriting history:

```sh
git push --atomic origin HEAD:main HEAD:beta
```

Publish the multi-platform image under the version and channel tags:

```sh
docker buildx use playlist-bridge-builder
docker buildx inspect --bootstrap
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/rstuke82/playlist-bridge:2.1.0 \
  -t ghcr.io/rstuke82/playlist-bridge:main \
  -t ghcr.io/rstuke82/playlist-bridge:latest \
  -t ghcr.io/rstuke82/playlist-bridge:beta --push .
```

From the existing server Compose directory:

```sh
docker compose pull
docker compose up -d --no-build
```

To pin the release, set `PLAYLIST_BRIDGE_IMAGE=ghcr.io/rstuke82/playlist-bridge:2.1.0` in the existing environment file.
