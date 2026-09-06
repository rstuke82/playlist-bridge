# Playlist Bridge

**Version:** 2.0.0-beta.1  
**Build:** 20260906.4

Playlist Bridge syncs public **Spotify** and **Apple Music** playlists to playlists in your local **Plex music library**.

Version 2.0 adds a self-hosted **React + TypeScript** web interface with a **FastAPI** backend while retaining the existing matching engine, CLI, and JSON state files during the 2.0 beta series.

> **Beta software:** back up your Playlist Bridge JSON state files before installing a new beta build.

## Current beta features

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
- Existing JSON state remains compatible
- Atomic state writes and process locking
- Webhook notification foundation for later 2.0 betas

## State files

Playlist Bridge continues to use JSON files in the project root:

```text
config.json
mapping.json
missing_tracks.json
match_metadata.json
source_snapshots.json
ignored_tracks.json
artist_aliases.json
```

Keep these files when upgrading from 1.5. They contain your registered playlists, Plex configuration, saved mappings, favorites, Auto Sync settings, ignored tracks, aliases, and source snapshots.

A simple backup before upgrading is recommended:

```bash
mkdir -p backup-state
cp config.json mapping.json missing_tracks.json match_metadata.json \
  source_snapshots.json ignored_tracks.json artist_aliases.json backup-state/ 2>/dev/null || true
```

## Requirements

- macOS or Ubuntu
- Python 3.9 or newer
- Node.js 20 or newer
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
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Verify the tools:

```bash
python3 --version
node --version
npm --version
git --version
```

Node.js should be version 20 or newer.

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
npm install
npm run build
cd ..
```

A successful build creates `web/dist/`. FastAPI serves this production build automatically.

### 5. Start Playlist Bridge

From the project root with the Python virtual environment active:

```bash
python -m playlist_bridge web
```

Playlist Bridge listens on port `8787`.

On the same computer, open:

```text
http://localhost:8787
```

From another computer on your network, open:

```text
http://SERVER-IP:8787
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

Development API requests are proxied to FastAPI on port `8787`.

## Updating an existing beta installation

Back up the JSON state files first, then:

```bash
git switch beta
git pull
source .venv/bin/activate
pip install -r requirements.txt
cd web
npm install
npm run build
cd ..
python -m playlist_bridge web
```

Do not delete the existing JSON state files during an update.

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

## Missing-track fixes

When a deduplicated missing track is matched from the web UI, Playlist Bridge saves the match as a manual mapping across the affected unresolved occurrences and then syncs the affected playlists so the correction is immediately reflected in Plex.

## Beta notes

The 2.0 beta series is an architectural transition. The existing matching engine currently remains available behind the new API while components are progressively separated into reusable backend modules. JSON compatibility and CLI support are being preserved throughout that transition.
