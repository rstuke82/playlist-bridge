# Playlist Bridge

**Version 1.01**

Playlist Bridge syncs public **Spotify** and **Apple Music** playlists to your local music library through Plex.

It matches source tracks against your library, preserves manual match decisions, prefers better album copies when duplicates exist, keeps playlist order in sync, and copies available playlist artwork.

## Features

- Spotify playlist support
- Apple Music playlist support, including Replay playlists
- No Spotify or Apple Music API credentials required
- Fuzzy track matching with title, artist, and album awareness
- Parenthetical and featured-artist normalization
- Remix and live-version intent matching
- Soundtrack and `Various Artists` track-artist handling
- Preference for original studio-album copies when appropriate
- Persistent manual match overrides
- Interactive review of missing or incorrect matches
- Scored Plex candidates for difficult tracks
- Manual Plex search
- Candidate lists hide results below 50%
- Playlist artwork synchronization
- Apple artwork quality and dimension checks
- Playlist order synchronization
- Last-sync history
- Automatic cleanup of common text-encoding glitches
- Fully automated `--sync-all` mode

## Requirements

- Python 3
- A Plex Media Server containing your music library
- A Plex authentication token
- Public Spotify and/or Apple Music playlist URLs

Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

## Installation

Clone or download Playlist Bridge, then open a terminal in the project directory.

Optionally create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start Playlist Bridge:

```bash
python sync.py
```

## First-Time Plex Setup

The first time Playlist Bridge needs Plex, it asks for:

```text
Plex server URL (e.g., http://localhost:32400):
Plex API token:
```

Playlist Bridge verifies the connection before saving it.

You can change the Plex connection later from:

```text
[9] Settings
```

## Main Menu

Running:

```bash
python sync.py
```

opens the interactive menu:

```text
==================================================
Playlist Bridge v1.01 - Spotify/Apple Music to Plex
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

## Adding a Playlist

Choose:

```text
[1] Add new Spotify/Apple Music playlist
```

Then paste a public playlist URL.

Spotify example:

```text
https://open.spotify.com/playlist/7eahWLng9go8LDR5gcW6A3?si=...
```

Apple Music example:

```text
https://music.apple.com/us/playlist/replay-2019/pl.rp-NLLMIo0EvBxO
```

Playlist Bridge accepts normal Spotify playlist URLs with query parameters and Apple Music playlist IDs that contain characters such as hyphens.

When a playlist is added, Playlist Bridge:

1. Fetches the source playlist.
2. Scans your Plex music library.
3. Matches source tracks to Plex tracks.
4. Saves unresolved tracks for later review.
5. Creates the Plex playlist.
6. Adds matched tracks in source order.
7. Applies available playlist metadata and artwork.
8. Registers the playlist for future syncs.

## Syncing Playlists

### Sync all playlists

Choose:

```text
[2] Sync all playlists
```

Every registered playlist is refreshed.

Saved mappings are reused first, including matches you selected manually in Options 5 and 6.

### Sync one playlist

Choose:

```text
[3] Sync specific playlist
```

Then select the playlist you want to refresh.

During a normal sync, Playlist Bridge shows the source and matched destination track:

```text
[1/100] ✓ What The?! - 311 (Voyager) → What The?! - 311 (Voyager)
```

A green `✓` means the track matched.

A red `✗` means no suitable automatic match was found:

```text
[98/100] ✗ HandClap - Fitz and The Tantrums (Fitz & the Tantrums (Deluxe))
```

If the source service does not provide an album, the source album appears as:

```text
(N/A)
```

## Resolving Missing Tracks

Choose:

```text
[5] Resolve missing tracks
```

Playlist Bridge shows playlists with unresolved tracks and lets you work through them one at a time.

For each unresolved track, Playlist Bridge shows the best candidate matches scoring **50% or higher**. Lower-scoring results are hidden.

Example:

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

Numbers are used only to select numbered items.

Controls:

- `s` — skip the current track and leave it unresolved
- `m` — manually search Plex by title, artist, or album
- `f` — save your progress, sync the playlist immediately, and return to the main menu
- `x` — save progress and exit

Manual search results are also scored and sorted.

Use:

```text
[c] Cancel manual search
```

to leave manual search without selecting a result.

If you reach the end of the unresolved list, Playlist Bridge asks:

```text
Sync this playlist to Plex now? (y/n):
```

You can return to Option 5 later and continue resolving anything that remains.

## Editing Existing Matches

Choose:

```text
[6] Edit playlist matches
```

This lets you review tracks that already have saved mappings.

Example:

```text
[1] Beautiful Disaster - 311 (Transistor)
    → Beautiful Disaster - 311 (Transistor)
```

Select a track to see alternative Plex candidates:

```text
→ Fixing: Summer of Love - 311 (Omaha Sessions)

  Current match: Summer Of Love - 311 (Dammit)

