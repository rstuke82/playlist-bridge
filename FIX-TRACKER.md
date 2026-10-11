# Harmonia fix tracker

Updated for build 20261010.6. Fixed means implemented and locally validated; live deployment verification is separate. Original audit evidence is retained in the workspace audit-harmonia-20261009.9/AUDIT.md. F16 reflects the later admin-only P3 reprioritization.

| ID | Priority | Status / build | Short description |
| --- | --- | --- | --- |
| F01 | P1 | Fixed · .10 | Member-controlled playlist URL could make arbitrary server-side requests. |
| F02 | P2 | Fixed · .12 | Provider edits were discarded and concurrent saves could overwrite edits. |
| F03 | P2 | Open | Playlist permission checks miss ignore restoration and block read-only details. |
| F04 | P2 | Fixed · .17 | Delayed Lidarr Grab events can erase newer failure status. |
| F05 | P2 | Fixed · .17 | Missing-catalog polling branches can overwrite a newer webhook. |
| F06 | P2 | Open | Member requests use owner availability and omit actionable failure details. |
| F07 | P1 | Fixed · 20261010.6 | Delegated-admin prepared views lose server context. |
| F08 | P2 | Fixed · 20261010.2 | Single-playlist health checks become all-playlist checks; members are denied. |
| F09 | P2 | Fixed · 20261010.2 | Track details and match previews can use historical playlist membership. |
| F10 | P2 | Fixed · .10/.11 | Changing an Apple Music album link left stale artwork candidates; chooser recovery added. |
| F11 | P2 | Fixed · .10 | Issues suggested replacing releases already allowed by format/country preferences. |
| F12 | P2 | Fixed · .10 | Clearing library views did not clear durable prepared views. |
| F13 | P2 | Fixed · .12 | Factory reset retained member databases and derived personal state. |
| F14 | P2 | Fixed · 20261010.1 | Auth focus refresh retains expired users and old CSRF tokens. |
| F15 | P2 | Open · host-dependent | Native SQLite credential-store file permissions can be too permissive. |
| F16 | P2 | Open · admin-only | Webhook body-size enforcement relies on Content-Length. |
| F17 | P2 | Partially fixed | Runtime database archive residue and current docs cleaned; public-repo test inclusion/hygiene remains. |
| F18 | P2 | Fixed · .13 | Post-import Plex lookup searched track titles and stopped retrying before indexing completed. |
| F19 | P1 | Fixed · .14 | Activity rendered numeric album track counts as arrays, crashing the whole page on completion. |
| F20 | P1 | Fixed · .16 | Indefinite post-import retries revive old pending albums and rebuild views repeatedly. |
| F22 | P3 | Fixed · 20261010.1 | Organize Jobs into Running, Queued and Completed sections, ordered by execution history or queue position. |
| F23 | P1 | Fixed · updated 20261010.1 | Background saved-page rebuild churn delays first-time album loading on the single Views worker. |
| F21 | P4 | Open | Verify Duplicates walks every mapped music folder instead of verifying saved potential-duplicate candidates. |

## Build .17 additions

Discover Recently Added retains album-added dates on targeted imports and reloads saved views while visible. Harmonia release selection no longer opens or writes audio files. These fixes are locally validated; live deployment remains unverified.

## F19 evidence and validation

The live Safari console on Activity showed `TypeError: E.result.tracks.map is not a function` after an album finalizer returned a numeric `tracks` count. The actual React rendering regression fails on .13 and passes on .14. Activity now renders track and playlist result lists only for arrays. See ACTIVITY-20261009.14.md in the build for the exact changes.

## Verification still pending

Real Plex recovery of the reported Fall Out Boy album after deploying .13 or later; Activity stability on the deployed .14/.15 frontend; production factory reset, custom multiple-process deployments and mobile/accessibility device checks. Plex library.new webhook support remains a future idea.


## F20 fix

Follow-up checks are capped at six attempts and a 20-minute window anchored to the import/manual refresh. Expired or undated legacy records stop; queued expired checks perform no service reads. One recovery check is queued globally at a time. Unsuccessful follow-ups do not update inventory or rebuild views. Network failures consume the same retry budget. Requests show the stopped-check reason; manual Refresh This Album starts a fresh bounded window. Validated locally; deployment remains pending.


