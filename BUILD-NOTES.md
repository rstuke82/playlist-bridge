# Playlist Bridge 2.0.0-beta.4

Build: `20260908.8`. The uploaded beta.3 had removed its separate build number; this resumes after the prior numbered build `20260908.7` while keeping the version exactly `2.0.0-beta.4`.

## Package

Built from the uploaded `Playlist Bridge.zip`. Includes Python source, frontend source and lockfile, compiled frontend, Dockerfile, Compose file, documentation, and regression tests. Excludes private runtime data, credentials, backups, virtual environments, and node_modules. Keep your existing `data/` directory when replacing the source files.

## Changes

- One completion-scheduled polling loop per resource, shared in-flight GETs, jobs at 3 seconds active / 45 seconds idle, health at 45 seconds.
- Page-specific list loads on entry or completed state changes, settings reads on section entry, and no schedule polling.
- Health results merge from incremental background-job results without repeatedly fetching playlist lists.
- Serialized detail loads with browser timeout, retry/error display, and relevant-job refresh; separate two-worker backend pool and 60-second API deadline. A timed-out worker retains its slot until it exits, preventing an unbounded backlog. Existing per-call network timeouts remain unchanged.
- Strict Plex detail errors, off-event-loop request logging, cached repository setup, fresh request-local state, lazy read-only namespace loads, and no read-only baseline deep copies.
- One health/attempt load per playlist-list request; batch log cleanup with the same newest-1,000 visible window; additive SQLite indexes, still schema version 3.
- Three concurrent read-only health checks with incremental persistence and safe cancellation. Matching heuristics and CLI command behavior are preserved.
- HTML cache revalidation and immutable hashed assets.

## Validation completed

- Python compile/syntax passed.
- `npm run build` passed and production assets are included.
- 40 Python regression tests passed, including actual ASGI route/middleware requests for key endpoints, detail success/error/timeout/busy responses, and Logs responsiveness during blocked detail work.
- Health tests verified concurrency of three, incremental persisted results, cancellation, and unchanged sync/mapping/missing/snapshot/last_synced state.
- SQLite migration/idempotence, existing schema-3 state compatibility, log retention, and added indexes passed using disposable fixtures.
- Docker Compose configuration parsed successfully. No Docker image was built or run; Docker daemon was unavailable, and further local testing was stopped at the user's request.
- Frontend polling/navigation structure was reviewed and compiled. No live-browser or real Spotify/Apple/Plex account validation was performed.

## Server update

Stop the existing service and back up `data/`. Replace project source files with this release while retaining `data/` and your `.env`. Then run:

```sh
docker compose up -d --build
docker compose logs --tail=50
```

This is a source release; it does not publish or update the GHCR `beta` tag. Use `--build` to build the supplied source. Docker continues to use port 8173 by default.
