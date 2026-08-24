# Playlist Bridge

**Version 1.3.5**

Playlist Bridge syncs public **Spotify** and **Apple Music** playlists to your local music library through Plex.

It matches source tracks against your Plex library, preserves manual match decisions, prefers appropriate album/recording copies, keeps playlist order synchronized, copies meaningful playlist metadata and artwork, and tracks changes between syncs.

## Features

- Spotify playlist support
- Apple Music playlist support, including Replay playlists
- No Spotify or Apple Music API credentials required
- Fuzzy track matching with title, artist, album, and recording-version awareness
- Parenthetical and featured-artist normalization
- Explicit version handling for live, remix/mix, acoustic, demo, and branded session recordings
- Canonical studio-album preference when the source does not request a special version
- Soundtrack and `Various Artists` track-artist handling
- Persistent automatic and manual match mappings
- Interactive review of missing or incorrect matches
- Scored Plex candidates for difficult tracks
- Manual Plex search
- Candidate lists hide results below 50%
- Deduplicated all-missing-tracks view across registered playlists
- Playlist artwork synchronization
- Playlist description synchronization when the source provides a meaningful description
- Generic source descriptions such as `Playlist · 86 Songs` are omitted
- Playlist order synchronization
- Source playlist `ADDED` / `REMOVED` tracking
- Match-state `NEW` / `LOST` tracking
- End-of-sync change summaries
- Oldest-first playlist sorting by last sync
- Last match-attempt tracking for unresolved-track triage
- Multiple-playlist selection for Option 3
- Match provenance: `automatic`, `manual`, and protected `legacy`
- Clear only automatic mappings while preserving manual and legacy mappings
- Versioned JSON state with automatic legacy migration and one-time backups
- Fully automated `--sync-all` mode
- Read-only `--sync-all --dry-run` mode
- Automatic cleanup of common text-encoding glitches
- Predictable one-level Back behavior throughout submenus

## What's New in 1.3.5

Version 1.3.5 focuses on terminal presentation, Apple Music artwork handling, and read-only diagnostic improvements.

### Terminal UI polish

Playlist Bridge now uses more consistent terminal styling:

- Spotify service labels use Spotify green
- Apple Music service labels use Apple Music red/pink
- Auto sync `ON` is green and `OFF` is red
- registered-playlist status uses a filled status dot for both states
- match provenance is color-coded consistently: automatic, manual, and legacy
- match/provenance summaries are aligned for easier scanning
- secondary metadata such as timestamps, URLs, albums, and `N/A` values is visually subdued
- long sync operations use consistent section dividers

These are presentation-only changes and do not alter matching or sync behavior.

### Better Apple Music playlist artwork

Apple Music sometimes exposes a wide social-preview image such as `1200x630` instead of square playlist artwork.

Version 1.3.5 improves that flow by:

- correctly generating Apple CDN artwork alternatives even when the source URL contains query parameters such as `?l=en-US`
- preferring Apple's square `cc` crop rendition when available
- preserving URL query parameters when generating alternate Apple artwork URLs
- falling back to a local center crop when Apple does not provide a usable square image
- preserving the full shorter image dimension without stretching

For example, a `1200x630` source image can be center-cropped to a true `630x630` Plex playlist poster.

Local center cropping uses Pillow.

### Internal read-only diagnostics

The read-only diagnostic tools were expanded to support:

- testing the matching behavior of an unregistered Spotify or Apple Music playlist without creating or registering it
- a consolidated album playlist-coverage report
- artist-grouped album coverage with per-album covered/total track counts
- album coverage scoped only to Plex playlists registered with Playlist Bridge

Unrelated Plex playlists, smart playlists, and generated playlists no longer affect Playlist Bridge's album-coverage diagnostic unless that Plex playlist is actually registered in Playlist Bridge.

No state-schema change is required for 1.3.5.

## What's New in 1.3

Version 1.3 adds two workflow controls: permanent per-playlist track ignores and per-playlist automatic-sync participation.

### Permanently ignore a source track

While resolving missing tracks in Option 5 or fixing an existing match in Option 6, you can now choose:

