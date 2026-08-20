# Playlist Bridge

**Version 1.0**

Sync public **Spotify** and **Apple Music** playlists to a **Plex** music library.

Playlist Bridge fetches tracks from public playlist pages, matches them against tracks already in Plex, creates or rebuilds Plex playlists in source order, preserves manual match decisions, and syncs available playlist metadata and artwork.

## Features

- Spotify playlist support
- Apple Music playlist support, including Replay playlists
- No Spotify or Apple Music API credentials required
- Plex playlist creation and synchronization
- Persistent source-to-Plex track mappings
- Fuzzy title/artist matching
- Album-aware matching
- Preference for original/canonical album copies
- Lower ranking for compilations, live albums, remixes, deluxe editions, and remasters
- Interactive missing-track triage with scored Plex candidates
- Manual Plex search for difficult matches
- Existing match review and correction
- Playlist artwork synchronization
- Apple artwork dimension verification before Plex upload
- Spotify artwork extraction
- Persistent last-sync timestamps
- Automated `--sync-all` command for scheduled use

## Requirements

- Python 3
- A reachable Plex Media Server
- A Plex authentication token
- Spotify and/or Apple Music playlists that are publicly accessible

Python dependencies are listed in `requirements.txt`:

```text
requests>=2.28.0
fuzzywuzzy>=0.18.0
python-Levenshtein>=0.20.0
beautifulsoup4>=4.11.0
```

## Installation

Create a virtual environment if desired and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then run:

```bash
python sync.py
```

On Windows, activate the virtual environment with:

```powershell
.venv\Scripts\activate
```

## Plex Setup

On first use, Playlist Bridge asks for:

```text
Plex server URL (e.g., http://localhost:32400):
Plex API token:
```

The script verifies the connection against Plex before saving it.

Plex configuration is stored locally in `config.json`.

You can change the Plex connection later from:

```text
[9] Settings
    [1] Reconfigure Plex
```

## Interactive Menu

Running the script without arguments opens:

```text
==================================================
Playlist Bridge - Spotify/Apple Music to Plex
==================================================
[1] Add new Spotify/Apple Music playlist
[2] Sync all playlists
[3] Sync specific playlist
[4] View registered playlists
[5] Resolve missing tracks
[6] Edit playlist matches
[7] Sync history
[8] Remove playlist
[9] Settings
[x] Exit
==================================================
```

### 1. Add new playlist

Paste a public Spotify or Apple Music playlist URL.

Examples:

```text
https://open.spotify.com/playlist/7eahWLng9go8LDR5gcW6A3?si=...
```

```text
https://music.apple.com/us/playlist/replay-2019/pl.rp-NLLMIo0EvBxO
```

Spotify URLs with query parameters are normalized automatically. Apple Music playlist IDs containing characters such as hyphens are also supported.

When adding a playlist, the script:

1. Fetches the source playlist.
2. Scans the Plex music library.
3. Matches source tracks to Plex tracks.
4. Saves any unmatched tracks for later review.
5. Creates the Plex playlist if at least one track matched.
6. Adds tracks in source order.
7. Applies available description and artwork.
8. Stores the playlist for future synchronization.

### 2. Sync all playlists

Synchronizes every registered playlist.

Saved mappings—including manual matches from Options 5 and 6—are reused before fuzzy matching is attempted.

### 3. Sync specific playlist

Select one registered playlist and synchronize only that playlist.

### 4. View registered playlists

Shows each registered playlist with:

- Playlist name
- Source service
- Source URL
- Last-sync timestamp

Service names are consistently displayed as **Spotify** and **Apple Music**.

### 5. Resolve missing tracks

Displays playlists that currently contain unmatched source tracks.

For every missing track, Playlist Bridge shows the best available Plex candidates with album and score:

```text
[1/20] Let It Go - Idina Menzel (Frozen)

  Best Plex candidates:
  [1] Let It Go - Idina Menzel (Frozen) (100%)
  [2] Let It Go - Idina Menzel (Frozen Deluxe Edition) (93%) [-7 deluxe]
  [3] Let It Go - James Bay (...) (68%) [LOW CONFIDENCE]

  [s] Skip
  [m] Manual search
  [f] Finish triage & sync now
  [x] Exit
```

Numbers are reserved for selecting numbered candidates.

Controls:

- `s` — leave this track unmatched and continue
- `m` — manually search Plex by title, artist, or album
- `f` — save current triage progress, keep the remaining tracks unresolved, sync the playlist immediately, and return to the main menu
- `x` — save progress and exit the program

Manual-search results are also scored and sorted. Use `c` to cancel a manual search.