## F21 — candidate-only duplicate verification

Verify Duplicates currently runs the complete configured-folder audit before hashing same-album, same-size candidate groups (`playlist_bridge/file_audit.py`, `execute(verify=True)`). This repeats the folder traversal even when potential duplicates already exist in saved scan evidence. Priority P4: performance/workflow improvement; the existing byte-identical comparison remains functional.

Proposed fix: consume saved potential-duplicate candidate paths, validate their current signatures and configured-root access, and hash only eligible candidates. Changed, missing or stale evidence should request a fresh Scan Files rather than trigger a full traversal. Retain unaffected findings, preserve cancellation checks, and report candidate/verified/confirmed counts. No implementation or build change made.


## F22 — Jobs status sections

User-requested UI change: replace current Jobs grouping with three sections: Running, Queued and Completed. Keep running/cancelling jobs in Running; order Queued by execution queue position; place finished jobs (successful, failed, cancelled or interrupted) in Completed with newest completion first. Preserve explicit outcome labels, cancellation and detail access. Priority P3: improves visibility of active work and execution order. This supersedes the earlier flat-list request. Implemented and locally validated in build 20261010.1; production verification remains pending.


## F14 fix — build 20261010.1

Refresh processes null users and current CSRF tokens. Session/account/permission changes cancel in-flight API requests, clear old account storage and remove the old app before reloading a clean document, which discards all module caches. Same-session focus does not reload. Authoritative refresh sequencing and session generation checks reject obsolete refreshes and late response bodies. Same-origin API 401 responses invalidate the visible session. Network failures alone do not sign the user out. Locally validated; cross-browser production behavior remains unverified.


## F23 — saved-view rebuild churn and foreground starvation

Reported 2026-10-10: many Prepare Page Data events and long album loading. Offline reproduction against delivered build 20261010.1 confirms three unchanged download-status polls queue three listening-history rebuilds without history/inventory changes. DISCOVER includes lidarr_requests and user_requests; listening history shares DISCOVER. Polling updates download_checked_at routinely, advancing the namespace revision. saved_views.tick considers every persisted page, including old album/detail/filter pages, and enqueues up to three per account per tick without a recent-use requirement. All prepare_views jobs share the single Views worker; a new album with no saved data returns HTTP 202 behind earlier background jobs. Logs contain multiple events per job, so screenshot event count is not itself a job count.

Evidence: reproduce_view_churn.py and view-churn-reproduction.txt in this audit directory. Locations: playlist_bridge/saved_views.py DISCOVER, saved/read/enqueue/tick; playlist_bridge/lidarr_downloads.py snapshot; playlist_bridge/library.py album; playlist_bridge/jobs.py WORKER_LIMITS and worker planning. Code-level behavior is confirmed; the deployed queue size and elapsed runtime have not been measured.

Fix direction: give first-load/foreground page requests priority over background refreshes; narrow history/discovery dependencies to actual inputs; suppress revision changes from polling-only bookkeeping where suitable; refresh recently used or explicit startup landing pages rather than every historical page; coalesce queued revisions and stop obsolete background work safely. Preserve saved-view/account isolation and explicit refresh behavior. Implemented in updated build 20261010.1: demand-driven preparation, first-load priority, queued revision coalescing, narrowed dependencies and obsolete queued-job retirement. Ten regression tests added; 553 backend tests pass. Deployment behavior remains unverified.

## Build 20261010.3 additions

Artist/song searches return artist-credited containing albums and exclude compilations; featured lead credits can use close duration as supporting evidence; the chooser uses one candidate list. Existing open audit findings retain their status.

## Build 20261010.4 additions

Explicit featured credits are parsed for MusicBrainz discovery without changing source metadata. The five-recording rejection is removed. Search pagination beyond the initial 25 recording results remains outstanding.

## Build 20261010.5 additions

Targeted Plex album evidence preserves request completion against stale overall inventory. Imported timestamps are labeled accurately. Mobile navigation uses equal destination widths and a smaller bar/selection. Existing old requests need Refresh This Album once; physical-device verification remains pending.