```text
[i] Ignore permanently
```

An ignored track is scoped to that source playlist. Playlist Bridge:

- stops trying to match it automatically
- removes any existing saved mapping/provenance
- stops listing it as unresolved
- excludes it from the destination Plex playlist on future syncs
- remembers the ignore until you explicitly restore it

Ignored tracks are stored in:

```text
ignored_tracks.json
```

Manage them from:

```text
[9] Settings
[4] Manage ignored tracks
```

You can restore individual ignored tracks or restore all ignored tracks for a playlist.

### One-time / manual-only playlists

Each registered playlist can now have:

```text
Auto sync: ON
```

or:

```text
Auto sync: OFF
```

A playlist with Auto sync OFF remains fully registered. Its mappings, ignored tracks, source snapshots, match history, and Plex playlist are retained.

The difference is only automatic participation:

```text
python sync.py --sync-all
```

skips Auto sync OFF playlists, which also means normal cron jobs using `--sync-all` skip them.

Manual actions remain available:

- interactive **Sync all playlists** still syncs every registered playlist
- **Sync specific playlist** can sync an Auto sync OFF playlist at any time

New playlists ask after the initial import whether they should participate in automatic `--sync-all` / cron runs. Choosing no gives you the one-time/manual-only behavior while still keeping the playlist registered.

Manage this later from:

```text
[9] Settings
[5] Manage auto-sync
```

Existing pre-1.3 playlists default to Auto sync ON.

### State schema 2

Version 1.3 uses state schema 2.

Schema 2 adds `ignored_tracks.json` and the optional per-playlist `auto_sync` flag. Existing schema-0 and schema-1 data migrates without changing its payload semantics.

Before rewriting older state, Playlist Bridge creates one-time backups such as:

```text
config.json.pre-schema-2.bak
mapping.json.pre-schema-2.bak
```

Dry run remains read-only and does not perform schema migration.

### Also included from the 1.22 line

The current 1.3 code also includes the 1.22 improvements:

- LOST tracks retain and display the previous Plex match details when available
- LOST status remains visible during manual review
- legacy mappings are revalidated only when they are legacy; if the current automatic matcher independently chooses the exact same Plex track, the mapping is promoted to `automatic`
- manual and already-automatic mappings are not subjected to that legacy validation

## Requirements

- Python 3
- A Plex Media Server containing your music library
- A Plex authentication token
- Public Spotify and/or Apple Music playlist URLs
- Pillow (installed from `requirements.txt`) for local square artwork cropping

Install dependencies with:

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

You can configure or update Plex later from:

```text
[9] Settings
[1] Configure Plex
```

## Main Menu

Running:

```bash
python sync.py
```

opens:

