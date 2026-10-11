# Build 20261011.11 — request card alignment and lifecycle labels

Based on Harmonia 3.0 Beta 7 and compact-card build 20261011.10.

Changes:
- Add web/src/FittedTitle.tsx to measure titles at 18, 17 and 16 px equivalents before two-line truncation. Refit after resizing and font loading, retain full accessible text and hover title, and use relative units for text scaling.
- Update DiscoverShelves.tsx and release.css for fitted titles, equal-height grid cards and aligned title/artist/requester rows.
- Update AlbumCover.tsx and LidarrRequests.tsx to share lifecycle labels: Awaiting approval, Queued, Searching, Waiting for download, Downloading, Importing, Waiting for Plex, Partially available, Available, Needs attention and Cancelled. Imported albums require Plex confirmation before becoming Available. Genuine failures remain actionable.
- Update .github/workflows/security.yml to pinned checkout v6.1.0 (Node.js 24), retaining persist-credentials: false.
- Extend tests/test_recent_requests.cjs with lifecycle labels and title-fitting/resize regressions.
- Increment source/Docker build metadata and update README, CHANGELOG and FIX-TRACKER.

Validation: all 14 frontend regression scripts and TypeScript/Vite production build passed. Existing frontend bundle-size warning remains. The 702 backend tests also passed after updating Beta 8 release metadata. Backend logic is unchanged. Physical-device layout and deployed request lifecycle behavior remain unverified.

Prepared for the authorized Docker and GitHub Beta 8 publication. Publication results are recorded in the GitHub release. The checkout update takes effect for GitHub Actions after this workflow is pushed to the repository; it does not change prior run warnings.

Release metadata is updated to 3.0.0-beta8. Remove the previously tracked local web/node_modules symlink from the GitHub source; dependencies remain installed locally and excluded from packaging.
