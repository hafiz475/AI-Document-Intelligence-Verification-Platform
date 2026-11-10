# ADR 0016: Transactional active-vector replacement

- Status: Accepted
- Date: 2026-11-10

## Context

Model, provider, dimensions, embedding version, or chunk content can change. Mixed
vectors must never be compared silently, and failed re-embedding must not destroy the
last complete set.

## Decision

Each explicit embedding run records its configuration. The worker embeds every chunk
in batches before replacing active vectors in one transaction. A completed retry is a
no-op. A changed configuration creates a new run and replaces the document's active
vectors only after all batches validate.

## Consequences

Search either finds a fully compatible active set or returns a controlled conflict.
EmbeddingRun history is retained, while historical vectors are not retained.
