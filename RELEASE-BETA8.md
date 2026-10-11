Harmonia 3.0 Beta 8 — build 20261011.11

- Compact homepage request cards with aligned heights and title/artist/requester rows.
- Long titles try 18, 17 and 16 px equivalents before two-line truncation, retaining full accessible and hover text.
- Consistent lifecycle labels on homepage and Requests. Plex-confirmed albums show Available; imported albums awaiting Plex show Waiting for Plex. Actual failures remain Needs attention.
- Pinned checkout v6.1.0 uses Node.js 24, addressing the deprecated checkout runtime warning in future Actions runs.
- Remove a local dependency-folder symlink from GitHub source tracking.

Validation: 702 backend tests, 14 frontend regression scripts and TypeScript/Vite production build passed. Physical-device layout and live Plex/Lidarr behavior remain unverified. Existing frontend bundle-size warning and previously documented zlib advisory remain; see SECURITY-HARDENING-CHANGES.md. No advisories are suppressed.

Docker: ghcr.io/rstuke82/playlist-bridge:build-20261011.11 and :beta, for linux/amd64 and linux/arm64.

For upgrades from older betas, use HARMONIA_* environment names and a dedicated writable data volume owned by UID/GID 10001. See README.md and SECURITY-DEPLOYMENT.md.
