# Playlist Bridge

**Release:** Playlist Bridge 2.2 Beta 2

Playlist Bridge syncs public **Spotify** and **Apple Music** playlists to playlists in your local **Plex music library**.

Playlist Bridge provides a self-hosted **React + TypeScript** web interface with a **FastAPI** backend while retaining the existing matching engine, CLI, with SQLite runtime storage.

> Back up the existing data directory before upgrading; keep its mount and connection settings.

## Media availability

Settings → Tasks provides separate Plex Library Scan, Lidarr Library Scan, Reconcile Availability, and Retry Missing Matches tasks. Scan frequency follows midnight-aligned intervals; Run Now does not shift the schedule. Plex cache and matching options live in Settings → Plex; Lidarr inventory options live in Settings → Lidarr.

Scans inventory the entire configured Plex music library and Lidarr catalog, including albums added outside Bridge. Successful snapshots persist in SQLite across restarts and are scoped to the configured service. Scans link saved source tracks and requests without changing playlist contents or manual mappings. Retry Missing Matches applies the automatic matcher separately and can queue affected Auto Sync playlists; custom or disabled playlist schedules are excluded from that automatic queue.

Routine syncs can reuse a fresh Plex snapshot for the configured lifetime. Source playlists are still fetched and destination contents verified. Failed verification invalidates the snapshot. Actual speed gains depend on library size and external services.

Requests show In Progress only while present in the download queue. Added albums that are not downloading and not imported show Needs Attention. Plex availability is tracked separately from Lidarr import status. Album-only requests without source tracks are not claimed as verified in Plex.

Playlist Details supports inherited, disabled, or custom weekly schedules using the server timezone. Custom schedules replace recurring global Auto Sync for that playlist. Overlapping scheduled syncs are skipped; manual runs do not move the next scheduled time. Filters cycle through include, exclude, and off. Ready to Sync includes pending match changes and newly matched missing tracks.

## Lidarr

This preview is published to the beta branch and Docker tags `beta` and `2.2.0-beta.2`. Stable main/latest remain on 2.1.0.

In Settings → Lidarr, enter the server URL (including any URL base) and API key. Test Connection loads root folders, quality profiles and metadata profiles from that instance. Choosing a root folder loads its quality, metadata, monitoring and tag defaults; Use Root Folder Defaults restores them after overrides. A metadata profile named None is supported and is distinct from monitoring None. Choose defaults, enable the integration and save. Blank API-key fields retain the existing key only when the server URL stays the same. Keys remain server-side in the persistent SQLite database; do not publish the data directory or backups.

On Missing or playlist details, choose **Add Album to Lidarr**. Opening the dialog searches Lidarr using the source album, or track and artist when the album is unknown. Select a result, adjust options inline and click **Add to Lidarr**. Validation runs before the request is queued, then the dialog closes with confirmation on the same page. **Advanced Lookup · MusicBrainz** provides editable Recording, Artist and Album fields, prefilled where possible. Clear a field to omit it; clear Recording and Artist for an album-only search. Missing source albums are resolved through recording search; metadata results are candidates for review, not automatic identifications. MusicBrainz uses its public API without credentials, a descriptive User-Agent, throttling, and a SQLite cache (7 or 30 days, at most 500 lookups). Its availability and Lidarr's metadata catalog can differ.

Defaults monitor only the selected album, do not monitor future discoveries, and do not search immediately. Broader monitoring choices apply only when adding a new artist. Existing artists retain their profiles, paths and other album flags. Paused artists must be enabled in Lidarr before requesting monitored/searching additions. Existing album entries are reused; an already monitored album is never silently unmonitored. Confirmation queues a persistent Activity job; changing settings invalidates an unexecuted preview. A timed-out external write is not automatically retried: inspect Lidarr before retrying.

Adding an album does not remove Bridge's missing entry or alter Plex. Once Lidarr's download/import reaches Plex, Sync / Refresh can resolve it. No scheduled bulk album adds, automatic downloads of every missing album, or automatic MusicBrainz-to-track match changes are included.

