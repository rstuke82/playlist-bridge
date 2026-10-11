# Harmonia 3.0 Beta 7

Source release `v3.0.0-beta7`, based on validated build 20261011.9. Includes the web-only runtime migration, beta fixes, security hardening, HARMONIA_* environment names, request pagination, corrected request progress and the redesigned homepage request cards. See BUILD-NOTES.md and SECURITY-DEPLOYMENT.md for validation and upgrade requirements.

# Build 20261011.9

- Homepage recent requests use horizontal cards with right-side artwork, requester names/avatars and readable status pills. No year is displayed.
- Pending searches are no longer errors; queued and awaiting-approval requests remain in progress. Actual search/download/import failures still require action.
- Retain album artwork from preview through request creation and empty inventory updates, with release-group cover fallback for older requests.
- Refresh saved request projections after upgrade. Rename Review / Request to Request Album.

# Build 20261011.9

- Rename all environment variables to HARMONIA_* without compatibility aliases. Update Docker defaults, health checks, Compose settings, tests and documentation. Existing database filenames and data layout are unchanged.

# Build 20261011.9 — prepared

- Requests pagination footer with range counts, page-size choices and navigation.
- R01–R06 application/container/proxy/redirect/queue/dependency controls; remaining zlib advisory and deployment checks are documented in SECURITY-HARDENING-CHANGES.md.

# Build 20261011.6

- A04: queue member album searches in the bounded lookup worker, with private jobs, immediate cancellation, shared release filtering and recording pagination.
- A05: try up to four valid advertised Plex connections during first-run setup, preserving TLS verification and existing server/library selection.
- A06: stream image downloads with a 20 MB limit, a 30-second caller deadline and four-download admission limit.

# Build 20261011.5

- A01: protect fresh installation claiming with a private one-time setup key bound to the Plex login attempt; commit ownership with a recoverable configuration journal and reject competing claims/key reuse.
- A02: coalesce concurrent and rapid PIN polling, apply expiring per-IP/global limits and cap active checks; retry busy responses automatically in the login UI.
- A03: queue first-owner Plex inventory initialization, preserve it through interrupted setup recovery, and show progress/failure guidance in the application.
- Existing configured installations retain normal login and receive no setup key.

## Build 20261011.1

- Extracted the shared runtime into domain modules and removed legacy.py and the unsupported interactive CLI.
- Removed terminal setup prompts; Plex configuration failures now direct users to web Settings.
- Updated Docker packaging, documentation and canonical test imports; added ten runtime regression guards.

## Build 20261010.12 — UI consistency audit

- Fix UX01–UX13: request sorting/status badges, full Library filter reset, artist-link operation locks, corrected navigation/instructions, request capability gates, accessible field names, loading/error states, Lookup worker filtering and playlist editor recovery.
- Standardize explicit sort orders and filter resets; guard saving forms and modal dismissal; align the tablet header breakpoint through 850px.
- Validation and exact changed files: UI-UX-FIXES.md. Registry publication status is recorded separately.

## Build 20261010.10

- Replace visible Bridge/Playlist Bridge branding with Harmonia in the interface, service messages, notification application label, CLI and current README. Keep compatibility identifiers and recognize legacy Plex summary markers in both sync and description refresh.
- Remove Requests bulk and per-album Lidarr link-check controls and duplicate search field. Remove the old local search filter so persisted queries cannot hide rows.
- Align sort dropdown and direction button; give direction button a 44px target and clear accessible action label.

Changed files are listed in BRANDING-FIX.md; Requests also changes web/src/LidarrRequests.tsx and web/src/discover-layout.css. Updated tests/test_30.py branding expectation and tests/test_22_beta3.py legacy-summary replacement case. Backend validation: 615 tests passed for branding; request section checks passed after Requests edits. TypeScript/Vite build passed; Docker repeats it for both architectures. Existing bundle-size warning remains. Live integration and device behavior remain unverified.

## Build 20261010.9

- Correct mobile header spacing across Discover shelves, recommendations, trending and listening history. Replace vertical flex basis with content-sized grid headings.
- Ignore uses the same text size as other history actions.
- Move ignored listening-history albums to Blocklist with Restore, busy state and error feedback. Discover no longer fetches or displays the ignored list. Existing account-scoped endpoints and ignore behavior retained.

Changed web/src/discover-layout.css, web/src/Discover.tsx and web/src/DiscoverPreferences.tsx, plus release version metadata and documentation. No backend logic changed. TypeScript/Vite working-source build passed; Docker repeats validation on amd64 and arm64. Existing bundle-size warning remains. On-device layout and interactive Restore have not been verified.

## Build 20261010.8

F28: MusicBrainz discovery strips supported Advance, Advance Copy, Advance Promo and Advance Version qualifiers from parenthesized/bracketed or separated suffixes. Original source metadata is untouched. Legitimate names such as Advance and Follow or Advanced Studies are preserved. Two regression tests cover six qualifier forms and four legitimate names.

Discover listening-history button now reads Ignore.

Both amd64/arm64 TypeScript/Vite image builds passed; npm reported zero vulnerabilities. Existing bundle-size warning remains. No live MusicBrainz/device verification. Docker build completed in local builder cache; registry tags have not been updated.

## Build 20261010.7

- Keep Discover cards and history actions within mobile screen width.
- Compact album search spacing, text and artwork; keep 44px touch targets.
- Remove Search Existing Lidarr Library from album search.

## Build 20261010.6

- F07: validate and reconstruct server/account saved-view scope for delegated admins.
- F24: upgrade source-map-js to 1.2.2; zero dependency vulnerabilities reported.
- Group Requests into Needs Action, In Progress, Partially Available, Completed and Cancelled / Failed sections with counts. Preserve filters and detail access.

## Build 20261010.5

- Persist targeted Plex album confirmation on requests; preserve complete/partial availability when overall inventory is stale. Retain event-generation/failure/removal safeguards and newer definitive inventory precedence.
- Label prior fulfilled timestamps as Lidarr imports rather than Plex completion.
- Rebalance mobile navigation into four equal columns with a smaller bar/selection; preserve position and accessible material fallbacks.

## Build 20261010.4

- Parse explicit featured artist credits for unknown-album MusicBrainz discovery: Pitbull, John Ryan — Fireball (feat. John Ryan) searches Pitbull / Fireball. Preserve original metadata and comma band names without explicit feature credits.
- Use the same parsed identity when validating recording and album results; invalidate prior search caches.
- Remove the five-recording rejection; browse all qualifying recordings within the fetched 25-recording search page.

## Build 20261010.3

- Artist-and-song MusicBrainz searches with no album browse containing releases and return artist-credited albums; exclude compilations/singles and respect studio preference. Preserve actual release artist credits; invalidate old recording search caches.
- Use close duration as supporting evidence for structured/explicit featured lead credits, retaining title/artist/version checks.
- Remove the large Automatic match panel; show suggestions in the normal candidate list with a small Suggested label and preserved provenance.

## Build 20261010.2

- Resolve otherwise identical catalog recordings using source duration: within 5 seconds, at least 10 seconds closer than competitors; retain ambiguity/version safeguards.
- F08: retain selected playlist health scope in validation and execution; permit members with playlist permission to check their own selected playlists. Consolidated health remains admin-only. Change per-playlist job submission to POST with normal CSRF protection.
- F09: Track Details and match previews read current saved source plus overlays. An empty current source remains empty. Historical health is a labeled fallback when no current snapshot exists.

## Build 20261010.1 — updated F23

- Stop periodic rebuilding of every historical saved page; preserve explicit startup landing-page preparation.
- Prioritize first-load pages and coalesce queued refreshes to the latest revision.
- Remove request polling bookkeeping from Discover/listening-history dependencies; retain Requests invalidation.
- Retire obsolete queued page jobs on upgrade, preserving saved data and active jobs.
- Add 10 regression tests; all 553 backend tests and frontend validation pass.

## Build 20261010.1