```text
==================================================
Playlist Bridge v1.3.5 - Spotify/Apple Music to Plex
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

Playlist Bridge accepts Spotify playlist URLs with query parameters and Apple Music playlist IDs containing characters such as hyphens.

When a playlist is added, Playlist Bridge:

1. Fetches the source playlist.
2. Scans the Plex music library.
3. Matches source tracks to Plex tracks.
4. Saves unresolved tracks for later review.
5. Creates the Plex playlist.
6. Adds matched tracks in source order.
7. Applies meaningful source metadata and available artwork.
8. Registers the playlist for future syncs.
9. Establishes its initial source snapshot.

## Syncing Playlists

### Sync all playlists

Choose:

```text
[2] Sync all playlists
```

Every registered playlist is refreshed.

Saved mappings are reused first, including matches you selected manually.

### Sync selected playlists

Choose:

```text
[3] Sync specific playlist
```

The picker is sorted by oldest last-sync time, with `Never` first:

```text
[1] Replay 2015 (Apple Music) - Last sync: Never
[2] Replay 2022 (Apple Music) - Last sync: 2026-08-18 13:45
[3] Replay 2025 (Apple Music) - Last sync: 2026-08-21 08:10
```

Select one playlist:

```text
2
```

or several:

```text
1,3,5
```

Ranges are also accepted:

```text
1-3
```

During a normal sync, Playlist Bridge shows each source track and its Plex destination.

A normal matched track appears with a green checkmark.

A newly created mapping may be marked:

```text
✓ NEW
```

A track newly added to the source playlist may also be marked:

```text
ADDED
```

Those markers can appear together because source changes and mapping changes are tracked independently.

A red `✗` means no suitable match was found.

If a previously mapped track can no longer safely use its saved Plex target, it may be marked:

```text
✗ LOST
```

If the source service does not provide an album, the source album appears as:

```text
(N/A)
```

## Source Playlist Changes

After Playlist Bridge has a previous source snapshot, it compares the current playlist against the prior successful sync.

Added tracks are reported as:

```text
ADDED   Song - Artist (Album)
```

Removed tracks are reported as:

```text
REMOVED Song - Artist (Album)
```

The first tracked sync for an older installation establishes a baseline instead of reporting the entire playlist as added.

Source snapshots are updated only during real syncs, not dry runs.

## Resolving Missing Tracks

Choose:

```text
[5] Resolve missing tracks
```

Playlist Bridge shows playlists containing unresolved tracks.

The list is sorted by **Last match attempt**, with `Never` first:

```text
[1] Replay 2015 (Apple Music) - 9 unmatched - Last match attempt: Never
[2] Replay 2025 (Apple Music) - 7 unmatched - Last match attempt: 2026-08-20 20:14
```

The timestamp changes only when you explicitly choose:

```text
[t] Start triage
```

Simply opening a missing-track overview and backing out does not count as an attempt.

### All missing tracks

Option 5 also provides:

```text
[a] All missing tracks (deduped)
```

This combines unresolved tracks across all registered playlists.

Tracks are deduplicated by normalized title + artist. If different occurrences contain different album metadata, Playlist Bridge prefers a meaningful album over `N/A` for display.

Each entry reports how many playlists and unresolved occurrences contain that track.

### Per-playlist triage

After selecting a playlist, Playlist Bridge first shows the complete unresolved list before scanning Plex:

```text
Missing tracks for 'Replay 2025' (9 total):

[1] Example Song - Example Artist (Example Album)
[2] Another Song - Another Artist (N/A)

[t] Start triage
[b] Back
[x] Exit
```

Choosing `b` or pressing Enter returns to the playlists-with-unmatched-tracks list.

During triage, candidate matches scoring below 50% are hidden.

Controls include:

- numbered choice — select a displayed Plex candidate
- `s` — leave the track unresolved
- `m` — manually search Plex by title, artist, or album
- `i` — permanently ignore this source track for this playlist
- `f` — save triage progress and sync the playlist now
- `x` — save progress and exit

A match explicitly selected during triage is stored as a **manual** mapping.

## Permanently Ignoring Tracks

Playlist Bridge can permanently ignore a source track for one playlist.

In Option 5 and Option 6, choose:

```text
[i] Ignore permanently
```

An ignored track:

- is not automatically matched
- does not appear as unresolved
- is not added to the Plex destination playlist
- remains ignored across future syncs
- does not affect the same song in other source playlists

Manage ignored tracks from:

```text
[9] Settings
[4] Manage ignored tracks
```

Restoring an ignored track makes it eligible for normal matching on the next sync.

## Editing Existing Matches

Choose:

```text
[6] Edit playlist matches
```

The playlist list shows mapping provenance counts:

```text
[1] Replay 2025 (Apple Music) - 91 current matches (78 auto, 8 manual, 5 legacy)
```

After selecting a playlist, each current mapping shows its provenance:

```text
[1] Example Song - Example Artist (Example Album)
    → Example Song - Example Artist (Example Album) [manual]
