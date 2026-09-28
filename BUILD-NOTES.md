# Playlist Bridge 3.0 Beta 6

Package/image version: `3.0.0-beta.6`. Default port: 8173. Beta channel only.

## Artist-first local library

- Library opens to compact artist rows, with album and track counts.
- Select an artist to browse their unified album catalog.
- One filter menu: artist association filters in the artist list, release-type and availability groups in album views.
- Shared filter/sort popovers render above translucent panels and remain within the viewport.
- Embedded MusicBrainz artist IDs provide direct links. Untagged artists can be associated through reviewed candidates or an explicit MBID. Same-name artists with different MBIDs remain separate.
- Refresh Metadata loads the MusicBrainz catalog as a background job.

## Optional iTunes metadata

- Supplement MusicBrainz with genre, album artwork and missing display dates; no identity or file-tag replacement.
- Automatic iTunes association requires an exact artist name and a corroborating album. Ambiguous candidates require review.
- Cache results for seven days and pace requests. Toggle enrichment in Settings → Local Library.
- Hide invalid years such as 0000 and 0001.

## Upgrade

Pull the beta image and recreate your container. Preserve your existing data and read-only music mount. Local Library remains opt-in. Open an artist and use Review Artist Link or Refresh Metadata, then refresh Library after the Activity job finishes.

When using the optional local Compose override, keep it in both commands:

```sh
docker compose -f docker-compose.yml -f docker-compose.local.yml pull
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

This release does not add native downloading/importing, the queued Users redesign, or automatic recreation of missing Plex playlists.

## Validation

Four focused artist/metadata checks and five local-library checks passed. Python compilation and the frontend build passed. No full regression, live-service metadata testing or browser visual testing was performed.

Docker tags: `ghcr.io/rstuke82/playlist-bridge:beta` and `:3.0.0-beta.6`, for AMD64 and ARM64. Stable main/latest remain unchanged. Backups and runtime databases are excluded from publication.