- F14: authoritative session refresh handles null users and refreshes CSRF; session changes clear account storage and cancel old API requests before a clean page reload. Ignore obsolete refresh responses and late body decoding. API 401 responses clear the session centrally.
- F22: replace worker grouping in Jobs history with Running, Queued and Completed sections. Preserve outcome labels, owner/worker filtering, details and Stop Pending Jobs. Active jobs remain visible independently of completed-history pagination.

## Build 20261009.17

- Remove direct media-file tag writes from Harmonia release selection; retain Lidarr release selection and refresh.
- Preserve album-added dates and album artwork during targeted Plex import lookups.
- Refresh Discover's saved Recently Added shelf while visible and when returning to the page.
- Preserve failure status against delayed/duplicate Grabs; current queue evidence confirms retries and retires previous download identities.
- Protect missing-catalog, identity-repair, search-command and poll-error writes against newer webhooks.

# Build 20261008.9

- Stop repeated mirror searches while keeping public fallback.
- Preserve automatic retries only for searches routed directly to public MusicBrainz.
- Clarify search progress and retry preferences, with regression coverage.

## Build 20261008.8

- Remember listening-history identity when requesting selected Lidarr editions.
- Hide confirmed imported library albums automatically, including before Plex indexes them.
- Align library candidate scores with automatic history evidence and retain all artist credits.
- Add request, approval, member isolation and automatic removal coverage.

## Build 20261008.7

- Added per-task startup policies and configurable landing-page preparation.
- Reuse active jobs and retain saved pages during startup preparation.
- Default to missing-only inventory scans and overdue Last.fm refreshes; keep other work opt-in.
- Added startup freshness, identity, deduplication, member context and settings regression coverage.

## Build 20261008.6

- Fixed restricted-member playlist detail controls and matching queue visibility.
- Fixed album return breadcrumb labels using the same history origin as the Back action.
- Added focused permission-rendering and breadcrumb regression coverage.

## Build 20261008.5

- Restore the original Playlist Bridge installation declaration structure with Harmonia artwork and matching sRGB export metadata.
- Add paired original/new icon pages for controlled on-device comparison.

## Build 20261008.4

- Add Apple touch-icon size variants and precomposed fallback.
- Add isolated Safari icon-check page; actual home-screen fix remains unverified.

## Build 20261008.3

- Refresh browser and mobile PWA icons with simplified Harmonia branding.
- Add versioned icon and manifest references, opaque Apple exports and a dedicated maskable icon.

## Build 20261008.2

- Ignore individual listening-history albums per account, with a saved restore list.
- Preserve exclusions across Last.fm refreshes and filter before the suggestion limit.
- 410 backend checks, frontend behavior checks and production build pass.

## Build 20261008.1

- Add member Library Issues permission and enforce it before prepared reads.
- Scope all member requests and download actions to their own albums; preserve requester attribution and owned progress links.
- Support Plex-only Library browsing with requests unavailable when Lidarr is disabled.
- Align shared Library editing and member request controls with server permissions.
- Update final regression contracts; 407 backend checks, frontend behavior checks and production build pass.

# Build 20261007.19

Scope Lidarr catalog webhooks to affected albums/artists, batch durable targets, preserve arrivals during execution, and remove unconditional follow-up scans. Imported album track/file reads now use albumId.

# Build 20261007.18

Hide routine request download-status polling from Activity, active counts and filtered history while preserving diagnostic access.

# Build 20261007.17

Guard stale Library and Discover responses, isolate feed updates, invalidate caches after saved changes, and scope album return navigation to browser-history entries.

# Build 20261007.16

Use saved Lidarr rename previews for naming issues, show current and expected paths, clear legacy guessed warnings, and report unavailable checks.

# Build 20261007.15

Canonical album identity, compilation evidence, actionable Plex album Issues, managed secondary types, portrait title alignment, and internal page preparation visibility. See BUILD-NOTES.md for validation and limits.

# Build 20261007.14

Album navigation now loads the correct return destination. Album details share Library availability and artwork rules. Album reads use small durable projections, and Plex image lookups reuse revision-scoped indexes instead of rebuilding library associations.

# Build 20261007.13

Requests now waits for prepared data without crashing navigation and keeps the previous list after a failed refresh. Page preparation runs in a reserved worker alongside long background jobs, while exclusive database maintenance remains serialized.

## Build 20261005.8 — 2026-10-05

- Changed Discover feeds to read saved Last.fm refresh data without making external Last.fm requests during page load.
- Expanded the Last.fm refresh job to prepare top albums, recent history, and trending recommendations.
- Made recommendations user-triggered so they cannot delay or time out the listening-history feed.
- Added clear empty states when saved data is not ready for the current Last.fm settings.

## Build 20261005.7 — 2026-10-05

- Shows Lidarr and Plex cover art in Last.fm library-link candidates, with a placeholder only when the image is unavailable.
- Prevents Requests cards and filters from overflowing at tablet and small-desktop widths.
- Reflows playlist problem tracks so long identity and Lidarr status text no longer collapse into narrow word columns.
- Removes the duplicate inline album-request submit button and uses consistent dialog actions and labels.
- Adds an accessible label to the library-link filter.

## Build 20261005.6 — 2026-10-05

- Collapses matching Lidarr and Plex copies into one Last.fm library-link result.
- Saves the Lidarr album as the durable identity while retaining the related Plex album as availability evidence.
- Keeps Plex-only results when no unique Lidarr counterpart can be established and leaves ambiguous Lidarr identities separate for review.

## Build 20261005.5 — 2026-10-05

- Fixes Last.fm history rows that incorrectly use the album title as the performer, such as Hybrid Theory — Hybrid Theory.
- Automatically recognizes existing Plex and Lidarr albums using canonical album titles, any credited performer, group-name aliases, and track evidence.
- Ignores edition labels such as EP, Single, Deluxe and Remaster when comparing listening history with the library.
- Keeps ambiguous and unrelated same-title albums available for manual review instead of auto-linking them.
- Narrows manual album-link candidate comparison before scoring tracks, avoiding multi-second scans across every library album.

## Build 20261005.4 — 2026-10-05

- Keeps the dominant album performer for Last.fm history albums with featured guests; only balanced multi-performer compilations use Various Artists.

## Build 20261005.3 — 2026-10-05

- Adds Last.fm missing-album settings for history range, minimum plays, suggestion count, and ordering.
- Pages through the selected history window in 200-scrobble requests with a 5,000-scrobble safety cap.

## Build 20261005.2 — 2026-10-05

- Fixes Last.fm history-gap filtering when compilation and collaboration credits are returned as artist-name strings.

## Build 20261005.1 — 2026-10-05

- Adds manual album-level Plex linking and uses the saved album target for Plex artwork updates.
- Fixes Last.fm listening-history parsing when optional fields arrive as strings.
- Fixes portrait navigation badges, solid on-screen menus, playlist and missing-track text layout, and labeled request filters.
- Closes playlist action menus after selecting a schedule mode.

# Playlist Bridge changelog

## Build 20261004.11 — 2026-10-04

- Enabled concurrent SQLite reads while workers persist progress, keeping Tasks and History responsive.
- Prevented health, library, and metadata jobs from running at the same time and reduced health-check fan-out.
- Added a scheduled and manual Last.fm Discovery refresh for recent plays and top albums.
- Removed terminal EP and Single release labels from MusicBrainz discovery queries without changing saved titles.
- Summarized repeated Lidarr fewer-track import rejections and retained full details in an expandable view.

## Build 20261004.10 — 2026-10-04

- Fixed `/api/health` failing after switching from semantic beta versions to build numbers.
- Made saved update metadata from earlier beta images safe to compare with build-number releases.
- Fixed `/api/lidarr/requests` failing when an inventory row stores the artist as text.

## Build 20261004.9 — 2026-10-04

- Retried incomplete Spotify chunked GET responses before failing a job.
- Rejected generic Apple artwork templates that contain no image identity.
- Kept expected 404s from optional Apple artwork variants out of the error log.

## Build 20261004.8 — 2026-10-04

- Replaced request status sections with one newest-first, artwork-rich feed.
- Added persistent request status, requester, text, sort, and direction controls.
- Linked request artwork and titles to the current Library album identity and restored Requests state on return.
- Kept live download progress visible while moving maintenance actions into a compact details menu.
- Switched user-facing release labels and package naming from beta numbers to build numbers.