After reaching the end of the missing-track list, the script asks:

```text
Sync this playlist to Plex now? (y/n):
```

### 6. Edit playlist matches

Reviews mappings that already exist for a playlist.

Source and Plex albums are displayed in the same format:

```text
[1] Beautiful Disaster - 311 (Transistor)
    → Beautiful Disaster - 311 (Transistor)
```

When editing a match:

```text
→ Fixing: Summer of Love - 311 (Omaha Sessions)

  Current match: Summer Of Love - 311 (Dammit)

Top Plex candidates:

  [1] Summer Of Love - 311 (Dammit) (100%)
  [2] Summer of Love - 311 (Omaha Sessions) (100%)
  [3] Summer Of Love - 311 (Unity) (100%)
```

If the source service did not provide an album, it is displayed as:

```text
(N/A)
```

The edit screen supports:

- numbered choices — select a Plex candidate
- `s` — skip without changing the current match
- `d` — unlink the current mapping
- `b` — return to the previous screen
- `x` — exit

### 7. Sync history

Shows recently synchronized registered playlists based on their saved `last_synced` timestamps.

### 8. Remove playlist

Removes the playlist from Playlist Bridge's registered configuration after confirmation.

### 9. Settings

Currently provides Plex reconfiguration.

## Command-Line Automation

The script intentionally exposes only fully automated command-line actions.

### Interactive mode

```bash
python sync.py
```

Starts the normal menu.

### Sync every registered playlist

```bash
python sync.py --sync-all
```

This performs a non-interactive sync of all registered playlists.

`--sync-all`:

- Uses existing saved mappings
- Respects manual matches
- Fetches current Spotify/Apple Music playlist contents
- Rebuilds the corresponding Plex playlists
- Updates available metadata/artwork
- Updates last-sync timestamps
- Leaves unmatched tracks recorded for later interactive triage

If Plex is not already configured, `--sync-all` exits with an error rather than opening an interactive setup prompt.

### Help

```bash
python sync.py --help
```

Example:

```text
usage: sync.py [-h] [--sync-all]

Sync Spotify and Apple Music playlists to Plex. Run without arguments for the
interactive menu.

options:
  -h, --help  show this help message and exit
  --sync-all  Sync all registered playlists to Plex non-interactively using
              saved mappings.
```

## Automated Scheduling

Because `--sync-all` is non-interactive, it can be used with cron, systemd timers, Task Scheduler, or similar automation.

Example cron job running every day at 2:00 AM:

```cron
0 2 * * * cd /path/to/playlist-bridge && /path/to/python sync.py --sync-all
```

Running from the project directory is important because Playlist Bridge stores its JSON state files in the **current working directory**.

## Local Data Files

Playlist Bridge keeps its state in JSON files in the directory from which the script is run.

### `config.json`

Stores:

- Plex connection information
- Registered source playlists
- Plex playlist IDs
- Last-sync timestamps

### `mapping.json`

Stores persistent source-track → Plex-track mappings.

A mapping is keyed primarily by:

```text
Title|Artist
```

Manual matches are stored in the same mapping cache and are reused by future normal syncs and `--sync-all`.

If the source service later changes the exact title or artist text, the key may change and the track may need to be matched again.

### `missing_tracks.json`

Stores source tracks that could not be automatically matched.

New missing-track entries preserve:

- Title
- Artist
- Album, when available
- Source track ID, when available

Option 5 can also re-fetch older playlist entries to recover album metadata when possible.

## Matching Logic

Playlist Bridge first checks `mapping.json`. If a mapping already exists for a source track, that Plex track is reused immediately.

For tracks without a saved mapping, candidates are scored using title, artist, and album information.

### Identity score

The base identity score is weighted approximately as:

```text
65% title
35% artist
```

A weak artist match receives an additional penalty.

Automatic matching currently requires an identity score of at least `90`, with an additional minimum title score.

Album information influences **which copy of a song wins**, but does not override a poor title/artist identity.

## Canonical Album Preference

When Plex contains several copies of the same song, Playlist Bridge prefers a normal studio-album copy over special-release copies when possible.

Album-name matches can receive a bonus, but Plex releases receive ranking penalties for certain release types:

| Release type | Penalty |
| --- | ---: |
| Compilation / Greatest Hits / Essential | -14 |
| Live / Unplugged / Concert | -16 |
| Remix | -14 |
| Acoustic / Stripped | -10 |
| Deluxe / Expanded / Anniversary | -7 |
| Remaster | -5 |

For example:

```text
Beautiful Disaster - 311 (Transistor)              100%
Beautiful Disaster - 311 (Greatest Hits ’93–’03)   86%
```

