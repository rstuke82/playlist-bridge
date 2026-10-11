GitHub source release identity: Harmonia 3.0 Beta 7 (`v3.0.0-beta7`), build 20261011.9.

# Unpublished Requests pagination and risk hardening

Based on published build 20261011.6 in harmonia-r01-r04; retains its R01/R04 implementation. Release metadata was subsequently incremented to 20261011.9 in the prepared release directory. Publication remains pending.

## Requests

Each expanded status section now paginates with a bottom footer: Showing start to end of total results; Display 5, 10, 25, 50 or 100 results per page (default 25); Previous and Next controls. Page size changes reset the page, deep-linked albums remain reachable, page boundaries clamp when results shrink and Completed stays collapsed by default. Footer stacks on narrow screens.

## Security changes

R02 runs the image as UID/GID 10001 and hardens Compose capabilities, filesystem and resource bounds. R03 separates intentional Plex LAN access from pinned public HTTPS artwork connections, validates redirects and refuses credentialed service redirects. R05 gives new/imported members approval-first requests, preserves explicit saved policies and caps atomic pending approvals/jobs with HTTP 429 recovery. R06 locks the tested Python runtime, follows requirements includes during startup, pins frontend/runtime/scanner images, moves runtime to Debian Trixie, removes pip after installation and prepares native architecture image scanning in CI.

## Exact changed files relative to published 20261011.6

- playlist_bridge/browser_security.py (new), playlist_bridge/api.py, playlist_bridge/accounts.py: R01/R04 HTTPS/proxy/cookie/header policy; localhost health probe compatibility; approval defaults.
- Dockerfile, .dockerignore, docker-compose.yml, .env.example: image user, pinned bases/lock, removed runtime installer and Compose hardening/settings.
- playlist_bridge/redirect_policy.py (new), playlist_bridge/image_download.py, playlist_bridge/artwork_sync.py, playlist_bridge/plex_client.py, playlist_bridge/network.py: public-address pinning/TLS/redirect policy and credentialed service protection.
- playlist_bridge/discover.py, playlist_bridge/import_users.py, playlist_bridge/jobs.py: member approval defaults and atomic queue admission.
- playlist_bridge/bootstrap.py, requirements.txt, requirements.in (new), requirements.lock (new): resolved runtime installation and startup dependency validation.
- .github/workflows/security.yml (new): immutable checkout/scanner, native AMD64/ARM64 builds, regressions and actual OS/Python image scanning; fails on critical/high findings.
- web/src/Discover.tsx: permission summary/editor reflects approval-first defaults.
- web/src/LidarrRequests.tsx, web/src/requestSections.ts, web/src/release.css: pagination options/range/navigation and responsive footer.
- tests/test_browser_security.py (new), tests/test_remaining_risks.py (new): 19 security/queue/lock/health regressions.
- tests/test_request_history_performance.cjs: page size controls and active-section pagination assertions.
- tests/test_30.py: existing server-default request test explicitly enables automatic approval.
- tests/test_build_20261007_14.py, tests/test_build_20261008_14.py: image streaming/status fixtures and fully mocked external transport boundary.
- scripts/package_source.py: allowlist includes lock/input, new deployment guide/report and CI workflow.
- README.md, FIX-TRACKER.md, SECURITY-DEPLOYMENT.md (new), R01-R04-CHANGES.md (new), this report: current implementation and deployment status.

## Validation and unresolved advisory

697 backend tests passed locally with locked dependencies and inside the hardened Python 3.12 ARM64 container. All 13 frontend regression scripts passed; production frontend and AMD64/ARM64 container builds passed. Non-root startup and private data writes succeeded with a read-only root filesystem, no capabilities, no-new-privileges and resource limits. Actual pinned HTTPS transport fetched Apple's public favicon with HTTP 200. The existing frontend bundle warning remains.

Final local image index: sha256:ab066837f95aabaae9e7731e8008210eb15e00e3535f4988306f8c06ff75b69e. Both platform images were scanned with Docker Scout 1.25.0. Each reports 0 critical, 1 high, 1 medium and 26 low findings. Removing the unnecessary runtime pip eliminated its advisory findings; changing the base eliminated the earlier critical GnuTLS findings.

The high finding is CVE-2026-85091 in zlib 1:1.3.dfsg+really1.3.1-1. Debian currently marks this distribution package unfixed: https://security-tracker.debian.org/tracker/CVE-2026-85091 . The stated upstream affected range and older Debian package version need further vendor assessment; no finding was suppressed and no remote exploitability in Harmonia is asserted. The CI gate will fail while a high finding remains. R06 advisory remediation therefore remains open, even though locking/scanning controls are implemented. Full reports remain in verification/source-cves-amd64.md and source-cves-arm64.md, excluded from source packaging.

No image publication, production deployment, live proxy/firewall/cookie verification, data ownership change or physical-device verification was performed. Prepare existing data ownership before deploying the UID 10001 image. CI is prepared locally; repository installation and hosted CI execution remain unverified.
