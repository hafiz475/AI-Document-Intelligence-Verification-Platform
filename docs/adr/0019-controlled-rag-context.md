# 0019: Render deterministic controlled evidence context

## Status

Accepted

## Decision

Render ranked evidence as explicit SOURCE, CHUNK_ID, DOCUMENT, PAGE, SIMILARITY, and
TEXT fields in stable rank order. Persist the exact retrieval set before generation.

## Consequences

Prompts are reproducible and debuggable. Object representations cannot accidentally
alter context. Context size is bounded by top-k 1-10.