## Remaining work — reprioritized after build 20261010.5

This table supersedes earlier priority summaries. Fixed items above remain fixed. Deployment verification is separate from confirmed defects.

| ID | Priority | Status | Remaining work |
| --- | --- | --- | --- |
| F07 | P1 | Fixed · 20261010.6 | Delegated-admin prepared views lose server context; verify account isolation and correct data scope. |
| F24 | P2 | Fixed · 20261010.6 | Upgrade vulnerable source-map-js build dependency and validate/publish a corrected build. |
| F25 | P2 | Confirmed open | Song-to-album discovery makes sequential repeated release lookups and blocks other searches under one lock; add incremental results and reuse. |
| F06 | P2 | Confirmed open | Member requests use owner availability and omit actionable failure details. |
| F03 | P2 | Confirmed open | Playlist permissions miss ignore restoration and block read-only details. |
| F15 | P2 | Host-dependent open | Restrict SQLite credential-store file permissions. |
| F16 | P2 | Confirmed open, admin-only | Enforce webhook body size without relying on Content-Length. |
| F17 | P2 | Partially fixed | Finish public-repository hygiene and test inclusion. |
| F26 | P3 | Confirmed limitation | Recording search fetches only the first 25 results; add pagination/load-more. |
| F27 | P3 | Investigation | Requests-page rebuilds may be triggered by polling-only bookkeeping; measure and suppress unnecessary invalidation. |
| F28 | P3 | Fixed · 20261010.8 | Album discovery does not strip supported qualifiers such as (Advance). |
| F21 | P4 | Confirmed open | Verify only saved potential-duplicate candidates rather than traverse all mapped folders. |

F07 is elevated because the affected boundary is account/server context. F24 is build-time exposure rather than a shipped runtime dependency. F27 remains suspected: repeated equal output sizes do not prove identical data. Requests confirmation/mobile appearance, real Plex recovery, factory reset and restart/member-isolation checks remain deployment validation, not additional confirmed defects.

## F07/F24 implemented after 20261010.5

Explicit server/account projection scope is reconstructed and permission-validated; source-map-js locked to 1.2.2. 613 backend tests and frontend build pass; npm audit reports zero vulnerabilities. Changes are in harmonia-f07-f24-fix, not yet packaged or pushed. Existing .5 registry tags remain unchanged.

## Build 20261010.6

Packages F07/F24 and Requests status sections. All existing filters and detail actions retained. Registry push status is recorded separately.

## Build 20261010.8

F28: MusicBrainz discovery strips supported Advance, Advance Copy, Advance Promo and Advance Version qualifiers from parenthesized/bracketed or separated suffixes. Original source metadata is untouched. Legitimate names such as Advance and Follow or Advanced Studies are preserved. Two regression tests cover six qualifier forms and four legitimate names.

Discover listening-history button now reads Ignore.

Both amd64/arm64 TypeScript/Vite image builds passed; npm reported zero vulnerabilities. Existing bundle-size warning remains. No live MusicBrainz/device verification. Docker build completed in local builder cache; registry tags have not been updated.

## Build 20261010.12 — UI audit fixes

UX01–UX13 are included in build 20261010.12, together with the shared control recommendations and tablet header correction. These IDs are independent of the older F findings. See UI-UX-FIXES.md for the per-ID resolution, exact changed files and validation. Backend: 634 tests passed; frontend: eight regression scripts passed; TypeScript/Vite production build passed. Registry publication status is recorded separately. Physical-device appearance remains unverified.

## Audit fixes — build 20261011.5

- A01 (P1): protected one-time setup claim and restart-safe configuration/owner journal — fixed.
- A02 (P2): bounded, shared sign-in polling with per-IP/global admission limits — fixed.
- A03 (P2): automatic first-owner inventory scan and initialization feedback — fixed.
- A04–A06 and deployment-dependent R01–R06 remain as documented in the 20261011.4 deep audit.

