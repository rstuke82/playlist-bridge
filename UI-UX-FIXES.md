# UI/UX fixes based on build 20261010.11

All thirteen confirmed UI audit defects are included in build 20261010.12, based on 20261010.11. Registry publication status is recorded separately.

| Audit ID | Change |
|---|---|
| UX01 | Requests honor the chosen field and direction within each status section. |
| UX02 | Library clears query, availability, primary release types and secondary release types, including saved exclusions. Active filters have visible removable chips. |
| UX03 | Shared request classification gives errors, cancellations and partial availability precedence over completion. Covers use partial/error indicators rather than green checks for these states. |
| UX04 | Administrator attention badges count attention requests; otherwise badges count active downloads. Count, color and accessible wording describe the same thing. |
| UX05 | Artist-link provider switches, result choices and searches lock during an operation, keeping each response with its provider. |
| UX06 | Ignore recovery instructions point to Blocklist → Ignored Tracks. |
| UX07 | Profile/account shortcuts to Missing tracks use that name. The actual management settings retain Library Management. |
| UX08 | Search disables the request action when permission or optional Lidarr availability prevents requests, with an explanatory title. |
| UX09 | Artist, artwork and association dialogs consistently guard direct Close/Done actions during mutations. Editable forms freeze while saving. |
| UX10 | Track playlist filter and text playlist input have explicit accessible names. |
| UX11 | Blocklist and recent requests distinguish loading, errors and loaded-empty states. Blocklist provides retry; settings feedback uses shared error notices and loading/status announcements. |
| UX12 | Job history includes the Lookup worker. Internal Views jobs remain omitted intentionally. |
| UX13 | Playlist editing requires successfully loaded revision data. Failed loads expose Retry; fields and Save stay disabled while loading or saving. |

Additional audit recommendations addressed:

- Requests and Issues now use the shared sort control. Shared sorts name the actual order: A–Z/Z–A, oldest/newest, fewest/most, or source/reverse source order. Each control uses independent radio groups.
- Requests, Issues and artist releases display active filter chips and a consistent Clear Filters action. Tri-state menus explain their page's any/all/category combination semantics without changing the existing matching rules.
- Jobs navigation labels match their destination; outdated Tasks and Library → Issues instructions were corrected. Add Playlist's empty-state link opens and focuses the actual Add form, including old dashboard aliases.
- Library and playlist refresh buttons disable during refresh. Settings, text composition and playlist editing guard in-flight edits.
- The mobile header's two-row layout now applies through 850px, matching the brand/sidebar breakpoint. The imported CSS cascade places brand and search on separate rows at 390, 760, 800 and 850px; desktop keeps the brand hidden in the header.

## Exact product files changed

All paths below are relative to this working copy:

- `web/src/requestPresentation.ts` — new shared request classification and badge helper.
- `web/src/AlbumCover.tsx`, `AppNavigation.tsx`, `LidarrRequests.tsx` — consistent request presentation, sorting and shared load-state exposure.
- `web/src/Controls.tsx`, `LibraryIssues.tsx`, `Library.tsx`, `PlaylistsView.tsx`, `TrackDetails.tsx` — sort/filter controls, resets, refresh locks and accessibility.
- `web/src/ArtistLinks.tsx`, `ArtworkPicker.tsx`, `PlaylistEditor.tsx`, `TextPlaylist.tsx`, `Discover.tsx` — operation locks, dismissal protection, editor recovery and form labels.
- `web/src/DiscoverPreferences.tsx`, `DiscoverShelves.tsx`, `General.tsx`, `ConsoleSettings.tsx`, `MetadataSources.tsx` — loading/error/save feedback and disabled states.
- `web/src/IgnoreDialog.tsx`, `BulkIgnore.tsx`, `Auth.tsx`, `ActivityNav.tsx`, `JobsPanel.tsx`, `App.tsx`, `LocalLibrary.tsx`, `SettingsTools.tsx`, `SearchPage.tsx` — corrected navigation/copy, Lookup filter, Add focus and request capability gate.
- `web/src/pass-20261008.css`, `discover-layout.css` — tablet breakpoint, form reset styling and partial-status appearance.

No backend implementation, service permissions, audio tags or dependency versions were changed. The released .11 source and synced `sources/` were preserved.

## Regression tests and validation

Added `tests/test_ui_consistency.cjs`. It evaluates actual source components/handlers with controlled service responses and checks sorting in both directions, partial/error precedence, badge meaning, complete filter reset and persistence, blocked provider changes and modal dismissal, editor load failure, loading/error/empty states, optional-Lidarr/account gates, accessible names and the imported header CSS cascade.

- Backend: **634 tests passed** (`verification/backend-ui-fixes.txt`). The first attempt correctly reported a missing frontend build; after building, the full suite passed.
- Frontend regressions: **8 scripts passed**, including all seven existing scripts and the new consistency regression (`verification/frontend-regressions-ui-fixes.txt`).
- TypeScript and Vite production build: **passed** (`verification/frontend-ui-fixes.txt`). The existing bundle-size warning remains.
- Physical iPhone/Safari rendering, Liquid Glass appearance and screen-reader traversal were not exercised. Header verification was a CSS cascade check, not a rendered browser screenshot. No browser/desktop control was used.