Top Plex candidates:

  [1] Summer Of Love - 311 (Dammit) (100%)
  [2] Summer of Love - 311 (Omaha Sessions) (100%)
  [3] Summer Of Love - 311 (Unity) (100%)
```

Controls include:

- numbered choices — select a different Plex match
- `s` — leave the current match unchanged
- `d` — unlink the saved match
- `b` — go back
- `x` — exit

Once you choose a manual match, Playlist Bridge remembers that Plex track for future syncs.

## How Matching Works

Playlist Bridge first checks whether you have already saved a match for the source track.

If you have, that match is reused.

If not, Playlist Bridge compares:

- Track title
- Track artist
- Album, when available

Title and artist identity are the primary signals. Album information helps choose between multiple copies of the same song rather than rescuing a clearly different title.

### Parentheses and alternate title formats

Version 1.01 improves matching when services represent the same song differently.

Examples:

```text
Austin (Boots Stop Workin')  ↔  Austin
Dark Sky (feat. S.A. Martinez)  ↔  Dark Sky
Song (Remastered 2011)  ↔  Song
Song - Radio Edit  ↔  Song
```

Playlist Bridge keeps the original source title for display and saved mappings. Normalized title forms are used only while scoring candidates.

The normalization is intentionally directional for unknown parenthetical text. A source title such as:

```text
Austin (Boots Stop Workin')
```

can match a plain destination title:

```text
Austin
```

but a plain source title is not automatically treated as identical to a destination-only alternate version such as:

```text
Bring Me to Life
Bring Me to Life (Synthesis)
```

That helps avoid choosing alternate arrangements or rerecordings just because their base titles are the same.

### Featured artists

Featured-credit variations such as `feat.`, `ft.`, `featuring`, and `with` are handled more flexibly.

This also applies when the source service lists featured performers as full co-artists.

For example:

```text
Take a Chance on Me (feat. Jewel)
AWOLNATION & Jewel
```

can match:

```text
Take a Chance on Me
AWOLNATION
```

The same logic handles cases where the featured performer named in the title differs from the additional artist text supplied by the source service.

### Remix and live versions

When the **source title explicitly requests a remix or live version**, Playlist Bridge treats that as intentional version information.

For example:

```text
Dracula (JENNIE Remix)
```

prefers:

```text
Dracula (JENNIE remix)
```

over a plain `Dracula` track, even if both happen to be stored on a remix album.

The ranking preference is:

```text
1. Destination title explicitly identifies the remix/live version
2. Destination title is plain, but its album identifies the version
3. Neither title nor album identifies the requested version
```

The reverse is also true: if the source does **not** request a live or remix version, a destination title that explicitly says `Live` or `Remix` is de-prioritized.

This prevents cases such as:

```text
Going Under (Remastered 2023)
```

from being treated as equivalent to:

```text
Going Under (live acoustic – 2003)
```

A title such as `Live Through This` is not treated as a live-version marker merely because it contains the word `Live`.

### Soundtracks and Various Artists albums

Plex can store a soundtrack or compilation under the album artist `Various Artists` while retaining the real performer as the individual track artist.

Playlist Bridge uses the Plex **track artist** when available.

So a source track such as:

```text
Ironic - Avril Lavigne
```

can correctly match a soundtrack entry whose album artist is `Various Artists`, while still displaying and scoring against `Avril Lavigne` as the track artist.

### Candidate score display

Options 5 and 6 show the strongest Plex candidates for a track.

Candidates scoring below **50%** are hidden so obviously unrelated library results do not clutter the list.

Low-confidence candidates that remain above the cutoff are still clearly labeled.

### Text cleanup

Playlist Bridge repairs common UTF-8/Latin-1 display corruption before matching and displaying metadata.

For example:

```text
We Didnât Start The Fire
```

is repaired to:

```text
We Didn’t Start The Fire
```

Already-correct Unicode text is left unchanged.

## Album Preference

When your library contains multiple copies of the same song, Playlist Bridge generally prefers a normal studio-album copy over special-release copies when the source does not explicitly request a special version.

Examples of lower-priority releases include:

- Greatest Hits / Best Of / Essential collections
- Live albums
- Remix releases
- Acoustic or stripped releases
- Deluxe or expanded editions
- Remasters

Typical ranking behavior:

```text
Beautiful Disaster - 311 (Transistor)
    preferred over
Beautiful Disaster - 311 (Greatest Hits ’93–’03)
```

This is a preference, not a hard rule.

If the source explicitly identifies a remix or live recording in the **track title**, that version intent takes priority over the normal studio-copy preference.

If the only good copy in your library is from a Greatest Hits, live, deluxe, remastered, or similar release, Playlist Bridge can still use it.

The source service also does not force a compilation copy. If Spotify or Apple Music points to a Greatest Hits release but Plex also contains the original studio-album version, Playlist Bridge can prefer the studio version.

## Playlist Artwork

Playlist Bridge attempts to copy playlist artwork from the source service.

### Spotify

Spotify artwork is retrieved from public Spotify playlist metadata.

### Apple Music

Apple Music sometimes exposes wide social-preview images instead of square playlist covers.

Playlist Bridge checks the actual downloaded image before sending it to Plex.

It can:

- Prefer playlist-level artwork
- Verify actual pixel dimensions
- Reject wide preview/banner images
- Reject very small images
- Try alternate square Apple artwork renditions

This helps prevent low-quality or badly cropped playlist posters.

## Registered Playlists

Choose:

```text
[4] View registered playlists
```

to see:

- Playlist name
- Source service
- Source URL
- Last sync time

Service names are displayed consistently as:

```text
Spotify
Apple Music
```

## Sync History

Choose:

```text
[7] Sync history
```

to view recently synchronized playlists.

## Removing a Playlist

Choose:

```text
[8] Remove playlist
```

to remove a playlist from Playlist Bridge after confirmation.

This removes the registration from Playlist Bridge. It does not delete the original Spotify or Apple Music playlist.

## Automated Sync

Playlist Bridge includes a non-interactive mode for scheduled syncing.

Sync every registered playlist:

```bash
python sync.py --sync-all
```

This:

- Uses saved mappings
- Respects manual matches
- Fetches current source playlist contents
- Refreshes Plex playlists
- Updates available metadata and artwork
- Records unresolved tracks for later review
- Updates last-sync timestamps

If Plex is not already configured, `--sync-all` exits instead of opening an interactive setup prompt.

### Help

```bash
python sync.py --help
```

Example:

```text
usage: sync.py [-h] [--sync-all]

Playlist Bridge v1.01 - Sync Spotify and Apple Music playlists to Plex. Run
without arguments for the interactive menu.

options:
  -h, --help  show this help message and exit
  --sync-all  Sync all registered playlists to Plex non-interactively using
              saved mappings.
```

## Scheduled Syncing

Because `--sync-all` is non-interactive, it can be run from cron, systemd timers, Task Scheduler, or another scheduler.

Example cron job running every day at 2:00 AM:

```cron
0 2 * * * cd /path/to/playlist-bridge && /path/to/python sync.py --sync-all
```

Run Playlist Bridge from its project directory so it can find its saved configuration and matching data.

## Saved Data

Playlist Bridge stores its local state in:

```text
config.json
mapping.json
missing_tracks.json
```

These files contain your Plex configuration, registered playlists, saved match decisions, and unresolved tracks.

Do not delete them unless you intentionally want to reset that information.

Manual matches are stored persistently and are reused during normal syncs and `--sync-all`.

## Public Playlist Requirement

Playlist Bridge reads public Spotify and Apple Music playlist pages.

You do not need Spotify developer credentials or Apple Music developer credentials.

The playlist must be publicly accessible.

If Spotify or Apple Music changes the structure of its public playlist pages, a future Playlist Bridge update may be required.

## Troubleshooting

### Plex connection fails

Check that:

- The Plex server URL is correct
- The server is reachable from the computer running Playlist Bridge
- Your Plex token is valid

You can reconfigure Plex through Option 9.

### A lot of tracks are missing

Use Option 5.

Playlist Bridge shows its best Plex candidates scoring 50% or higher.

You can also manually search by title, artist, or album.

### A track matched the wrong copy

Use Option 6 and choose the correct Plex track.

Your corrected match will be saved and reused during future syncs.

### A remix or live version matched incorrectly

Check whether the source track title itself identifies the version.

Playlist Bridge treats title-level `Remix` and `Live` markers as intentional. A plain source title will normally prefer a plain/studio copy, while a source title explicitly marked as a remix or live version will prefer that version.

If the library metadata is unusual, use Option 6 to save the desired Plex copy.

### A soundtrack track shows Various Artists

Playlist Bridge uses Plex's individual track artist when Plex provides one.

If a soundtrack entry still appears only as `Various Artists`, check the track metadata in Plex and make sure the individual track artist is populated.

### A manual match is no longer being used

Playlist Bridge saves mappings using the source title and artist.

If Spotify or Apple Music later changes the exact title or artist text, Playlist Bridge may see it as a new source track and require another match.

### Text contains characters such as `â`

Version 1.01 automatically repairs common UTF-8/Latin-1 encoding glitches before matching and display.

If malformed text still appears, it may already be stored that way in the original source or Plex metadata.

### Apple Music artwork looks wrong

Watch the artwork messages during sync.

Playlist Bridge reports actual image dimensions and rejects unsuitable wide or low-resolution artwork before uploading it.

### `--sync-all` stops because Plex is not configured

Run:

```bash
python sync.py
```

and configure Plex interactively first.

Then run `--sync-all` again.

## Security

`config.json` contains your Plex connection information, including your Plex token.

Keep it private and do not share it publicly.

The other saved data files contain information about your local music library and matching decisions and should also be treated as private local data.

## License

Playlist Bridge is licensed under the **GNU General Public License v2.0 only** (`GPL-2.0-only`).

See [`LICENSE`](LICENSE) for the full license text.
