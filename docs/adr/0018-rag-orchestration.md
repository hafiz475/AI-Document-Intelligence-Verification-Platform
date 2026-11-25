# 0018: Queue RAG orchestration through the existing worker

## Status

Accepted

## Decision

Create a persisted QUEUED question and process retrieval, generation, citation
validation, and answer persistence in the existing Dramatiq worker. Reuse the M3
embedding provider and semantic search service.

## Consequences

API requests return HTTP 202 and the UI polls. Provider latency and retries do not hold
HTTP connections, and no second retrieval implementation or vector store is introduced.