## 3.0.0-beta.16 — 2026-10-04

- Made Lidarr import webhooks log and refresh the mapped Plex album folder, report missing path mappings, and briefly recheck that album while Plex completes asynchronous indexing.
- Made known-album discovery search release groups by artist and album even when Song is populated, and added public fallback when an indexed mirror returns an empty search result.
- Added a result badge identifying public MusicBrainz, configured-mirror, and public-fallback searches, including preserved routing evidence for cached results.
- Fixed Requests claiming an available album was absent when Lidarr retained it under a different selected release-group identity.
- Fixed Apply Artwork to Plex failing with an undefined repository helper.
- Added persistent Last.fm listening-history links to existing Plex or Lidarr albums and collapsed compilation plays into one album-level finding.
- Added candidate/source duration evidence to match review and matching scores, immediate queued-match state, safer automatic fallback, and clearer automatic-versus-user-selected wording.
- Removed common remaster, deluxe, expanded, anniversary, and edit qualifiers from album and song discovery queries while preserving stored titles and capitalization.
- Added album artwork to MusicBrainz search results and removed duplicate selected-result text and outbound links from Add Album review.
- Added Requests badges for active downloads with attention coloring, Activity badges for running jobs, and Library links from request rows.
- Added optional Plex synchronization for manually selected album artwork, a profile destination menu, a persistent live-album filter, and MusicBrainz-ID-safe same-title blocklists.
- Added automatic capability testing for MusicBrainz mirrors, including indexed search when the configured server actually supports it.

## 3.0.0-beta.15 — 2026-10-04

- Preserved each account's non-expiring API key when Plex reauthenticates, preventing Lidarr webhook credentials from breaking after an update or sign-in.
- Added recent Last.fm listening-history gaps to Discover, with inventory-aware missing status and the normal album review/request flow.
- Made MusicBrainz the default Add Album search, kept Lidarr as a secondary existing-library search, and removed the duplicate footer Add action.
- Sorted requests newest first within each workflow stage, added stale Lidarr-link inspection and repair, and prevented newly added/download-queued albums from being marked absent during Lidarr inventory lag.
- Added compact artist/album back links, persistent mobile profile access, grouped Library issues, immediate manual-match feedback, and cleaner artwork controls without image overlays.
- Removed the redundant global activity banner while retaining compact contextual status and Activity links beside the action that started work.
- Redesigned Requests around Needs Action, In Progress, Completed, and Cancelled / Failed stages with progress, requester history, download details, and compact workflow sections.
- Retained fulfilled requests when an album is later removed from Lidarr, while showing the historical fulfillment and current Lidarr state separately.
- Added an Open in Lidarr action to linked requests and an in-place Re-add to Lidarr flow for retained requests whose album is no longer present.
- Added a Database settings page with integrity checks, query optimization, WAL checkpointing, backup-first compaction, configurable history cleanup, safe per-cache clearing, and derived-data rebuilding.
- Added a weekly Optimize Database task, enabled by default, and kept destructive factory reset behind an exact typed confirmation and a safety backup.
- Expanded desktop layouts to use full-width and ultrawide displays, including denser album grids, artist directories, and popular-track columns while preserving readable metadata text widths.
- Changed automatic artist background selection to prefer Fanart.tv banners, followed by Fanart.tv backgrounds and Plex artwork. Saved manual artwork choices remain unchanged.

## 3.0.0-beta.14 — 2026-10-03

- Replaced the initial full Library payload with a lightweight artist directory and targeted artist, issue, and album views.
- Added bounded, per-account Library view caching keyed to relevant saved-data revisions so repeated navigation does not rebuild unchanged inventory and metadata.
- Replaced repeated per-artist Plex scans, per-album blocklist reads, metadata-priority reads, and artwork lookups with shared indexes prepared once per revision.
- Reused prepared Plex and Lidarr indexes on album pages, avoiding another full Library and track-association pass for every album opened.
- Added server-side Library search, sorting, pagination, explicit refresh, and diagnostic timing for slow Library preparation.
- Kept the last Library directory visible during background refresh and invalidated targeted browser caches after edits.
- Retained Beta 13's Lidarr webhook batching and administrative Stop Pending Jobs control.
- Added manual Plex artist search and reviewed linking from the artist service icon, including fuzzy name candidates, album and track counts, Plex destinations, and artwork lookup through the selected artist.
- Coalesced automatic imported-album finalization into durable quiet-period batches of at most ten albums, with one availability reconciliation per batch.
- Collapsed existing queued or interrupted per-album finalizers during startup and stopped failed finalizers from automatically looping.
- Hardened Activity and job-history rendering against incomplete legacy payloads that could otherwise blank the page.
- Fixed Scan Local Files failing after a full library walk when Lidarr reports an alphanumeric track position such as `B4`.

## 3.0.0-beta.13 — 2026-10-03

- Added owner-first Plex discovery and administrator initialization for a fresh installation, with a redesigned setup and sign-in page.
- Opened read-only Lidarr-backed Library browsing to signed-in users while retaining administrative controls around scans, files, metadata, and mutations.
- Added official MusicBrainz release selection for Lidarr albums, mapped-file MBID tagging, and an automatic Lidarr refresh after the change.
- Replaced fragmented application logging with a structured diagnostic timeline correlated by worker, job, request, user, service, and entity, with search and time filters and 100,000-event retention.
- Removed Lidarr from display metadata source choices. Lidarr remains the source of truth for library state, monitoring, downloads, paths, and release selection.
- Standardized the mobile five-tab navigation and Plex-profile entry point, and removed the redundant mobile header search field.
- Migrated SQLite storage to schema 5 and added restore-time migration for Beta 12 backups.
- Fixed DEBUG events appearing in Logs while debug logging was disabled, and fixed compressed diagnostic header buttons.
- Coalesced Lidarr rename, retag, artist, and album webhook bursts into one quiet-period inventory refresh, including automatic cleanup of an existing queued catalog-event backlog while preserving targeted download finalization.
- Added a Stop Pending Jobs action that clears queued work across all account queues for administrators without interrupting currently running jobs.


## 3.0.0-beta.12 — 2026-10-02

- Added direct Fanart.tv artist and album artwork using MusicBrainz IDs, server-side credential storage, caching, source ordering, and connection testing.
- Removed Lidarr artwork proxying and Lidarr artwork candidates; Lidarr remains the library authority.
- Reordered desktop navigation around Discover, Library, Playlists, Requests, and Search, with Missing and Blocklist grouped afterward.
- Reworked the mobile tab bar around the five primary destinations and moved utility destinations to the profile page.

## 3.0.0-beta.11 — 2026-10-02

- Fixed authenticated retrieval of Lidarr's cached artist artwork, removed redundant Account navigation, and stopped normal Plex refresh propagation from appearing as Activity attention.
- Fixed Lidarr artist artwork choices disappearing when Lidarr returned an internal absolute media URL or a generic image content type. Failed artwork now remains visible as unavailable instead of silently vanishing.
- Reworked Users into a profile-based directory with grouped, explicitly saved permissions and clearer active, disabled, and pending states.
- Artist artwork choices now load Lidarr automatically through an authenticated Bridge image proxy, and artist action menus close after a choice.
- Separated higher-bitrate AAC files into iTunes Match review so they do not count as quality problems or artist attention findings.
- Lidarr download and upgrade webhooks now visibly run an album-scoped local-file scan before the targeted Plex refresh, including missing and unmapped-file reporting.

### Added

- Added one non-expiring, regenerable API key per user with current permission enforcement and one-time full-key display.
- Added a stable `v1` API for status, job lookup, playlist URL sharing, library scans, reconciliation, and recent integration events.
- Added an iOS Shortcut workflow that accepts shared public Apple Music or Spotify playlist URLs.
- Added an authenticated Lidarr webhook receiver with duplicate-delivery protection and visible trigger attribution in Activity.

### Changed

- Lidarr imports and upgrades use targeted album finalization; rename, retag, artist, and album catalog events refresh the Lidarr inventory.


