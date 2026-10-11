# Historical release notes

These describe older builds, not current validation or behavior.

## Build 20261007.2: personalized Discover

Discover now shows personalized album recommendations based on similar artists from recent listening, followed by trending albums and listening-history gaps. Top albums have been removed. Run Refresh Last.fm Discovery once after upgrading to prepare the new personalized feed. All home feeds use saved refresh data.

## Build 20261004.10: health and request hotfix

The update checker understands build-number releases and safely handles saved release labels from earlier beta images. Request enrichment accepts both text and object-shaped Lidarr artists.

## Build 20261004.9: resilient source artwork requests

Spotify public playlist GETs retry incomplete chunked responses before failing. Apple Music generic artwork placeholders are ignored, and expected 404 responses from optional Apple artwork variants no longer appear as application errors.

## Build 20261004.8: chronological Requests

Requests now use one artwork-rich chronological feed, newest first, with persistent status and requester filters plus configurable sorting. Selecting a request opens the linked Library album and returns to the same place in the feed. Repaired Lidarr identities are used for Library links, and download progress remains visible without expanding administrative controls.

## Previous beta: reviewed links and clearer live state

Beta 16 lets Last.fm listening-history gaps be linked directly to an existing Plex or Lidarr album, including compilations whose track artist differs from the album artist. Match review now shows source and candidate durations, keeps automatic suggestions distinct from choices made by a person, immediately displays queued matches, and removes edition labels such as remaster and deluxe edition from discovery queries without changing saved titles.

Requests link back to Library albums and show active-download counts in navigation, with an attention color when action is required. Activity shows the number of jobs actually running. Artist pages retain a live-album preference, same-title releases remain distinct by MusicBrainz ID, manually selected album artwork can optionally be sent to Plex, and artist profile menus expose account and administration destinations.

Custom MusicBrainz servers are tested for direct lookup, relationship expansion, browse, and indexed-search support. Harmonia uses only the capabilities that pass and continues to use public MusicBrainz for unavailable operations.

## 3.0 Beta 15: request workflow and maintenance

Beta 15 gives Requests a persistent workflow for needs action, work in progress, completed, and cancelled or failed albums. Completed history remains visible if an album is later removed from Lidarr, while each request provides the appropriate Lidarr link or re-add action. Settings → Database adds health checks, safe cache tools, history retention, backup-first compaction, derived-data rebuilding, and a separately confirmed factory reset.

Large displays now show wider library grids, artist heroes, popular tracks, settings, and request history. Automatic artist backgrounds prefer Fanart.tv banners before conventional backgrounds and Plex, while saved artwork selections remain unchanged.

## 3.0 Beta 14: faster Library navigation

Beta 14 makes the Lidarr-backed Library substantially faster to open and navigate. The artist directory uses a lightweight response, while artist details, issues, and albums load only when opened. A bounded, revision-aware prepared view reuses MusicBrainz identities, Plex associations, artwork choices, and file evidence until relevant saved data changes. The server also replaces repeated per-item database reads and full-list scans with shared in-memory indexes, and records slow Library preparation in the diagnostic timeline.

Automatic Lidarr import finalization now waits for a quiet period and drains a durable batch of at most ten albums at a time. Existing backlogs are collapsed during startup, availability reconciliation runs once per batch, and a failed album waits for an explicit retry instead of repeatedly rejoining the queue. Activity safely renders older incomplete job records.

Beta 13's owner-first Plex setup, official MusicBrainz release selection, structured diagnostics, webhook batching, and Stop Pending Jobs remain included. Lidarr remains the library and download authority and is not used as a display-metadata source.

## 3.0 Beta 11: API access, iOS sharing, and Lidarr events

Beta 11 gives each account one non-expiring personal API key under Account → API Access. An iOS Shortcut can share a public Apple Music or Spotify playlist URL directly to Harmonia. Administrators can configure a Lidarr Webhook Connection so imports run the existing targeted album finalization and broader catalog events refresh the Lidarr inventory. API-triggered jobs identify their source in Activity.

## 3.0 Beta 10: playlist editing and library upgrade review

Beta 10 adds a full playlist editor to Playlist Details. Tracks can be added from the Lidarr library, pasted into an existing playlist, removed, edited, and reordered. Duplicate occurrences are retained. These changes are stored as a durable Harmonia overlay, so provider refreshes do not erase manually added tracks that Apple Music omits from its public source.

Library Management now reports clear Lidarr naming mismatches and identifies MP3, non-256 kbps AAC, and non-FLAC/ALAC files for iTunes Match upgrade review. Moving a candidate out for replacement keeps it visible as **Missing — awaiting upgraded file** until its stable Lidarr/MusicBrainz identity returns.

Source safety checks reject an unexpectedly empty or shortened provider response before Plex can be changed. Confirmed empty playlists remain valid. Contributor-aware matching handles multi-artist and featured credits more reliably, and Lidarr search selections retain their MusicBrainz recording identity.

## 3.0 foundations: accounts, discovery and library review

Sign in with Plex. The **configured Plex server owner must sign in first**; existing 2.x playlists and history remain in that owner's account. Individual users must have access to the selected music library. Managed Plex Home users are not supported. For a new installation, open the web sign-in page and have the Plex server owner sign in. Harmonia discovers the owned server and first accessible music library before creating the administrator account. Serve remote access through HTTPS.

Each other account gets a separate SQLite database under the existing data volume's `users/` directory. Its playlists, matches, blocklist and jobs stay separate, and sync uses that user's Plex access token. The administrator controls scheduled sync and health tasks across accounts, access, request permissions, and shared playlist sources. Users can preview shared sources and add their own copy. Already-added sources are hidden per account. Publishing and unpublishing remain administrator-only. Disabled accounts do not run new scheduled work.

**Discover** replaces the default Dashboard navigation. Add a Last.fm API key in Settings to show albums from trending artists, search albums, or review a Last.fm user's top albums. Responses are cached server-wide for six hours. Availability uses saved Lidarr track identities linked to Plex files; ambiguous links require review. Reviewing Last.fm albums does not automatically request downloads.

Ordinary users request albums using server defaults. Lidarr and MusicBrainz configuration, credentials and caches remain administrator-controlled; download visibility and management can be granted independently in Settings → Users. Requests may require administrator approval. Users can review their own requests. **Library** is browsable by all signed-in users; administrative scans, file evidence, link corrections, metadata controls, and mutations remain permission-gated. It compares Plex and Lidarr inventories: linked, Lidarr only, needs review, or **Needs Attention / Missing from Lidarr**. Missing-from-Lidarr flags wait for both successful scans. Track counts and scan times remain separate from identity links. Plex inventories for shared users respect their own token's library visibility.

Backups now include personal databases. A restore invalidates browser sessions and interrupts unfinished restored jobs. Back up the entire existing data volume before upgrading or rolling back. CLI use remains the server owner's local workflow; CLI access is not an ordinary-user login.

This beta uses a production frontend build, Python syntax checks and six targeted checks with isolated data. Full regression, browser and container smoke tests were skipped. Live Plex sign-in, Last.fm discovery with your API key, and real-user Plex writes still need validation on your server. Duplicate-file inspection and audio conversion are not included.