When searching a newly added album, Bridge waits for Lidarr’s own refresh and track data rather than starting another refresh. Request status is retained in SQLite and shared across playlists: **Requested in Lidarr**, **Album added; search pending**, or **Album added; search failed**. **Retry Search** only checks readiness and submits or resumes the album search; it does not add or refresh the album again. A pending command is observed, not resubmitted. A search submission that times out without a command ID requires inspection in Lidarr.

Playlist filters now consolidate drift, health errors, missing and LOST under **Needs Attention**. Playlist details also support Ignore in the current playlist or universally. See [the roadmap](ROADMAP.md) for future plans.

Additional features:

- Missing toolbar alignment and shorter match-search loading text.
- Optional artist tags on album addition, including an opt-in merge into existing artists without replacing their other tags.
- A persistent match queue shared by Missing, playlist details and Track Details. Queue several choices, then **Apply Matches & Sync** to save all and sync each affected playlist once. Edits remain drafts until applied; failed validation and cancelled pending jobs return them to review. Existing compatibility API endpoints retain their immediate job behavior.
- Ignore requests wait behind active jobs instead of contending with an active sync's write lock. They are saved when executed; Plex removal still happens on the next sync.
- Add Playlist clears and unlocks its URL field as soon as the job is queued.
- Settings → General → Console logging: debug off by default, with detailed terminal matching output and successful GET access lines only when enabled. Errors and job summaries remain visible; detailed Activity logs are always retained. CLI output is unchanged.
- Optional Apple song discovery and preview in match review and Track Details. Select a catalog recording to load Apple's official embedded player and store link. No audio is downloaded or cached by Bridge; preview availability depends on region and Apple's catalog. Spotify preview URLs are deprecated, so Playlist Bridge uses Apple for preview discovery even for Spotify-source tracks.