Build 20261011.5 published to its version tag and beta; AMD64 and ARM64 confirmed. A01–A03 are resolved. Remaining confirmed findings: A04 (P2), A05 (P2), A06 (P3). Deployment checks R01–R06 and live service/device validation remain pending.


## Audit fixes — build 20261011.6

A04 (P2), A05 (P2) and A06 (P3) are implemented. Member searches are queued and cancellable; first-run Plex setup falls back between advertised connections; artwork downloads enforce streaming size and bounded concurrency/deadline limits. Deployment checks R01–R06 and live service/device verification remain pending.

Published version and beta for AMD64/ARM64; registry digest sha256:471e01defcc7135f00d2e144e7d2b939c99b3fff6dd90eb96caf684600db94ab. Validation: 678 backend tests, 13 frontend scripts, production build passed.

## R01 and R04 — prepared after 20261011.6

R01 application controls and deployment defaults implemented: explicit proxy trust, optional HTTPS-only admission/Secure cookies, loopback Compose binding and proxy setup guidance. R04 application headers implemented: enforced compatible CSP/framing protection, HTTPS HSTS, nosniff, sensitive API/cookie no-store and disabled public API docs. Actual public TLS/proxy/firewall/cookies and physical-device behavior remain unverified. R02, R03, R05 and R06 remain open. No publication is implied by this entry.

R01/R04 validation: 686 backend tests and TypeScript/Vite production build passed. Exact changes: R01-R04-CHANGES.md.

## Remaining risk implementation and Requests pagination — unpublished working copy

- Requests: per-section pagination footer with Showing range/total, Display selector (5, 10, 25, 50, 100; default 25), Previous/Next controls and mobile layout. Completed remains collapsed by default; all expanded status sections paginate.
- R02: non-root UID/GID 10001, private writable data, read-only root, dropped capabilities, no-new-privileges, bounded tmpfs/memory/CPU/PIDs. Existing volume migration remains a deployment prerequisite.
- R03: validated/pinned public HTTPS artwork, revalidated redirects, no cross-origin Plex image redirects or automatic credentialed service redirects.
- R05: approval-first new/imported members, atomic 25-pending-approval limit, atomic member/admin job admission caps (25/200), duplicate joins and cancellation recovery.
- R06: exact Python lock and startup include validation, pinned multiarchitecture bases/scanner, Debian Trixie runtime, no runtime pip, prepared native AMD64/ARM64 image build/test/scan workflow. Actual CI installation/execution remains pending.
- R06 advisory remains OPEN: scanner flags high CVE-2026-85091 in Debian zlib; Debian tracker marks it unfixed. Remote exploitability in Harmonia is unverified. Final images contain no critical findings, one high, one medium and 26 low findings on each architecture. No advisories were suppressed.

Validation: 697 backend tests passed locally and in the hardened Python 3.12 ARM64 container; 13 frontend regression scripts passed; production frontend and AMD64/ARM64 image builds passed; non-root data-write/import smoke passed; pinned public HTTPS transport returned HTTP 200 from Apple. No publication, production service/proxy/firewall change, data-ownership change or physical-device verification was performed.

Final source-matched local image scans confirmed the same advisory counts on both architectures. Image index: sha256:ab066837f95aabaae9e7731e8008210eb15e00e3535f4988306f8c06ff75b69e. Exact changes and remaining verification: SECURITY-HARDENING-CHANGES.md.

Prepared as build 20261011.9; no registry push or deployment performed.

## Build 20261011.9 — prepared, unpublished

Completed environment branding migration to HARMONIA_* with no legacy aliases. Updated application startup, Docker health check, Compose interpolation, optional music mount, documentation and tests. Runtime data layout is unchanged. Validation: 698 backend tests, 13 frontend regression scripts, production frontend build and both Compose configurations passed.

## Build 20261011.9 — prepared, unpublished

Fixed false Needs Action for queued/pending requests and continuing Lidarr searches. Preserve request artwork and requester avatars. Redesign homepage recent-request cards with right-side artwork, left-side requester/album/status, no year, and responsive light/dark styling. Rename Review / Request to Request Album. Refresh saved request projections on upgrade. Validation: 701 backend tests, 14 frontend scripts, production frontend build and Compose configuration passed.