## 3.0.0-beta.10 — 2026-10-01

### Added

- Added a playlist editor for adding, removing, editing, and reordering tracks while preserving duplicate occurrences. Lidarr-library search and pasted `Artist - Track - Album` lists can append tracks to an existing playlist.
- Added durable Bridge playlist overlays. Manually added and edited tracks survive provider refreshes, including Apple Music uploaded tracks omitted from public playlist data.
- Added read-only Library Management findings for files that clearly violate the enabled Lidarr naming format and for iTunes Match upgrade review. MP3, non-256 kbps AAC, and non-FLAC/ALAC files are flagged with their codec, bitrate, path, and Lidarr identity.
- Added a persistent **Missing — awaiting upgraded file** state when a previously identified upgrade candidate is temporarily removed for replacement.

### Changed

- Playlist sync, details, health checks, and auto-sync-off audits now use the same merged source-plus-Bridge playlist, while source audit history remains limited to actual provider changes.
- Lidarr-search additions retain MusicBrainz recording IDs so known tracks can link directly instead of repeating title-only matching.
- Expanded contributor parsing and matching for comma-separated, featured, ampersand, and multi-artist credits.
- Provider observations now protect existing playlists from unconfirmed empty or shortened responses. A playlist is cleared only when the provider explicitly confirms a complete empty result.

### Fixed

- Fixed **Ready to Sync** remaining visible after a successful sync because stale inventory-link evidence was treated as a new pending playlist change. Match edits being processed by an active sync are no longer presented as pending work.

## 3.0.0-beta.9 — 2026-10-01

### Added

- Added album-scoped post-import finalization for Lidarr, mapped local files, and Plex, plus a manual Refresh This Album request action.
- Added split MusicBrainz routing: public indexed search plus an optional mirror for direct MBID and browse metadata, with safe public fallback.
- Added scored album and track evidence to Discover's Lidarr linking review, album blocklisting, direct release-group additions to Lidarr, Spotify artist links, and Lidarr banner/fanart background choices.
- Added ordered fallback priorities for each metadata field.
- Added inline, clickable Library attention details for artists and albums, explicit artwork controls for missing images, and immediate artwork refresh after selection.
- Added grouped task schedules by worker, weekly schedules, per-task and all-task default restoration, and clearer local-scan configuration state.
- Added collapsible Not Completed and Completed request groups, with Lidarr download progress and controls kept in Requests.
- Added reviewed album-cover, artist-portrait, and artist-background selection using available Lidarr, Plex, Apple Music/iTunes, and Cover Art Archive images.
- Added Bridge-only artwork overrides with source labels, detected dimensions, enlarged previews, unavailable-image feedback, and Reset to Automatic.
- Added an optional Last.fm Popular Tracks section to artist pages.

### Fixed

- Replaced the mobile header's username, Account text and sign-out controls with the Plex profile image; Account now contains profile details and sign-out.
- Reduced Scan Local Files memory pressure by excluding the unrelated Plex inventory, loading individual saved snapshots, and decoding large Plex library responses only once.
- Added ISO timestamps with timezone offsets to container console output from the first server startup line.
- Linked manual task runs to their corresponding task row, hid blocklisted albums throughout Library browsing, and simplified artist service buttons to accessible icon-only controls.
- Prevented concurrent health checks from independently loading the full Plex library, which could report a timeout even while the Plex connection test passed.
- Changed the MusicBrainz connection test to hydrate a release-group returned by its live public search and return concise mirror errors instead of a server traceback.
- Made Activity prefer the newest running job over queued work.
- Stopped Plex inventory scans from silently launching Retry Missing Matches and retire any legacy retry still queued after upgrade.
- Fixed Metadata Sources order updates returning HTTP 422 and made the current Activity panel follow the newest running job.
- Classified partially downloaded Lidarr albums as Wanted, added progress to Scan Local Files, and accepted 300×300 playlist artwork when no larger candidate is available.
- Fixed artist portraits to render at a consistent 1:1 ratio.
- Prevented Plex-triggered missing-match retries from being presented as manual scheduled-task runs.
- Removed the duplicate Downloads view from Activity and required Plex confirmation before a request is marked Completed.
- Fixed an artwork chooser crash that could blank the page as the first candidate image loaded.
- Unified sidebar, About, API and CLI release labels with the canonical package version.
- Disabling a schedule now cancels scheduled work already queued across user accounts and requests safe cancellation of running scheduled work.
- Active task rows now distinguish manual runs from scheduled runs, and workers recheck disabled schedules immediately before execution.
- Enabled recurring scheduling for Refresh Album Metadata.

## 3.0.0-beta.8 — 2026-09-30

### Added

- Added reviewed artist links for MusicBrainz and Apple Music, plus per-field metadata source preferences.
- Added Last.fm or MusicBrainz artist descriptions and separate portrait/wide-hero artwork handling.
- Added canonical album identities using Lidarr's MusicBrainz release-group ID, with cached MusicBrainz catalog fallback when Lidarr omits an identity.
- Added missing MusicBrainz catalog albums to artist pages without changing Lidarr's role as the library authority.
- Added a disabled-by-default Refresh Album Metadata task on the Metadata worker.
- Added supplemental Apple Music album IDs, links, artwork, and dates when iTunes returns one unambiguous exact-title match.

### Changed

- Library navigation now returns to the artist directory; availability and release-type controls support multiple selections.
- Simplified artist actions and prevented square artwork from being stretched into hero backgrounds.
- Library filters now mean In Library (downloaded in Lidarr), Wanted (monitored without files), and Missing (not in Lidarr or unmonitored).
- Plex linkage is shown separately from Lidarr ownership and download state.
- Album pages identify their metadata source and expose available Lidarr, MusicBrainz, and Apple Music links.
- Added an Other release-type filter and limited MusicBrainz catalog additions to groups containing an Official release.

## 3.0.0-beta.7 — 2026-09-30

- Unify mobile/desktop navigation, restore missing mobile destinations through More, and refine glass styling with safe-area and accessibility support.
- Add optional scheduled read-only File Audit, on-demand SHA-256 duplicate verification, inaccessible-mount safeguards, and persistent issue review/intentional decisions.

- Restore Lidarr as the sole library authority; retire local catalog mode while preserving saved data.
- Add File Tools path mappings, selectable track paths, Plex links, and categorized reconciliation/duplicate findings.
- Group artist releases, simplify availability filters, preserve Library browsing state, and enforce disc/track order.
- Run metadata, inventory, download, and playlist work in independent bounded lanes; preserve account/destination and backup protections.
- Filter persistent job history by worker and show specific queue reasons.

## 3.0.0-beta.6 — 2026-09-28

- Open local Library to an artist list with MusicBrainz association review.
- Add optional cached iTunes metadata enrichment without changing file identities.
- Consolidate Library filters and fix shared menu stacking above glass panels.
- Hide invalid release years.

## 3.0.0-beta.5 — 2026-09-27

- Add opt-in read-only local music scans, MusicBrainz catalog reconciliation and local-to-Plex links.
- Add release-country and media-format preferences with official-release priority.
- Use local inventory for matching and availability when enabled; preserve existing mappings.
- Add optional read-only Docker music mount and scheduled local scanning.

## 3.0.0-beta.4 — 2026-09-26

