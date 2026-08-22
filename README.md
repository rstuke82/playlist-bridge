# Playlist Bridge

**Version 1.2**

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

## What's New in 1.2

Version 1.2 expands matching safety, synchronization visibility, state management, and interactive workflow.

### Sync change tracking

Playlist Bridge now remembers the previous source playlist contents and can distinguish:

```text
ADDED
REMOVED
```

from matching-state changes:

```text
NEW
LOST
```

These labels describe different things:

- `ADDED` — the track is new in the source playlist since the previous snapshot.
- `REMOVED` — the track was present in the previous source snapshot but is no longer present.
- `NEW` — the source track did not previously have a saved mapping and was matched during this sync.
- `LOST` — a previously saved Plex target is no longer safely usable.

At the end of a normal sync, Playlist Bridge prints:

```text
=== SYNC SUMMARY ===
Source tracks:
Matched:
New matches:
Lost matches:
Source ADDED:
Source REMOVED:
Unresolved:
```

Existing installations establish a source-content baseline on their first tracked 1.2 sync rather than incorrectly reporting every existing source track as newly added.

### Safer match provenance

Saved mappings can now be identified as:

```text
automatic
manual
legacy
```

`legacy` means the mapping existed before provenance tracking was introduced. Playlist Bridge does not guess whether an older mapping was automatic or manual.

Manual and legacy mappings are protected from **Clear automatic matches**.

If a saved manual or legacy Plex ID becomes stale, Playlist Bridge does not silently replace it with a new automatic guess. It is surfaced for review instead.

### Improved recording/version matching

Explicit source recording intent is now handled more carefully.

Examples of distinct recording intent include:

```text
Song (Demo)
Song (Acoustic)
Song (iTunes Session)
Song (Apple Music Session)
Song (Spotify Sessions)
Song (Named Remix)
Song (Somebody Mix)
Song (Live ...)
```

A source that explicitly requests one of those versions will not automatically collapse to a plain studio recording that lacks the requested intent.

Generic album-era provenance is treated differently. For example:

```text
Time is Precious (Evolver Sessions)
```

can correctly match:

```text
Time Is Precious (Evolver sessions – 2003)
```

without treating `Evolver Sessions` as the same kind of distinct performance marker as `iTunes Session`.

Featured-artist credits remain flexible metadata. A source such as:

```text
Good Vibes (feat. Lutan Fyah) - Rebelution
```

can match a destination such as:

```text
Good Vibes - Rebelution feat. Lutan Fyah
```

without incorrectly preferring an acoustic copy simply because the album name is similar.

### Better playlist selection and navigation

Option 3 supports multiple selections:

```text
1,3,5
```

and ranges:

```text
1-3
```

Playlists shown with a **Last sync** timestamp are ordered with:

```text
Never
oldest
...
newest
```

Option 5 is similarly ordered by **Last match attempt**, with `Never` first.

Where `[b] Back` is shown, both `b` and an empty Enter return exactly one menu level.

### State-file schema versioning

Playlist Bridge now versions its persistent JSON structure independently from the application version.

Current state files use schema 1:

```json
{
  "_schema_version": 1,
  "data": {
    "...": "..."
  }
}
```

Existing unversioned Playlist Bridge state is treated as legacy schema 0 and loads normally.

On the next normal save, legacy files are migrated to schema 1. Before an existing file is rewritten, Playlist Bridge makes a one-time byte-for-byte backup such as:

```text
mapping.json.pre-schema-1.bak
```

A dry run does not perform the migration or write any state.

If an older Playlist Bridge build encounters a newer unsupported schema, it stops instead of risking corruption of the newer state.

## Requirements

- Python 3
- A Plex Media Server containing your music library
- A Plex authentication token
- Public Spotify and/or Apple Music playlist URLs

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
Playlist Bridge v1.2 - Spotify/Apple Music to Plex
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
- `f` — save triage progress and sync the playlist now
- `x` — save progress and exit

A match explicitly selected during triage is stored as a **manual** mapping.

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
- reject wide banner/social-preview images
- reject very small images
- try alternate square Apple artwork renditions

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

## Automated Sync

Sync every registered playlist non-interactively:

```bash
python sync.py --sync-all
```

This uses saved mappings, refreshes source contents, updates Plex playlists, records unresolved tracks, updates change-tracking state, and updates last-sync timestamps.

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
- does not write any JSON state
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
```

Purpose:

- `config.json` — Plex configuration and registered playlists
- `mapping.json` — source-track to Plex-track mappings
- `missing_tracks.json` — unresolved source tracks
- `match_metadata.json` — automatic/manual provenance for mappings
- `source_snapshots.json` — previous source playlist contents for `ADDED` / `REMOVED` comparison

### JSON schema

Schema 1 uses:

```json
{
  "_schema_version": 1,
  "data": {
    "...": "..."
  }
}
```

Older unwrapped Playlist Bridge JSON loads as schema 0.

The first normal save under 1.2 migrates those existing files and creates one-time backups such as:

```text
config.json.pre-schema-1.bak
mapping.json.pre-schema-1.bak
missing_tracks.json.pre-schema-1.bak
```

New state files that did not previously exist do not need a migration backup.

If the file declares a schema newer than this Playlist Bridge build understands, the application stops rather than overwriting it.

## Upgrading from 1.1

You can replace the old `sync.py` with 1.2 and keep your existing:

```text
config.json
mapping.json
missing_tracks.json
```

No reset is required.

Existing saved mappings load normally and are classified as `legacy` until you explicitly confirm/change them or new automatic mappings are created.

If you want to verify the upgrade without writing anything first:

```bash
python sync.py --sync-all --dry-run
```

Then run a normal sync when ready. The first normal state save performs the schema-1 migration and creates the one-time backups.

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

Playlist Bridge validates actual image dimensions and rejects unsuitable wide or low-resolution artwork.

### `--sync-all` stops because Plex is not configured

Run:

```bash
python sync.py
```

configure Plex interactively, then run `--sync-all` again.

## Security

`config.json` contains your Plex connection information, including your Plex token.

Keep all local state files and schema-migration backups private and out of source control.

The recommended `.gitignore` excludes them.

## License

Playlist Bridge is licensed under the **GNU General Public License v2.0 only** (`GPL-2.0-only`).

See [`LICENSE`](LICENSE) for the full license text.