```

Select a track to view alternative Plex candidates.

Controls include:

- numbered choice — choose or confirm a Plex match
- `s` — leave the current match unchanged
- `d` — unlink the saved mapping
- `i` — permanently ignore this source track for this playlist
- `b` or Enter — go back one level
- `x` — exit

A match explicitly selected or confirmed here becomes **manual**.

After changes are saved, Playlist Bridge can perform one normal full playlist sync using the updated mappings.

## How Matching Works

Playlist Bridge checks saved mappings first.

If no usable saved mapping exists, it compares:

- Track title
- Track artist
- Album, when available
- Explicit recording/version intent

Title and artist identity remain the primary signals. Album information helps choose among plausible copies of the same song rather than rescuing a clearly different title.

### Parentheses and alternate title formats

Playlist Bridge can normalize common metadata differences while keeping the original source title for display and saved mappings.

Examples:

```text
Austin (Boots Stop Workin')  ↔  Austin
Dark Sky (feat. S.A. Martinez)  ↔  Dark Sky
Song (Remastered 2011)  ↔  Song
Song - Radio Edit  ↔  Song
```

Unknown destination-only alternate labels are handled conservatively, so a plain source title is not automatically treated as identical to every alternate arrangement with the same base title.

### Featured artists

Feature credits such as `feat.`, `ft.`, `featuring`, and `with` are treated as credit metadata rather than recording-version intent.

This allows equivalent metadata layouts across services to match even when the guest appears in the source title, artist field, destination artist field, or only one service.

### Recording/version intent

Explicit special recordings are protected.

Supported intent includes:

- remix / named mix
- live
- acoustic / stripped
- demo
- iTunes Session
- Apple Music Session
- Spotify Session / Sessions

If the source explicitly requests one of these and Plex only has a plain copy with no matching recording intent, Playlist Bridge can leave the source track unmatched rather than silently substituting the wrong recording.

Generic album-era session labels such as `Evolver Sessions` are treated as provenance rather than automatically as a branded alternate-performance recording.

### Soundtracks and Various Artists

When Plex has a compilation or soundtrack whose album artist is `Various Artists`, Playlist Bridge uses the individual track artist when Plex provides it.

### Candidate score display

Options 5 and 6 show the strongest candidate results.

Candidates below **50%** are hidden.

## Album Preference

When multiple copies of the same recording exist, Playlist Bridge generally prefers a normal studio-album copy over a special-release copy unless the source explicitly requests the special recording.

Lower-priority release types can include:

- Greatest Hits / Best Of / Essential collections
- Live albums
- Remix releases
- Acoustic or stripped releases
- Deluxe or expanded editions
- Remasters

This is a ranking preference, not a blanket rejection.

A source compilation does not force the Plex compilation copy if the canonical studio version is a better destination.

## Playlist Metadata and Artwork

Playlist Bridge updates source metadata and artwork during actual playlist creation/sync operations.

Artwork discovery is skipped during matching-review and dry-run paths.

### Descriptions

A meaningful source playlist description is copied to Plex.

Service-generated labels such as:

```text
Playlist · 86 Songs
86 Songs
Playlist · 86 Songs · 5 hr 12 min
```

are intentionally omitted because Plex already identifies the object as a playlist and displays its item count.

If the source exposes no meaningful description, the Plex description is left empty.

### Text cleanup

Common UTF-8/Latin-1 mojibake is repaired before matching/display and before playlist metadata is sent to Plex.

For example:

```text
We Didnât Start The Fire
```

becomes:

```text
We Didn’t Start The Fire
```

and:

```text
Playlist Â· 86 Songs
```

is repaired before generic-description filtering.

### Spotify artwork

Spotify artwork is retrieved from public Spotify playlist metadata.

### Apple Music artwork

Apple Music can expose wide social-preview images instead of square playlist art.

Playlist Bridge checks actual image dimensions and can:

- prefer playlist-level square artwork
- reject very small images
- generate Apple CDN square-crop alternatives even when the source URL contains query parameters
- prefer Apple's square `cc` rendition when available
- locally center-crop a sufficiently large wide image when no suitable square rendition is available
- upload the resulting square poster to Plex without stretching the artwork

## Registered Playlists

Choose:

```text
[4] View registered playlists
```

Registered playlists are shown oldest-last-sync first, with `Never` first.

The list includes:

- Playlist name
- Source service
- Source URL
- Last sync time
- Auto sync ON/OFF

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

to remove the registration from Playlist Bridge after confirmation.

This does not delete the original Spotify or Apple Music playlist.

## Settings

Choose:

```text
[9] Settings
```

The Settings menu includes:

```text
[1] Configure Plex
[2] Clear all matching for a playlist
[3] Clear automatic matches
[4] Manage ignored tracks
[5] Manage auto-sync
[b] Back
[x] Exit
```

### Configure Plex

Use **Configure Plex** to set or replace the Plex server URL and token.

Existing playlist registrations and saved mappings are not removed.

### Clear all matching for a playlist

This removes that playlist's saved mappings and unresolved state so the next sync can rematch from scratch.

You can clear one playlist or all registered playlists.

This does not remove the playlist registration or modify the Plex playlist immediately.

### Clear automatic matches

This removes only mappings explicitly recorded as `automatic`.

It preserves:

- `manual` mappings
- `legacy` mappings whose original provenance cannot be known safely

The cleared tracks are matched again on the next sync.

### Manage ignored tracks

Use **Manage ignored tracks** to review permanent per-playlist ignores.

You can restore one ignored track at a time or restore all ignored tracks for a playlist.

### Manage auto-sync

Use **Manage auto-sync** to toggle whether a registered playlist participates in automated `--sync-all` runs.

```text
Auto sync: ON
```

means the playlist participates in cron / `--sync-all`.

```text
Auto sync: OFF
```

means it remains registered but automated `--sync-all` skips it.

Manual interactive synchronization is still allowed.

## Automated Sync

Sync every registered playlist whose Auto sync setting is ON:

```bash
python sync.py --sync-all
```

This uses saved mappings, refreshes source contents, updates Plex playlists, records unresolved tracks, updates change-tracking state, and updates last-sync timestamps. Playlists with Auto sync OFF are skipped.

If Plex is not already configured, `--sync-all` exits rather than opening interactive setup.

### Dry run

Evaluate all registered playlists without changing Plex or local state:

```bash
python sync.py --sync-all --dry-run
```

Dry run:

- fetches current source playlist contents
- scans Plex
- performs normal matching analysis
- reports matching and source-change information
- does not clear or rebuild Plex playlists
- does not update Plex metadata/artwork
- does not update timestamps
- does not write any JSON state, including ignored-track state
- does not perform legacy schema migration

`--dry-run` must be used together with `--sync-all`.

### Help

```bash
python sync.py --help
```

The public command-line options are:

```text
-h, --help
--sync-all
--dry-run
```

## Scheduled Syncing

Because `--sync-all` is non-interactive, it can be run from cron, systemd timers, Task Scheduler, or another scheduler.

Example daily cron job at 2:00 AM:

```cron
0 2 * * * cd /path/to/playlist-bridge && /path/to/playlist-bridge/.venv/bin/python sync.py --sync-all >> /path/to/playlist-bridge/cron.log 2>&1
```

Run Playlist Bridge from its project directory because saved state is stored relative to the current working directory.

## Saved Data

Playlist Bridge stores persistent state in:

```text
config.json
mapping.json
missing_tracks.json
match_metadata.json
source_snapshots.json
ignored_tracks.json
```

Purpose:

- `config.json` — Plex configuration and registered playlists
- `mapping.json` — source-track to Plex-track mappings
- `missing_tracks.json` — unresolved source tracks
- `match_metadata.json` — automatic/manual provenance for mappings
- `source_snapshots.json` — previous source playlist contents for `ADDED` / `REMOVED` comparison
- `ignored_tracks.json` — per-playlist source tracks that should never be matched or added unless restored

### JSON schema

Schema 2 uses:

```json
{
  "_schema_version": 2,
  "data": {
    "...": "..."
  }
}
```

Older unwrapped Playlist Bridge JSON loads as schema 0. Versioned schema-1 state also upgrades automatically.

The first normal save under 1.3 migrates older state and creates one-time backups such as:

```text
config.json.pre-schema-2.bak
mapping.json.pre-schema-2.bak
missing_tracks.json.pre-schema-2.bak
```

The new `ignored_tracks.json` file is created as needed and does not require a migration backup when it did not previously exist.

If a file declares a schema newer than this Playlist Bridge build understands, the application stops rather than overwriting it.

## Upgrading

You can replace the old `sync.py` with 1.3 and keep your existing state files.

No reset is required.

Existing playlists that do not yet have an `auto_sync` field default to Auto sync ON.

Existing saved mappings continue to load normally. Legacy provenance behavior remains conservative, with one exception: during a normal sync, a valid legacy mapping is independently checked by the current matcher. If the matcher chooses the exact same Plex track, that mapping can be promoted to `automatic`. If it chooses something else or cannot confidently match, the saved mapping remains unchanged and stays `legacy`.

If you want to verify source fetching and matching before writing state:

```bash
python sync.py --sync-all --dry-run
```

Dry run does not modify Plex or write/migrate JSON state.

The first normal state save performs any required schema-2 migration and creates one-time backups.

## Public Playlist Requirement

Playlist Bridge reads public Spotify and Apple Music playlist pages.

You do not need Spotify developer credentials or Apple Music developer credentials.

The playlist must be publicly accessible.

If either service changes the structure of its public pages, a future Playlist Bridge update may be required.

## Troubleshooting

### Plex connection fails

Check that:

- the Plex server URL is correct
- the server is reachable from the computer running Playlist Bridge
- your Plex token is valid

You can update Plex through Option 9 → Configure Plex.

### A lot of tracks are missing

Use Option 5.

Review the complete unresolved list, use the deduplicated all-missing view, then start triage when ready.

### A track matched the wrong copy

Use Option 6 and select the correct Plex track.

Explicit choices are stored as manual mappings and reused on future syncs.

### A demo/acoustic/live/remix/session version is unmatched

This can be intentional.

If the source explicitly requests a distinct recording and Plex only contains a plain version, Playlist Bridge prefers leaving it unresolved instead of silently choosing the wrong recording.

Use Option 5 or Option 6 if your Plex metadata identifies the correct recording in an unusual way.

### I want to rematch automatic choices but keep my corrections

Open:

```text
[9] Settings
[3] Clear automatic matches
```

Manual and legacy mappings remain protected.

### I want to reset all matching for a playlist

Open:

```text
[9] Settings
[2] Clear all matching for a playlist
```

The playlist registration and Plex playlist remain in place.

### Source changes are all showing baseline

That is expected on the first tracked 1.2 sync for an existing playlist.

The next sync has a prior source snapshot to compare against.

### A manual mapping's Plex ID disappeared

Playlist Bridge does not silently replace a stale manual or legacy mapping with a new automatic guess.

The track is surfaced for review.

### Text contains characters such as `â` or `Â·`

Playlist Bridge repairs common UTF-8/Latin-1 encoding corruption before matching and metadata updates.

### Playlist description is just `Playlist · N Songs`

Playlist Bridge suppresses that generic source-generated metadata. A meaningful source description is preserved; otherwise Plex receives an empty description.

### Apple Music artwork looks wrong

Watch the artwork messages during sync.

Playlist Bridge validates actual image dimensions. Wide Apple Music artwork is first retried through square Apple CDN variants and, when necessary, center-cropped locally to a square poster. Very small artwork is still rejected.

### `--sync-all` stops because Plex is not configured

Run:

```bash
python sync.py
```

configure Plex interactively, then run `--sync-all` again.

### An ignored track is missing from Plex

That is expected. Permanently ignored tracks are deliberately excluded from the destination playlist.

Restore it from:

```text
[9] Settings
[4] Manage ignored tracks
```

Then sync the playlist again.

### A playlist is not running from cron

Check its Auto sync setting:

```text
[9] Settings
[5] Manage auto-sync
```

Auto sync OFF playlists are intentionally skipped by `python sync.py --sync-all`.

They can still be synchronized manually from the interactive menu.

## Security

`config.json` contains your Plex connection information, including your Plex token.

Keep all local state files and schema-migration backups private and out of source control.

The recommended `.gitignore` excludes them.

## License

Playlist Bridge is licensed under the **GNU General Public License v2.0 only** (`GPL-2.0-only`).

See [`LICENSE`](LICENSE) for the full license text.
