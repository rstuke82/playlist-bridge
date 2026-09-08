# Playlist Bridge

**Version:** 2.0.0-beta.2  
**Build:** 20260908.7

Playlist Bridge syncs public **Spotify** and **Apple Music** playlists to playlists in your local **Plex music library**.

Version 2.0 adds a self-hosted **React + TypeScript** web interface with a **FastAPI** backend while retaining the existing matching engine, CLI, with SQLite runtime storage.

> **Beta software:** back up your Playlist Bridge JSON state files before installing a new beta build.

## Current beta features

Beta 2 adds Settings logs, visible health-check progress and actionable Plex failures, consistent playlist navigation, and an explicit Save Match / Cancel workflow.

- React + TypeScript web interface
- FastAPI backend
- Dashboard with live, read-only playlist health checks
- Add and analyze Spotify or Apple Music playlists from the web UI
- Sync all playlists, favorites, or individual playlists
- Clickable favorite stars and Auto Sync controls
- Deduplicated missing-track review with Plex candidate matching
- Saving a missing-track match syncs the affected playlists automatically
- Plex configuration directly in the Settings page
- Existing Playlist Bridge CLI remains available
- Automatic legacy JSON import with preserved backups
- Atomic state writes and process locking
- Webhook notification foundation for later 2.0 betas

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

Replace the source files with the new build (or pull the beta branch), then:

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

The default image is `ghcr.io/rstuke82/playlist-bridge:beta`. This archive does not publish an image.
To pin this build, set `PLAYLIST_BRIDGE_IMAGE=ghcr.io/rstuke82/playlist-bridge:2.0.0-beta.2-build.20260908.7`
in `.env` once that tag is published. The `beta` and `2.0.0-beta.2` tags may advance; the build tag identifies this build.
Beta images should never be tagged `latest`.

Maintainers can build and tag for GHCR with:

```bash
docker build --build-arg VCS_REF="$(git rev-parse HEAD)" \
  -t ghcr.io/rstuke82/playlist-bridge:2.0.0-beta.2-build.20260908.7 \
  -t ghcr.io/rstuke82/playlist-bridge:2.0.0-beta.2 \
  -t ghcr.io/rstuke82/playlist-bridge:beta .
docker login ghcr.io
docker push ghcr.io/rstuke82/playlist-bridge:2.0.0-beta.2-build.20260908.7
docker push ghcr.io/rstuke82/playlist-bridge:2.0.0-beta.2
docker push ghcr.io/rstuke82/playlist-bridge:beta
```

The image includes OCI title, description, source, version, revision, and a separate build label.
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

For the beta branch:

```bash
git clone -b beta https://github.com/rstuke82/playlist-bridge.git
cd playlist-bridge
```

For an existing checkout:

```bash
git switch beta
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

## Updating an existing beta installation

Stop the app and back up the full data directory first, then:

```bash
git switch beta
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

Show the 2.0 beta version/build:

```bash
python -m playlist_bridge version
```

## Playlist health

The Dashboard health check is intentionally **read-only**. It fetches the current source playlist URL and compares it with the Plex library and destination playlist without performing a sync.

Each playlist has an independently collapsible Health section with placeholders before its first check and a Last updated timestamp. Results persist across navigation and restarts. Check All Health updates each row as its check completes and shows “Checking playlist X of Y”. Progress continues across page navigation. Connection failures appear beside the playlist with a Settings link and are preserved across refresh/restarts; the last successful metrics remain visible and are labeled as such.

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

Click a registered playlist name to view its full live source track list, saved Plex matches and Automatic / Manual / Legacy / LOST / Unresolved status. Sync Now and Check Health are available there. Fix Match can replace an existing match using scored candidates or text search. Choose all unresolved occurrences or selected playlists; only affected playlists sync after saving. Selecting a candidate does not save immediately. Review the selection and click Save Match, or use Cancel, Close, Escape, or click outside the picker to leave without changes. Cancellation is available while candidates load; once saving starts, wait for the save/sync result.

## Missing-track fixes

When a deduplicated missing track is matched from the web UI, Playlist Bridge saves the match as a manual mapping across the affected unresolved occurrences and then syncs the affected playlists so the correction is immediately reflected in Plex.

## Beta notes

The 2.0 beta series is an architectural transition. The existing matching engine currently remains available behind the new API while components are progressively separated into reusable backend modules. Legacy JSON is imported automatically; CLI support remains available.


## Settings logs

Settings includes a read-only Logs viewer with Refresh and level filtering. It shows recent web operations, health failures, and captured sync output, newest first. The latest 1,000 entries are stored in SQLite; the viewer shows up to 200. Plex tokens and recognized credentials are redacted. This is an application activity log, not a live Docker console or historical CLI log importer. Docker process/startup failures before the application opens its database remain available through `docker compose logs`.

Beta 1 SQLite databases upgrade automatically to schema 2, adding the log table while preserving existing runtime state and health results. Back up your data directory with the app stopped before upgrading. Beta 1 cannot open the newer schema; use your backup to roll back.
