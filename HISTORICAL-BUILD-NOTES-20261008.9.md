# Harmonia · Build 20261008.9

Mirror searches make one attempt.

- Stop automatic retry loops for queries routed to a configured MusicBrainz mirror with the required indexed-search capability. This applies to both initial album discovery and subsequent/manual searches.
- Retain the existing public fallback on an empty/failed mirror response, but do not repeat that mirror-and-fallback sequence automatically.
- Queries routed directly to public MusicBrainz retain the configured retries. An untested/lookup-only mirror does not claim to handle indexed searches.
- Show Searching MusicBrainz mirror without misleading multi-attempt progress. Label retry preferences as Public service automatic retries.
- Includes all startup and listening-history fixes from builds .7 and .8.

## Validation

Frontend behavior checks passed: one request after retryable mirror failure, no retry delay, correct routing per search entity/capability, public retry retention, and existing history/startup/navigation checks. TypeScript and Vite production build passed. All 26 focused backend routing/history regression tests passed. Backend behavior is unchanged except build metadata; existing bundle-size warning remains. No deployment or live service mutations.
