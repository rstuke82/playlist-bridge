Harmonia 3.0 Beta 7 brings together the validated beta fixes, web-only runtime migration, security hardening and UI improvements from source build 20261011.9.

Changes include:
- Redesigned homepage recent-request cards with artwork on the right and album, requester and status on the left.
- Corrected request progress: continuing searches remain in progress; genuine failures require attention. Request artwork is preserved.
- Requests pagination with 5, 10, 25, 50 and 100 results per section, default 25.
- Duration-aware playlist matching, artist/song search improvements and import recovery fixes.
- Authentication, account isolation, proxy/header protections, credential-safe redirects, job/request quotas and a non-root Docker runtime.
- Removal of CLI support and migration out of legacy.py, with the sync engine retained.
- HARMONIA_* environment variables throughout, without legacy aliases.

Upgrade requirements:
- Rename PLAYLIST_BRIDGE_* configuration entries to HARMONIA_* before recreating the container. TZ is unchanged.
- Back up application data and give its dedicated data directory ownership to UID/GID 10001. Do not change ownership of the music library. Existing database filenames and data mappings are retained.
- Consult SECURITY-DEPLOYMENT.md for HTTPS/proxy settings and restricted public access.

Validation: 702 backend tests, 14 frontend regression scripts and the TypeScript/Vite production build passed. Live Plex/Lidarr deployment and physical-device rendering remain unverified.

Known limitations: the frontend bundle-size warning remains. The previously reported zlib CVE-2026-85091 remains unresolved in the pinned runtime base; see SECURITY-HARDENING-CHANGES.md. This prerelease does not certify an advisory-free deployment. The security workflow builds test images and scans them; it does not publish images.

This is a GitHub source prerelease. No Docker images are published by this release operation.
