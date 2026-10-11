# Combined remaining fixes — build 20261010.11

Based on build 20261010.10. Release build 20261010.11; registry publication is recorded in verification/publish-20261010.11.txt.

- F03: users without playlist editing permission cannot restore ignored tracks; read-only track details and preview remain accessible.
- F06: member request availability is evaluated against their own Plex inventory. Request failures and finalization errors remain visible with credentials redacted; other requesters and playlist sources remain private.
- F15: POSIX data directories use mode 0700, credential-bearing database/config/migration files use 0600, including WAL/SHM. Existing modes are repaired. Windows requires administrator-managed ACLs; mounted volumes must permit ownership/mode changes.
- F16: the Lidarr webhook enforces its 1 MiB limit on actual streamed bytes, independent of Content-Length. Album/artist objects and IDs are validated before processing.
- F17: retain the entire regression suite; add a secret-free environment example and an explicit source packaging manifest. Historical build claims are separated from current documentation. Repository ownership, asset/license provenance and actual deployment remain release-owner checks.
- F21: Verify Duplicates hashes only same-album/same-size candidates in the latest saved local scan. It does not walk the library or write tags. Missing, stale, changed or unsafe candidates require a fresh scan.
- F25: long MusicBrainz searches run as cancellable background jobs in a dedicated worker lane; the UI polls short requests and shows partial results. Identical submissions coalesce and release-page lookups reuse cache.
- F26: artist/song lookup supports additional recording pages, merges album candidates and removes the 50-album truncation. Editing search fields clears pagination from the previous query; fields remain disabled while the active search completes or cancels.
- F27: polling-only timestamps and job progress do not invalidate prepared Requests views. Status, failure, result and availability changes still invalidate them. Request sorting uses meaningful modification time.

- F29: the installed urllib3 2.7.0 matched three security advisories (proxy TLS configuration, deflate streaming loop, unbounded chunk-size buffering). Requirements now enforce urllib3 >=2.8.0; the validation environment uses 2.8.0. The separate missing packaging development-tool dependency was repaired in the workspace environment, without adding it to application requirements.

## Validation

634 backend tests passed in the final combined run. TypeScript/Vite production build passed with the existing bundle-size warning. All seven frontend regression scripts passed. Npm live audit reports zero vulnerabilities. OSV reports no advisories for 16 checked installed application dependencies; this is not an exhaustive resolved Docker dependency scan. Pip consistency check passes. Syntax checks cover 145 Python files. Source packaging includes all 67 Python test files, excludes runtime databases/logs/backups, verifies ZIP integrity and contains no matches for the checked high-confidence secret signatures.

The initial combined test run found an older request fixture needing the new provider parameter; that fixture and the prior retry fixture were corrected. A final full run also validates the updated urllib3 dependency. Nineteen backend tests were added relative to published .10 (seven background-search tests and twelve remaining-fix tests); one frontend polling regression script was added. These checks preceded the release version update to 20261010.11.

Exact changed files: verification/changed-files-combined.txt. Full results: verification/backend-combined.txt, frontend-combined.txt, frontend-regressions-combined.txt, npm-audit-combined.json, python-advisories-combined.json and static-combined.json.

Live Plex/Lidarr, mobile Safari, reverse-proxy behavior, Windows ACLs and both Docker architectures have not been verified by local tests.