- **Create from Text** accepts numbered/plain lists, artist-first or song-first lines, optional albums, and Song by Artist. Users review editable rows, fix ambiguous lines, remove headings, and name the playlist before Save & Sync. Text is treated as data, not instructions. Source order and duplicates remain intact.
- Custom sources persist in each account's SQLite store and can be edited from Playlist Details. Revision checks prevent overwriting newer edits. Registration survives zero matches so Missing, review and request workflows can be used before a Plex copy exists. Sync creates the Plex copy when playable tracks become available. Existing ignores and blocked artist names apply to text playlists. Custom Playlist is labeled consistently in lists and Missing filters.
- New automatic matching follows source metadata → Lidarr track identity → imported-file/Plex link. Existing recording/version thresholds and live safeguards are reused. An identified but undownloaded or unlinked track stays missing. Ambiguous identities require review.
- Lidarr scans collect tracks and files per artist, then replace the snapshot only after successful completion. Plex scans retain file paths and GUIDs. Links prefer exact file paths, with unique exact artist/album/title metadata as a fallback. Only imported Lidarr files qualify for automatic playback links. Matching reuses the loaded catalog and persists validated source identities and links in SQLite.
- **Music Library** browses Lidarr artists, albums with artwork, and tracks, including selected-release information, search, status filters, reverse sorting, and service links. Available, Partially Available, Downloading, Awaiting Download, Awaiting Plex, and Scan Pending are distinct.
- **Needs Attention** shows Plex tracks not linked to Lidarr, plus imported Lidarr albums awaiting Plex. A missing association is explicitly distinguished from proof that an album is absent from Lidarr.
- Administrators can review and correct track-to-Plex associations. Associations are server/library scoped and shared across accounts, but are reused only when the Plex item is visible and its identity remains unchanged for the current account. Existing playlist manual matches are not overwritten.
- Discover checks playback availability through these track links when the new inventory exists. Playlist Details displays the saved Lidarr identification state.


## 3.0.0-beta.3 — 2026-09-26

- Discover shows saved-user top albums and Trending as separate sections. Both apply artist blocks and Hide Available Albums.
- Lidarr album identifiers take priority over title matching. Administrators can link a Discover album to an existing scanned Lidarr album; links apply across accounts. Plex remains the playback/track-match check. Availability is still a snapshot, not a live guarantee of edition completeness.
- Playlist sorting includes Date Added and Reverse Sort. Three-dot and bulk actions offer Follow Server Schedule and Manual Only; selected schedules update without waiting for a running sync. Existing custom schedules are replaced only for selected playlists.
- Shared playlists are visible to users, with read-only source previews and album availability. Already subscribed or queued sources are hidden per account; the user section disappears when empty. Publishing remains administrator-only.
- Apple Music service names decode correctly and lose the service suffix. Known automatic names are cleaned; custom names are preserved. Older shared entries without naming provenance receive display-only cleanup.
- Selected album results include an inline request button. User request dialogs close after submission and track details update their request status.
- Settings → Users supports administrator promotion, playlist/request permissions, automatic approval, download visibility and download management. Promoted users retain their own playlists and Plex credentials. The owner cannot be demoted/disabled, and the last administrator is protected. Download visibility/management grants access to server request downloads; integration credentials/settings stay private.
- Administrators can approve/decline pending requests and remove completed/inactive Bridge request records. Removal leaves Lidarr albums, files and downloads intact. Active Bridge request jobs must finish first.
- Duplicate-track play queues use the ordered-list URI supported by PlexAPI with an explicit client identifier, avoiding one queue-add call per occurrence. The returned order/count is verified before use; unsupported responses fall back to standard additions. Detailed fallback diagnostics stay in DEBUG. Plex may still collapse duplicates.


## 3.0 Beta 2 — 2026-09-26

Account-scoped concurrent jobs and admin Activity, queued-edit-aware syncing, shared-cache improvements, source audit history, saved Last.fm usernames and artist blocks, richer Discover/album availability, Plex user imports and permissions, configurable task times, backup controls, custom MusicBrainz servers, and the pending layout/search/status fixes. See BUILD-NOTES.md for behavior and limitations.

## 3.0 Beta 1 — 2026-09-25

Plex account sign-in, isolated personal playlists and jobs, administrator-controlled shared scheduling and album requests, Last.fm Discover and top-album review, and an admin Plex/Lidarr Library comparison. Includes the pending structured Lidarr search, MusicBrainz year/review-link and missing Plex destination safeguards. See BUILD-NOTES.md for upgrade requirements and beta limitations.

# 2.2 Beta 3

Package/image version: `2.2.0-beta.3`. Beta channel only; default port 8173. Stable main/latest remain on 2.1.0.

- One global Sync Playlists task and one all-playlist, read-only Health Check task.
- Server schedule, Custom schedule, or Manual only per playlist. Custom runs remain independent when the global task is disabled.
- Favorites and Auto Sync flags removed from the web interface. Explicit Sync Now, Sync Selected, and Sync Filtered actions retain manual control.
- Retry Missing Matches marks Ready to Sync and follows the configured schedule instead of creating another automatic sync path.
- Rename playlists in Bridge and Plex, preserve custom names across syncs, restore source names, and choose a destination name when adding. Duplicate titles remain separate by source and Plex IDs.
- Plex descriptions retain source text and include one replaceable successful-sync summary with the source link, timestamp, and track counts.
- Stale Lidarr album IDs are cleared or relinked by release-group identity. Missing albums offer Add Album Again instead of a stale Open/Retry link.

# 2.2 Beta 2

Package/image version: `2.2.0-beta.2`. Default port: 8173. Beta channel only; main/latest remain on 2.1.0.

- Persistent full Plex and Lidarr inventories, service-scoped caching, and read-only availability reconciliation.
- Separate scan and missing-match retry tasks; scan preferences live under their service settings.
- Requests require a download queue entry for In Progress; added but unimported albums without downloads need attention.
- Durable, latest-value-wins playlist setting changes avoid lock errors during active jobs.
- Per-playlist weekly schedules, server timezone, overlap prevention, and unchanged schedules after manual runs.
- Include/exclude/off filters and Ready to Sync for pending match changes.
- Conservative matching normalization for standalone ampersands, leading artist “The”, apostrophes, and Unicode accents. Recording-version safeguards and thresholds remain intact.

# 2.2 Beta 1

- Add configurable Media Availability scans and requested-track Plex status.
- Reuse Plex library snapshots in sync jobs and batch discovered matches per Auto Sync playlist; preserve manual/ignored selections and show Ready to Sync elsewhere.
- Skip unchanged Plex track-list writes and log source/library/matching timings.
- Improve Requests navigation, album-result layout, and links to Lidarr albums and downloads.

# 2.1 final

- Requests navigation and download/import-only Activity view.
- Missing row alignment and Artist/Album sorting.
- Lidarr album artwork and standalone album search from Search.
- Editable MusicBrainz Recording, Artist and Album fields, including album-only searches.
- Includes all 2.1 beta improvements; universal playlist distribution remains planned for 2.2.

# Playlist Bridge 2.1 Beta 8

- Add Missing-page bulk Ignore with one scope confirmation, queued per-track results, and protection against hidden selections.
- Replace duplicate sort directions with one Reverse sort toggle; preserve saved preferences and align Track Details filtering with Playlist Details.
- Separate Jobs and Album Downloads with clear headings and active tabs. Add remembered download status/text filters, standard refresh controls, and collapsible completed/cancelled history.
- Use concise decoded service errors and expandable technical details; keep stack traces/raw diagnostic bodies at DEBUG and actual failure messages at ERROR.
- Correct success-message styling and operation-specific progress text. Show friendly playlist names and Stop Ignoring actions in settings.

# Playlist Bridge 2.1 Beta 7

- Restore Ignored, Manual and Automatic alongside Needs Attention in playlist-detail filters.
- Add ascending/descending playlist sorting by name, last synced and missing count.
- Request the selected Apple preview album through Lidarr while retaining the preview and page context.
- Add Activity → Downloads with persistent album status, real download progress, import errors, and confirmed cancel/replacement actions; retry searches recheck active downloads.
- Distinguish imported music from Plex availability, preserve imported files, and reject ambiguous multi-album queue removals.
- Audit logging: MusicBrainz lookup/cache/retry/result details at INFO, upstream errors at ERROR, pending operations at WARNING, and routine HTTP polling/candidate diagnostics at DEBUG. Correlate request logs and redact secrets.

# Playlist Bridge 2.1 Beta 6

- Return from Track Details to the originating playlist/page, retaining filters and scroll position; preserve origin through refresh and browser Back.
- Keep song previews inline near the track, with playback above a bounded recording list; closing the preview stops playback.
- Add shared Ignore and Add Album to Lidarr actions to Track Details, with request status, single-playlist preselection and clear selection guidance.
- Simplify playlist-detail filters to Needs Attention (or all tracks when cleared); retain per-playlist search/filter/sort state during navigation.
- Apply release-type priority and studio preference to Lidarr results as well as MusicBrainz results, before the result limit.
- Label MusicBrainz as Advanced Lookup; offer Apple Music album suggestions for tracks with unknown source albums, without changing source metadata or saved matches.