API references: [Lidarr](https://lidarr.audio/docs/api/), [MusicBrainz rate limits](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting).

## Library review and safeguards

- Activity, Settings and version stay at the bottom of the desktop sidebar across intermediate widths.
- Unrequested live recordings require review instead of automatic acceptance. Existing saved selections are preserved.
- Missing has remembered source, playlist, favorite, Missing/LOST and Manually matched elsewhere filters, with the same filter/sort controls as Playlists and playlist details.
- Runtime backup folders are excluded from Git, Docker contexts and release archives.

## Features

Playlist Bridge 2.1 provides SQLite persistence, Docker deployment and the existing CLI and matching engine.

- Dashboard cards open their corresponding pages. Playlist cards apply the exact matching filter, clear previous search/filter state and remember the resulting view. Needs Attention uses the same criteria as its dashboard count.
- Quick Actions has a pencil editor for up to five actions, including sync scopes, Health Check, Back Up Now and Check for Updates. Selection and display order are remembered in the browser.
- Add Playlist is one action: paste a public Spotify or Apple Music URL, choose Favorite and Auto Sync, and add it. Invalid or already registered URLs are rejected inline before queuing. Fetching, matching and Plex creation run as a background job with Activity details. The analysis API remains compatible for existing clients.
- All dialogs render above the application panels, centered in the visible viewport even after scrolling. Dialog content scrolls internally, controls remain reachable on mobile, keyboard focus stays within the dialog and returns to the trigger when closed. This includes Ignore, Fix Match, removal, backup restore, log clearing and Quick Actions.
- Match labels are consistently Auto, Manual, Saved, Missing, LOST and Ignored. Saved means an older match whose origin is unknown; it is not relabeled as Auto or Manual. Existing mappings and internal field names are preserved. Sorting uses Last synced.
- Activity has permanent desktop and mobile navigation, full job history and retained logs. Playlist filters, bulk Auto Sync, consistent Settings pages, daily backups, restore and midnight-aligned recurring tasks are included.
- Stable installations default to the latest image and main update channel.

Storage remains SQLite schema 4. New activity snapshots use the existing generic state table; existing schema 4 databases require no schema migration. Jobs and output survive restarts. The API keeps idle polling slow; live activity uses one completion-scheduled request at a time while expanded, then stops after final output. Lists and settings load on demand. Two bounded detail workers, request timeouts, read-only health concurrency, matching thresholds, Docker port 8173 and CLI support are preserved.

- React + TypeScript web interface
- FastAPI backend
- Dashboard statistics and bulk actions; read-only health details on Playlists
- Add and analyze Spotify or Apple Music playlists from the web UI
- Sync all playlists, favorites, or individual playlists
- Clickable favorite stars and Auto Sync controls
- Deduplicated missing-track review with Plex candidate matching
- Saving a missing-track match syncs the affected playlists automatically
- Plex configuration directly in the Settings page
- Existing Playlist Bridge CLI remains available
- Automatic legacy JSON import with preserved backups
- Atomic state writes and process locking

## Persistent storage and migration

Native installs use the current working directory, or `PLAYLIST_BRIDGE_DATA_DIR` when set. Docker uses `/data`.

- `config.json`: startup settings (Plex connection, server/data directory settings).
- `playlist-bridge.db`: registered playlists, favorites, auto-sync, mappings, provenance, missing/ignored tracks, snapshots, sync history, artist aliases, notification settings/history where present, and health results/history.

At first startup, legacy config and `mapping.json`, `missing_tracks.json`, `match_metadata.json`, `source_snapshots.json`, `ignored_tracks.json`, and `artist_aliases.json` are imported transactionally. Plain and schema-wrapped JSON are accepted. Imported values are checked for exact preservation before commit. Originals are preserved as `.pre-sqlite.bak` files and inside the migration backup table. Legacy state JSON is never read as live state again. Config is reduced to startup settings. Invalid legacy files stop migration without altering the originals; correct them and restart to retry.

Back up the entire data directory with the application stopped before upgrading. After migration, retain the database and config when updating. To roll back to a pre-SQLite build, restore the pre-migration backups into a separate directory; later SQLite changes are not exported to legacy JSON.

Missing, empty, `{}`, and partial config files allow the UI to launch. Artist aliases now live in SQLite; editing the old alias JSON no longer changes matching. CLI alias management remains available. First use initializes/migrates storage even for a CLI dry run; subsequent dry-run matching does not save sync state.

## Docker installation (macOS and Ubuntu)

Install Docker Desktop on macOS or Docker Engine with the Compose plugin on Ubuntu.
Docker includes Python and the compiled React UI; Node and Python are not needed on the host.

From this extracted project directory, build and start:

```bash
docker compose up -d --build
docker compose ps
```

Open `http://localhost:8173` (or `http://SERVER-IP:8173`), then configure Plex in **Settings**.
Missing, blank, and `{}` config files are valid; no Plex connection is needed for the UI or `/api/health` to start.
Use a Plex address reachable from the container; `localhost` inside Docker refers to the container itself.

Compose mounts `./data` at `/data`. Keep that directory when updating or recreating the container.
To migrate an existing native install, stop its web service and scheduled CLI syncs, back up its state,
and copy the existing config and legacy state JSON files into `./data` before starting Docker.
Do not run the native and container installations against the same data at the same time.

To change the port, put this in a `.env` file alongside `docker-compose.yml`:

```dotenv
PLAYLIST_BRIDGE_PORT=8174
```

Compose uses that port for both the host mapping and backend. The healthcheck follows it automatically.
`PLAYLIST_BRIDGE_DATA_DIR` can also select a data directory for native runs; relative paths resolve from the working directory.
Inside this Compose service it stays `/data`; change the left side of `./data:/data` to relocate host storage.

### Updating a locally built image

Replace the source files with the new build (or pull the main branch), then:

```bash
docker compose up -d --build
docker compose logs --tail=50
```

### Using GHCR images

After a maintainer publishes the image to GHCR, use:

```bash
docker compose pull
docker compose up -d --no-build
```

The default image in this preview is `ghcr.io/rstuke82/playlist-bridge:beta`.
To pin this build, set `PLAYLIST_BRIDGE_IMAGE=ghcr.io/rstuke82/playlist-bridge:2.2.0-beta.2`
in `.env`. The `main` and `latest` tags follow stable releases.

Maintainers can publish both server architectures with the existing buildx builder:

```bash
docker buildx use playlist-bridge-builder
docker buildx inspect --bootstrap
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/rstuke82/playlist-bridge:2.2.0-beta.2 \
  -t ghcr.io/rstuke82/playlist-bridge:beta --push .
```

If the named builder does not exist, replace the first command with `docker buildx create --name playlist-bridge-builder --use`. The multi-platform build includes both AMD64 servers and ARM64 machines.

The image includes OCI title, description, source, version, and revision labels.
See the [Dockerfile reference](https://docs.docker.com/reference/dockerfile/) and
[GitHub Container Registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

To run the CLI in the running container:

```bash
docker compose exec playlist-bridge python sync.py
docker compose exec playlist-bridge python sync.py --sync-all
```

## Native requirements

- macOS or Ubuntu
- Python 3.9 or newer
- Node.js 22.12 or newer
- npm
- Git
- Plex Media Server with a music library
- Plex authentication token
- Public Spotify and/or Apple Music playlist URLs

Playlist Bridge does not currently require Spotify or Apple Music developer credentials for public-playlist source handling.

## Installation

The overall installation is the same on macOS and Ubuntu. Commands that differ by operating system are called out below.

### 1. Install system requirements

**macOS** using Homebrew:

```bash
brew install git python node
```

**Ubuntu:**

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip curl
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

Verify the tools:

```bash
python3 --version
node --version
npm --version
git --version
```

Node.js should be version 22.12 or newer.

### 2. Clone Playlist Bridge

For the stable branch:

```bash
git clone -b main https://github.com/rstuke82/playlist-bridge.git
cd playlist-bridge
```

For an existing checkout:

```bash
git switch main
git pull
```

### 3. Create and activate the Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

When the environment is active, your shell prompt will normally begin with `(.venv)`.

### 4. Install and build the web interface

```bash
cd web
npm ci
npm run build
cd ..
```

A successful build creates `web/dist/`. FastAPI serves this production build automatically.

### 5. Start Playlist Bridge

From the project root with the Python virtual environment active:

```bash
python -m playlist_bridge web
```

Playlist Bridge listens on port `8173`; set `PLAYLIST_BRIDGE_PORT` to override it.

On the same computer, open:

```text
http://localhost:8173
```

From another computer on your network, open:

```text
http://SERVER-IP:8173
```

Stop the server with **Ctrl+C**.

### 6. Configure Plex in the web UI

Open **Settings** at the bottom of the left sidebar and enter:

- Plex server URL, for example `http://plex-server:32400`
- Plex token
- Plex music library

Use **Test & Discover Libraries**, select the music library, then choose **Save Plex Settings**.

### 7. Optional frontend development mode

For React development with hot reload, keep the FastAPI server running and open a second terminal:

```bash
cd web
npm run dev
```

Vite normally serves the development UI at:

```text
http://localhost:5173
```

Development API requests are proxied to FastAPI on port `8173`. If you override the backend port, update the proxy target in `web/vite.config.ts` to match.

## Updating an existing installation

Stop the app and back up the full data directory first, then:

```bash
git switch main
git pull
source .venv/bin/activate
pip install -r requirements.txt
cd web
npm ci
npm run build
cd ..
python -m playlist_bridge web
```

Keep the database, config, and migration backups during updates.

## Running automatically on Ubuntu with systemd

If Playlist Bridge is running continuously on an Ubuntu server, you can create a systemd service. Replace `/path/to/playlist-bridge` with the actual clone location on that machine.

```ini
[Unit]
Description=Playlist Bridge Web UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/playlist-bridge
ExecStart=/path/to/playlist-bridge/.venv/bin/python -m playlist_bridge web
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

After saving the unit as `/etc/systemd/system/playlist-bridge.service`:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now playlist-bridge
sudo systemctl status playlist-bridge
```

## CLI compatibility

The existing CLI remains available:

```bash
python sync.py
```

Automated sync:

```bash
python sync.py --sync-all
```

Dry-run automated sync:

```bash
python sync.py --sync-all --dry-run
```

Show the installed version:

```bash
python -m playlist_bridge version
```

## Playlist health

The playlist health check is intentionally **read-only**. It fetches the current source playlist URL and compares it with the Plex library and destination playlist without performing a sync.

Each playlist has an independently collapsible Health section with placeholders before its first check and a Last updated timestamp. Results persist across navigation and restarts. Check All Health updates each row as its check completes and shows its current stage in the background job banner. Progress continues across page navigation. Connection failures appear beside the playlist with a Settings link and are preserved across refresh/restarts; the last successful metrics remain visible and are labeled as such.

A health result includes:

- source track count
- Plex destination playlist count
- tracks matched in the Plex library
- unresolved tracks
- ignored tracks
- expected tracks missing from the Plex playlist
- extra tracks currently in the Plex playlist
- source additions/removals since the last saved source snapshot

Running a health check does **not** modify Plex playlists, mappings, source snapshots, missing-track state, or `last_synced`.

## Playlist details and match fixes

Click a registered playlist name to view its full live source track list, saved Plex matches and Auto / Manual / Saved / LOST / Missing status. Sync / Refresh and Health Check are available there. Fix Match can replace an existing match using scored candidates or text search. Choose all missing occurrences or selected playlists; only affected playlists sync after saving. Selecting a candidate does not save immediately. Review the selection and click Save Match, or use Cancel, Close, Escape, or click outside the picker to leave without changes. Cancellation is available while candidates load; once saving starts, wait for the save/sync result.

## Missing-track fixes

When a deduplicated missing track is matched from the web UI, Playlist Bridge saves the match as a manual mapping across the affected unresolved occurrences and then syncs the affected playlists so the correction is immediately reflected in Plex.

## Compatibility

The web API uses the existing matching engine and SQLite repository. Earlier JSON state is imported automatically; CLI support remains available.


## Settings logs

Settings includes a Logs viewer with Refresh, level and action filters, and Clear logs. It shows recent web operations, health failures, and captured sync output, newest first. The latest 1,000 entries are stored in SQLite; the viewer shows up to 200. Plex tokens and recognized credentials are redacted. This is an application activity log, not a live Docker console or historical CLI log importer. Docker process/startup failures before the application opens its database remain available through `docker compose logs`.

Older supported SQLite databases migrate automatically. Keep a backup before upgrading; restore the matching backup when rolling back to an older release.

## Background jobs and schedules

Settings is organized into General, Plex, Matching, Ignored Tracks, Tasks, Backups, Logs and About. Web sync, health, analyze, add, and match-save operations enter a persistent SQLite queue. One worker executes jobs in the background; progress and results remain available after navigation or refresh. Dashboard offers Sync All, Favorites and Auto Sync scopes. The Playlists action uses the filtered results. The Auto Sync setting controls membership in scheduled Auto Sync scopes.

Configure recurring tasks with interval dropdowns in Settings → Tasks. Hourly intervals align to midnight: every three hours means 00:00, 03:00, 06:00 and so on; Daily means midnight. Run Now never changes the next scheduled time. A queued or running task causes its next occurrence to be recorded as skipped, without a delayed replay. Other tasks remain eligible. The web backend must be running. Interrupted jobs are not replayed automatically after a restart.

On upgrade, existing schedules retain their enabled state and are aligned to midnight. Supported hourly frequencies are retained; other old custom schedules become daily. The original definitions are retained in SQLite for diagnostics. Review the Tasks page after upgrading. Check for Updates always runs every six hours; Backup defaults to Daily; other new schedules default to Disabled.

The Tasks page displays the scheduling timezone. Set `TZ=America/Chicago` (or your preferred IANA timezone) in the Compose environment to use that timezone. The included Compose file passes `TZ` through from `.env`. If unset, the first existing schedule's timezone is retained, otherwise UTC is used. Changing an explicit `TZ` and restarting realigns future task boundaries.

Backups are stored under the persistent data directory's `backups` folder. SQLite's online backup API creates a consistent database snapshot alongside startup configuration. Browser-local appearance and filter preferences, host environment files, Plex playlists and media files are not part of the backup. The Restore action uses a listed backup; to recover a downloaded archive on another installation, place the intact `bridge-*.zip` archive in its data/backups directory. Restore validates compatibility and creates a safety backup first. Connection credentials are included, so store downloaded archives privately.

Cancellation is cooperative: queued jobs stop immediately; running jobs stop at safe checkpoints. An in-flight network call or playlist update can finish first. Completed Plex changes and saved manual matches are retained. Restarting the app is not an undo operation. Existing CLI commands remain synchronous and retain their matching behavior.

## Finding and organizing music

Dashboard shows statistics and Add Playlist, including analysis, queue status, stages, errors, and a link to the registered playlist. Playlists supports combined filters, local name search, and sorting by name or most recently synced. View preferences persist in the browser; added dates are not displayed. Each playlist shows last synced and last successful health check; expand Health to see named missing/extra destination tracks, unresolved tracks, and source additions/removals. Run a fresh check to populate detailed drift for old results.

Search finds playlist names and tracks from saved source snapshots, health previews, missing records, and mappings. Its separate Search Lidarr albums form looks up albums for review and requests without requiring a missing track. Open a playlist for its live source list and track filtering.

Missing sorts by track title, artist, album, last checked, occurrences, or playlist count. Occurrences counts repeated track entries; playlist count counts distinct registered playlists. Expand memberships to navigate to each playlist. Ignore can apply to selected playlists or universally to current and future matching occurrences. Ignore changes local matching rules; the next sync updates Plex. Use Stop Ignoring in Settings → Ignored Tracks to remove an ignore rule.

### Album search and sync

Album search starts with `Artist - Album` (or `Artist - Track` when the album is unknown). Bypass cache requests fresh MusicBrainz results while preserving rate limiting; Lidarr lookups already go directly to Lidarr. Upstream caches remain outside Bridge’s control. Existing results stay visible while retrying, and album options use saved defaults under Options.

Existing Lidarr albums show their monitoring state and offer Search Album. This action queues a search without re-adding the album or changing monitoring settings. If match edits save but a subsequent Plex sync fails, Activity reports partial completion and retains the individual playlist errors. Plex verification reports missing titles/artists and occurrence counts, with sensitive response details redacted.

### Navigation and album discovery

Track Details returns to the playlist or page it was opened from, with its filters and scroll position retained. Song previews expand inline, and closing them stops playback. Track Details also offers Ignore and Add Album to Lidarr; a sole playlist membership is selected automatically, while multiple playlists require an explicit selection for matching.

Playlist Details offers Needs Attention, Ignored, Manual and Automatic filters; clearing filters shows all tracks. Release priority and studio preference apply to both Lidarr and MusicBrainz album results. MusicBrainz is labeled Advanced Lookup. When source album metadata is missing, Find Album with Apple Music offers suggestions you can review and use for a Lidarr search without overwriting source metadata.

### Requests, downloads and logging

Requests shows album request history and status. Activity → Downloads focuses on active downloads and requests awaiting import. Progress percentages appear only when Lidarr reports a size. Imported into Lidarr does not confirm Plex has scanned the album. Status refreshes while relevant pages are visible; completed requests remain in SQLite.

Cancel Download removes the selected download and its temporary files from the download client, without deleting imported library music or the album registration. Find Another Download also blocklists the release and asks Lidarr for a replacement. Both require confirmation; shared multi-album downloads must be managed in Lidarr. Cancel does not unmonitor an album. Import failures show the upstream reason and a link to Lidarr.

MusicBrainz lookup starts, cache decisions, retry attempts and results are retained at INFO. Failures are ERROR; pending operations are WARNING. Successful HTTP access/polling and detailed candidate diagnostics require the console debugging option. Logs redact credentials. Preview album actions use the selected recording's artist and album, preserving source metadata and saved matches.

### Filters, sorting and bulk actions

The sort menu lists each field once, with Reverse sort controlling direction. Saved sort preferences remain compatible. Track Details and Playlist Details share Needs Attention, Ignored, Manual, and Automatic filters.

Select visible tracks on Missing and choose Ignore selected to queue a batch (up to 500 tracks), with explicit playlist or universal scope and per-track results in Jobs. Hidden selections are cleared when filters change. Ignored Tracks settings shows playlist names and Stop Ignoring actions.

Activity separates Jobs from Album Downloads. Downloads supports In Progress and Needs Attention filters plus artist/album text filtering. Requests also supports Completed and Cancelled filters and retains their history. Error notices show a short service message, with technical detail expandable where present. Raw response bodies and stack traces require DEBUG logging.