This is a **preference, not a hard exclusion**. If the only good Plex copy is on a Greatest Hits, live, deluxe, or similar release, the matcher can still use it.

The canonical preference is also applied when the source service itself points to a compilation. A Spotify or Apple Music track originating from a Greatest Hits release does not force Plex to choose the Greatest Hits copy when the original studio-album copy is available.

## Match Display

During a normal sync, source and Plex albums are shown inline:

```text
[1/100] ✓ What The?! - 311 (Voyager) → What The?! - 311 (Voyager)
```

If the source album is unavailable:

```text
[2/100] ✓ Example Song - Artist (N/A) → Example Song - Artist (Album)
```

## Playlist Bridgehronization Behavior

A registered Plex playlist is rebuilt to follow the source playlist.

During a sync:

1. The current source playlist is fetched.
2. Saved mappings are reused.
3. New source tracks are matched.
4. Unmatched tracks are stored.
5. If at least one track matched, the existing Plex playlist is cleared.
6. Matched tracks are re-added in source order.
7. Playlist metadata and artwork are refreshed.
8. `last_synced` is updated.

The **source playlist is authoritative** for track membership and ordering.

Tracks that remain unmatched are omitted from the Plex playlist until they are resolved.

If no source tracks can be matched at all, the existing Plex playlist is left unchanged rather than being cleared.

## Playlist Artwork

Playlist Bridge attempts to copy source playlist artwork to Plex.

### Spotify

Spotify artwork is obtained from public Spotify metadata, including Spotify's public oEmbed metadata when available.

### Apple Music

Apple Music pages may expose several images, including wide social-preview graphics that are not suitable as Plex posters.

Playlist Bridge therefore:

- Prefers playlist-level artwork over generic social-preview images
- Reads declared artwork dimensions when available
- Downloads the actual image before upload
- Verifies the real pixel dimensions
- Rejects artwork that is not approximately square
- Rejects very small artwork below 600×600
- Attempts alternate Apple CDN square renditions when appropriate

This prevents a URL that appears to request a square image from being accepted when Apple actually returns a wide banner.

## Plex Behavior

Playlist Bridge currently loads tracks from the **first Plex music library** it finds.

Plex normal audio playlists require a media URI during creation, so a new Plex playlist is created using the first matched source track and the remaining tracks are appended afterward.

When rebuilding an existing playlist, Plex `playlistItemID` values are used for item removal rather than track rating keys.

## Public Playlist Access

Playlist Bridge currently reads public Spotify and Apple Music playlist pages rather than using authenticated Spotify or Apple Music APIs.

That means:

- Spotify Client ID/Secret are not required
- Apple Music developer credentials are not required
- The source playlist must be accessible publicly
- Changes to Spotify or Apple Music's public page structure can require parser updates

## Suggested `.gitignore`

The JSON files contain local configuration and match state and generally should not be committed.

A practical `.gitignore` is:

```gitignore
config.json
mapping.json
missing_tracks.json

spotify-test.py
sync copy.py

__pycache__/
*.pyc
```

If you prefer to ignore every JSON file in the repository instead:

```gitignore
*.json
```

## Troubleshooting

### Plex connection fails

Confirm:

- The Plex URL includes the correct protocol and port, such as `http://server:32400`
- The Plex server is reachable from the machine running the script
- The Plex token is valid

You can reconfigure Plex through Option 9.

### Many tracks remain unmatched

Use Option 5.

It shows the five highest-scoring Plex candidates even when their scores are below the automatic match threshold. You can also search Plex manually by title, artist, or album.

### A track is mapped to the wrong album

Use Option 6 to review and replace the saved match.

Once corrected, the chosen Plex track ID is persisted in `mapping.json` and future syncs reuse it.

### A manual match does not seem to be used

Mappings are keyed by the source track's exact `Title|Artist` combination. If Spotify or Apple Music changes either field, the new source text may produce a new key.

### Playlist artwork looks wrong

During Apple Music artwork processing, check the reported actual pixel dimensions. Non-square Apple preview images are rejected before upload and alternate square renditions are attempted.

### `--sync-all` asks for input

It should not ask for Plex setup. Ensure `config.json` already contains a valid Plex URL and token.

## Security

`config.json` contains your Plex connection information, including the Plex token.

Do not commit or share it publicly.

`mapping.json` and `missing_tracks.json` normally do not contain Plex credentials, but they contain local library and listening metadata and are also best kept out of source control.

## License

Playlist Bridge is licensed under the **GNU General Public License v2.0 only** (`GPL-2.0-only`).

See [`LICENSE`](LICENSE) for the full license text.