# Playlist Bridge 2.1 Beta 5

- Prefill album searches with Artist - Album, falling back to Artist - Track.
- Add Bypass cache for fresh MusicBrainz lookups; Lidarr searches already go directly to Lidarr. Keep prior results visible during retries.
- Show monitoring status for existing Lidarr albums and offer Search Album without adding the album or changing monitoring settings.
- Collapse album options under saved defaults.
- Add a musical bridge logo to the sidebar and page headers.
- Report named missing Plex tracks, expected/retained counts and redacted upstream error responses. Duplicate collapse remains acceptable; unmatched source tracks do not fail syncs.
- Report saved match edits plus failed follow-up syncs as partial success, retaining per-playlist errors for repair.

# Playlist Bridge 2.1 Beta 4

- Observe Lidarr initial refresh and track readiness without starting a duplicate refresh.
- Persist album requests across playlists and restarts, with album-added/search-pending/search-failed outcomes and a search-only retry action.
- Avoid duplicate album requests; a pending search command is resumed rather than submitted twice. Unknown search submissions require inspection in Lidarr.
- Simplify Add Album to one dialog, automatically search Lidarr on opening, and show confirmation on the originating page.
- Add Ignore to playlist details with playlist-only and universal scope.
- Consolidate playlist health/missing/LOST filters under Needs Attention; migrate stored filter selections and simplify the health summary wording.

# Playlist Bridge 2.1 Beta 3 — album search and navigation

- Wait for album metadata refresh before explicitly searching a newly added album, and track command completion with a bounded wait.
- Report refresh/search failures without repeating album additions or claiming downloads succeeded.
- Stay on the current page after queuing an album request.
- Add the same Lidarr album workflow to playlist-detail tracks.

# Playlist Bridge 2.1 Beta 3 — album review diagnostics

- Add Retry Review Once after a failed read-only album review; prevent overlapping review requests.
- Log Lidarr request starts, completions, release-group IDs and review stages at INFO.
- Preserve available Lidarr error response text and exception details at ERROR with credential redaction.
- Identify the exact failed endpoint and elapsed time; distinguish read-only timeouts from uncertain writes.

# Playlist Bridge 2.1 Beta 3 — maintenance update

- Register MusicBrainz settings before the website route so album lookup can initialize.
- Load saved Lidarr tag names on settings entry and flag missing tags.
- Replace stale loading text after album options fail to load.
- Log track identity and results for automatic matches, candidate search and Apple previews; include top candidate scores and penalties in debug output.
- Add regression coverage for API routing with the built website present.

# Playlist Bridge 2.1 Beta 3

- Add Settings → MusicBrainz with release priority, studio-release preference, cache retention, connection test and cache clearing.
- Reorder cached and fresh candidates before applying the display limit, without changing automatic track matching.
- Retry transient MusicBrainz lookup failures up to the configured limit (default two retries), with 15/30/45-second countdowns.
- Retry Once bypasses cache and automatic retries, making one attempt per press. Closing the dialog cancels pending retries.
- Existing MusicBrainz enable/cache preferences are used until the separate settings are saved.

# Playlist Bridge 2.1 Beta 2

- Keep API failure reasons, timing and request IDs in application logs; retain job IDs and debug stack traces.
- Distinguish upstream timeouts, connection/TLS failures, HTTP errors and invalid JSON. Only HTTP 429 is described as rate limiting.
- Add debug timing for source/Plex and Lidarr requests; retain quiet normal polling and redact API keys and authorization values.
- Replace the artist-tag list with inline Create & Add and removable tag chips, in settings and album options.
- Keep Lidarr fields at a consistent compact height.

# Playlist Bridge 2.0

Playlist Bridge 2.0 is the final release of the web application, with SQLite persistence, Docker deployment and the existing CLI and matching engine.

- Dashboard cards open their corresponding pages. Playlist cards apply the exact matching filter, clear previous search/filter state and remember the resulting view. Health Drift and Health Errors use the same predicates as their dashboard counts.
- Quick Actions has a pencil editor for up to five actions, including sync scopes, Health Check, Back Up Now and Check for Updates. Selection and display order are remembered in the browser.
- Add Playlist is one action: paste a public Spotify or Apple Music URL, choose Favorite and Auto Sync, and add it. Invalid or already registered URLs are rejected inline before queuing. Fetching, matching and Plex creation run as a background job with Activity details. The analysis API remains compatible for existing clients.
- All dialogs render above the application panels, centered in the visible viewport even after scrolling. Dialog content scrolls internally, controls remain reachable on mobile, keyboard focus stays within the dialog and returns to the trigger when closed. This includes Ignore, Fix Match, removal, backup restore, log clearing and Quick Actions.
- Match labels are consistently Auto, Manual, Saved, Missing, LOST and Ignored. Saved means an older match whose origin is unknown; it is not relabeled as Auto or Manual. Existing mappings and internal field names are preserved. Sorting uses Last synced.
- Activity has permanent desktop and mobile navigation, full job history and retained logs. Playlist filters, bulk Auto Sync, consistent Settings pages, daily backups, restore and midnight-aligned recurring tasks from Beta 8 are included.
- Git branches main and beta and Docker image tags main, beta and 2.0.0 receive the same final release. The default Compose image and update channel are main. Set HARMONIA_UPDATE_CHANNEL=beta to follow beta update notifications instead.

See BUILD-NOTES.md for compatibility and publishing details.

# Playlist Bridge 2.0 Beta 8

Playlist Bridge 2.0 Beta 8 focuses on remembered views, quiet activity and clearer settings.

- Playlist filters, name search, sorting and Compact/Expanded preference survive page navigation and browser refresh. Checkbox selections clear when leaving the page. Sync / Refresh acts on selected playlists, or the filtered set when nothing is selected.
- A permanent Activity button sits above Settings on desktop and in the mobile bottom navigation. It shows No active jobs, current progress or an attention indicator. Starting a job keeps you on your current page. Live output, results, Stop, Copy, Raw and Download are on the dedicated Activity page; job history is paginated across all saved jobs.
- Multi-select Auto Sync On/Off changes only the selected registrations without starting a sync. A static circular-arrows icon shows Auto Sync status in both playlist views.
- Settings has separate General, Plex, Matching, Ignored Tracks, Tasks, Backups, Logs and About pages. Panels share one content width; long ignored-track names wrap within it. Mobile Settings uses a section list and back navigation. Ignored Tracks supports filtering and bulk restore; Matching includes artist alias editing.
- Tasks lists all recurring jobs, including built-in Backup and Check for Updates, with last run, last result, duration, next run and Run Now. Options are Disabled, Every hour, Every 3 hours, Every 6 hours, Every 12 hours and Daily. There are no cron fields, time pickers or weekly schedules.
- Intervals align to midnight in the displayed app timezone. Manual runs never shift schedule boundaries. A scheduled occurrence is skipped and recorded when the same action/scope is queued or running. Different tasks may queue normally. Missed runs during downtime coalesce to one rather than replaying a backlog.
- Backups run daily at midnight by default. Back Up Now, Download and Restore are available. Scheduled backups retain 14 copies by default (7/14/30 configurable), with five manual and five pre-restore copies retained separately. Restoring creates a safety backup, restores app state and history, cancels queued work against the previous state, and leaves Plex untouched.
- About shows the release version, update status, last check and Check for Updates. The fixed six-hour update check is now a visible task with persisted job history. The browser title remains Playlist Bridge; no build number appears in the UI.

Beta 7 matching, duplicate handling, track membership previews, manual/automatic provenance, and optional Plex playlist removal are preserved. Standalone health checks remain read-only with respect to Plex and sync state.

See BUILD-NOTES.md for upgrade and publishing details.

# Playlist Bridge 2.0 Beta 7

