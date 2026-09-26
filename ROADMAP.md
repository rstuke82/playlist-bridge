# Roadmap

Future work only. Shipped changes and upgrade notes are in CHANGELOG.md and BUILD-NOTES.md.

- Expand Last.fm review beyond top albums to track history and collections, retaining import origins and existing recording-version/manual-match safeguards.
- Add reviewed manual album associations and stronger release identifiers to Plex/Lidarr reconciliation. Distinguish editions without relying on artist/album names and counts alone.
- Improve library diagnostics for partial imports, stale inventories and source metadata differences.
- Further optimize candidate indexing and reuse validated matches for unchanged tracks, while preserving source changes, ordering, duplicates and matching safeguards. Measure against real large libraries.
- Strengthen source completeness detection so audit history can safely distinguish a genuinely empty playlist from a partial provider response.
- Expand artist identity/alias and contributor metadata so blocked artists remain excluded when upstream services provide incomplete collaboration credits.
- Explore administrator-only duplicate-file review and optional FLAC-to-AAC conversion, with explicit review before changing music files.