Playlist Bridge 2.0 Beta 7 brings a consistent glass-style interface and clearer matching workflows.

- Desktop sidebar and floating mobile navigation, with accent colors and Light, Dark or Follow System appearance in General settings. Preferences are saved in your browser.
- One job terminal with timestamped progress. Playlist page loading uses a temporary status line that disappears when ready. Copy uses the native clipboard; Raw opens selectable text in the same panel, and Download saves the full log. Clipboard access requires browser support and a secure context; Raw remains available on plain HTTP.
- Unresolved source tracks produce completed-with-missing results. Actual Plex write/verification failures remain errors. Duplicate source occurrences are submitted in order using Plex's play queue support; if Plex collapses duplicate occurrences, the job warns and completes when the remaining distinct tracks and order are correct.
- Playlist filter, sort, refresh and Compact/Expanded icon controls sit together. Filters include Favorites, Needs Attention, 100% Matched, Has Manual Matches, Auto Sync, Missing, LOST and Never Synced. Multiple filters use AND; removable chips and Clear Filters reset them.
- Select multiple playlists for Sync / Refresh or removal. Sync acts on selected playlists, or the filtered set when none are selected. Removal asks whether to leave Plex playlists untouched (the default) or delete them too. Historical job output stays available, and unrelated registrations and mappings are preserved.
- Saved-match counts distinguish Auto, Manual and Legacy. Track names open Track Details with known playlist memberships, occurrence counts and current matches. Select playlists, preview a fresh automatic match or manual replacement, then apply and sync those playlists. Ignored occurrences are skipped; an unsuccessful automatic retry leaves existing matches unchanged.
- Accepting an automatic suggestion records Auto provenance; choosing a manual candidate records Manual. Existing matching rules and thresholds remain unchanged.
- A version-adjacent update indicator checks the public GHCR beta image every six hours. General settings includes Check Now. Updates are never installed automatically.
- Global search remains on its own page; page-local search fields filter the current page. The browser title is Playlist Bridge and the sidebar release label has no build number.

Earlier behavior remains: SQLite job-event history, sync-derived health, cached list rows, short-lived Analyze → Add reuse, and one generated schedule per action/scope. Standalone health checks remain read-only with respect to Plex and sync/matching state.

See BUILD-NOTES.md for packaging, limitations and publish commands.

# Playlist Bridge 2.0 Beta 6

Live terminal-style activity with service waiting states, follow/copy/download controls, retained summaries, quieter notifications, three quick filters, a layout icon, compact health indicators, overflow menus, relative sync dates, dedicated Search, and no added dates or visible build numbers. SQLite schema 4 and Docker port 8173 remain unchanged. See BUILD-NOTES.md for details and delivery limitations.

# Playlist Bridge 2.0 Beta 5 — build 20260908.9

Staged detail progress; durable job event details; sync health persistence; compact view; AND filters and scoped Sync / Refresh; app-only removal; cached page rows; detail status filters; automatic-first Fix Match; reusable analysis; unique generated schedules; SQLite schema 4. See BUILD-NOTES.md for behavior and delivery limitations.

# Playlist Bridge 2.0 Beta 4 — build 20260908.8

- Replace global 2.5-second refresh with non-overlapping, completion-scheduled job/health polling; coalesce concurrent GETs including React StrictMode mounts.
- Fetch page lists on entry and state changes; fetch settings data only in its mounted section. Remove schedules interval polling.
- Give browser requests deadlines and detail loads a stable, serialized lifecycle with errors/retry. Refresh details only for relevant completed changes.
- Isolate detail generation in a two-worker pool with a 60-second HTTP deadline and busy responses. Retain occupied capacity until timed-out workers actually exit. Use strict Plex errors instead of silently returning failed reads as missing matches.
- Move request logging off the event loop. Reuse repository initialization, keep request-local state, omit read-only baselines, and load lightweight endpoint namespaces on demand. Read health buckets once per playlist-list request.
- Batch log cleanup every 100 inserts, retaining the same visible 1,000-entry window. Add log, job, schedule, and health-history indexes without a schema-format change.
- Execute health batches with three workers, incremental saved results, cancellation checkpoints, and no sync-state saves. Remove health's global stdout capture lock; persist structured result summaries and diagnostics.
- Revalidate HTML and cache hashed assets as immutable. Keep Docker default port 8173.

# v2.0.0-beta.3

Overview dashboard; background jobs and cron schedules; safe job cancellation; detailed health drift; last-sync dates; universal ignore and linked missing memberships; playlist/missing sorting and filters; track and playlist search; improved add feedback; Settings sections and log controls. SQLite schema 3. Separate build numbers removed.

# v2.0.0-beta.2 — build 20260908.7

- Health checks show running indicators, numbered batch progress, and completion/failure status across navigation.
- Plex URL/connectivity, timeout, TLS, token/access, invalid-response and missing-resource failures have actionable messages and Settings links. Failed reads no longer masquerade as empty Plex playlists during health checks.
- Last failed health attempts persist while last successful results remain intact.
- Settings includes persistent, bounded and credential-redacted application logs with level filters.
- Match selection uses an explicit Save Match step and always-visible Cancel/Close controls, including Escape and backdrop dismissal before save.
- Playlist detail navigation consistently highlights Playlists and returns to the playlist list.
- SQLite schema 2 adds application logs and upgrades beta 1 databases without changing sync state. Matching heuristics, CLI defaults and Docker port 8173 are preserved.

# v2.0.0-beta.1 — build 20260908.6

- SQLite runtime storage with automatic validated legacy migration and preserved backups.
- Persistent, collapsible playlist health with incremental results and timestamps.
- Playlist details and manual Fix Match for existing mappings, with selected/apply-all unresolved occurrences.
- Version, matching heuristics, CLI entry points and Docker port remain unchanged.

# Changelog

All notable changes to Playlist Bridge are documented here.

## [1.3.5] - 2026-08-24

### Added

- Added brand-appropriate terminal colors for Spotify and Apple Music service labels.
- Added consistent color treatment for Auto sync ON/OFF and automatic/manual/legacy match provenance.
- Added aligned provenance summaries and subdued secondary metadata for easier terminal scanning.
- Added consistent section dividers for long sync and dry-run output.
- Added Pillow-based local center cropping for sufficiently large non-square playlist artwork.
- Added read-only matching diagnostics for an unregistered Spotify or Apple Music playlist.
- Added a consolidated read-only album playlist-coverage diagnostic grouped by artist and album.
- Album coverage now reports the number of covered tracks versus total tracks for each album.

### Changed

- Auto sync status now uses a filled status dot for both ON and OFF; color communicates the state.
- Apple Music artwork URL handling now preserves query parameters while generating alternate CDN renditions.
- Apple Music artwork now prefers square `cc` CDN crops before falling back to a local center crop.
- A wide `1200x630` source image can now be center-cropped to a true `630x630` poster without stretching.
- Album playlist coverage now compares only against Plex playlists registered with Playlist Bridge.
- Unrelated Plex playlists, smart playlists, and generated playlists no longer affect Playlist Bridge album-coverage diagnostics unless explicitly registered with Playlist Bridge.
- The two separate positive/negative album-coverage views were consolidated into one artist-grouped report.

### Fixed

- Fixed Apple artwork URLs with query strings such as `?l=en-US` failing to generate square CDN variants.
- Fixed wide Apple social-preview images being rejected without a usable square fallback.

### Dependencies

- Added `Pillow>=9.0.0` for local artwork center cropping.

### Compatibility

- State schema remains 2.
- No JSON reset or migration is required.
- Matching, permanent-ignore, auto-sync, provenance, source-snapshot, and LOST behavior remain compatible with 1.3.

## [1.3] - 2026-08-24

### Added

- Added per-playlist permanent track ignores in Option 5 and Option 6.
- Added `[i] Ignore permanently` while resolving missing tracks or editing an existing match.
- Added `ignored_tracks.json` for persistent per-playlist ignore state.
- Added Settings → **Manage ignored tracks** to restore individual ignored tracks or all ignored tracks for a playlist.
- Added per-playlist `Auto sync` ON/OFF state.
- Added Settings → **Manage auto-sync**.
- Added one-time/manual-only playlist behavior while keeping the playlist fully registered.
- New playlists now ask whether they should participate in automatic `--sync-all` / cron runs.
- Added Auto sync status to registered-playlist and manual-sync displays.
- Added `Ignored` count to sync summaries.

### Changed

- Automated `python sync.py --sync-all` now skips playlists whose Auto sync setting is OFF.
- Interactive **Sync all playlists** remains an explicit manual action and continues to sync every registered playlist.
- Interactive **Sync specific playlist** remains available regardless of Auto sync state.
- Existing playlists with no `auto_sync` field default to Auto sync ON.
- Permanently ignored tracks no longer participate in matching, unresolved lists, or destination Plex playlist construction.
- Ignoring an already-matched track removes its saved mapping and provenance.
- Restoring an ignored track makes it eligible for normal matching on the next sync.
- State schema advanced from 1 to 2.
- Schema 2 adds ignored-track state and optional per-playlist automatic-sync state.
- Existing schema-0 and schema-1 state migrate to schema 2 using the existing one-time backup mechanism.
- Dry run remains fully read-only, including ignored-track state and schema migration.

### Compatibility

- No reset is required when upgrading.
- Existing playlists default to Auto sync ON.
- Existing matching, missing-track, provenance, and source-snapshot data remains compatible.
- Older state files receive `.pre-schema-2.bak` backups before the first schema-2 rewrite.

## [1.22] - 2026-08-24

### Added

- LOST tracks now retain the previous Plex track ID and, when known, previous title, artist, album, and provenance.
- LOST status and previous-match details remain visible during manual unmatched-track review.
- Existing valid mappings learn a destination metadata snapshot for future LOST reporting.
- Added a read-only Developer Tools report for Plex albums with zero tracks on any Plex audio playlist.

### Changed

- Legacy mapping validation now runs only for mappings whose provenance is actually `legacy`.
- When the current automatic matcher independently chooses the exact same Plex track as a valid legacy mapping, that mapping is promoted to `automatic`.
- Legacy mappings remain unchanged when the current matcher disagrees or cannot confidently match.
- Manual and already-automatic mappings are not reclassified by the legacy-validation path.
- Dry run does not promote legacy mappings or write provenance changes.

## [1.2] - 2026-08-22

### Added

- Added sync-to-sync source playlist tracking with `ADDED` and `REMOVED` reporting.
- Added mapping-state tracking with visible `NEW` and `LOST` markers.
- Added an end-of-sync summary showing source tracks, matched tracks, new matches, lost matches, source additions/removals, and unresolved tracks.
- Added lightweight persistent source snapshots in `source_snapshots.json`.
- Added match provenance in `match_metadata.json` with `automatic`, `manual`, and protected `legacy` states.
- Added **Clear automatic matches** in Settings, preserving manual and legacy mappings.
- Added a deduplicated **All missing tracks** view across all registered playlists.
- Added **Last match attempt** timestamps to Option 5 and sort unresolved-playlist triage oldest first, with `Never` first.
- Added multi-playlist selection to Option 3 using comma-separated selections and ranges such as `1,3,5` or `1-3`.
- Added `--sync-all --dry-run` for read-only source fetching, Plex scanning, matching analysis, and change reporting.
- Added persistent JSON schema versioning independent of the application version.
- Added automatic schema-0-to-schema-1 migration for existing unversioned state.
- Added one-time pre-migration backups such as `mapping.json.pre-schema-1.bak`.
- Added protection against loading/writing state created by a newer unsupported schema.
- Added Spotify public-track ID fallback using the track URI when an explicit track ID is absent.

### Changed

- Playlists shown with **Last sync** are sorted `Never` first, then oldest to newest.
- Registered playlist display is also ordered oldest-last-sync first.
- Option 5 Back now returns to the unresolved-playlist list instead of the main menu.
- Submenus that show `[b] Back` also treat an empty Enter as Back.
- Option 6 now displays automatic/manual/legacy provenance counts and per-track provenance.
- Explicit candidate choices and confirmations in Options 5 and 6 are stored as manual mappings.
- Stale manual and legacy mappings are no longer silently replaced by a new automatic guess.
- Improved matching for explicit demo, acoustic, live, remix/mix, and branded session recordings.
- Branded iTunes, Apple Music, and Spotify sessions are treated as distinct recording intent.
- Generic album-era labels such as `Evolver Sessions` are treated as provenance rather than automatically as branded-session recording intent.
- Featured-artist metadata remains symmetric and does not by itself create recording-version intent.
- Prevented album bonuses from canceling unwanted title-level recording-version penalties.
- Playlist metadata text is repaired before being sent to Plex.
- Meaningful source playlist descriptions are preserved, while generic descriptions such as `Playlist · 86 Songs` are omitted.
- Source snapshots and match metadata participate in stored-state migration and normal saves.
- Dry runs remain fully read-only, including schema migration state.

### Fixed

- Fixed cases where a plain featured-artist recording could tie with or lose to an unwanted acoustic copy because an album bonus canceled the acoustic penalty.
- Fixed explicit demo requests collapsing to standard studio versions.
- Fixed branded session requests collapsing to studio recordings.
- Fixed named mix/remix and acoustic intent collapsing to plain recordings.
- Fixed generic `Sessions` text being over-classified as a distinct branded session recording.
- Fixed common playlist-description mojibake such as `Playlist Â· 86 Songs`.
- Fixed Option 5 submenu navigation returning too far up the menu hierarchy.

### Compatibility

- Existing 1.1 `config.json`, `mapping.json`, and `missing_tracks.json` files load without reset.
- Existing saved mappings are treated as `legacy` because pre-1.2 state did not record provenance.
- Legacy JSON is migrated only on the next normal save; dry run does not rewrite it.
- Existing state files receive one-time pre-schema-1 backups before migration.

### Notes

- `--sync-all` remains fully non-interactive.
- Public `--help` advertises `--sync-all` and `--dry-run`.
- Public Spotify and Apple Music playlist support remains API-key-free.
- Playlist Bridge remains licensed under GPL-2.0-only.

## [1.1] - 2026-08-20

### Added

- Option 3 now shows the last sync time beside each registered playlist.
- Option 5 now shows the full unresolved-track list before triage starts.
- Option 6 now shows the current saved-match count beside each playlist.
- Settings now includes **Clear matching for a playlist**.
- Matching can be cleared for one playlist or for **all playlists** with explicit confirmation and a summary of how many saved matches and unresolved records will be removed.

### Changed

- Renamed **Reconfigure Plex** to **Configure Plex**.
- Option 6 now saves match edits first and offers one full playlist sync when editing is complete instead of modifying Plex one corrected track at a time.
- Artwork discovery/fetching is skipped during Options 5 and 6 and runs only during actual playlist creation or synchronization.
- Clearing matching resets entries in `mapping.json` and `missing_tracks.json` while leaving playlist registrations and Plex playlists unchanged.

### Notes

- `--sync-all` remains fully non-interactive.
- Existing saved mappings continue to be respected unless they are explicitly cleared.
- Playlist Bridge remains API-key-free for public Spotify and Apple Music playlists.

## [1.01] - 2026-08-20

### Added and improved

- Improved parenthetical-title handling.
- Improved featured-artist and collaborator normalization.
- Added remix/live title intent handling.
- Improved soundtrack and `Various Artists` track-artist matching.
- Added common mojibake/text-encoding repair.
- Hid interactive candidates scoring below 50%.
- Improved preference for canonical studio-album copies.
- Kept automatic and manual match scoring more consistent.

This was the first formal GitHub release of Playlist Bridge.
## Build 20261005.9 — 2026-10-05

- Kept open request action menus above expanded request details so Remove from Bridge remains clickable.
## Build 20261006.1 — 2026-10-06

- Reordered Discover into personalized recommendations, albums from trending artists, and listening-history gaps.
- Removed the top-albums feed and generated recommendations from similar artists based on the user's recent listening.
- Added recommendation explanations and Show more controls; feeds continue to use saved refresh data.
