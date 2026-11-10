# ADR 0014: Dedicated active chunk embeddings in pgvector

- Status: Accepted
- Date: 2026-11-10

## Context

Embedding metadata and vector compatibility must be explicit without changing the
Milestone 1 chunk model.

## Decision

Store one active DocumentChunkEmbedding per chunk in PostgreSQL pgvector. Persist
project, document, provider, model, dimensions, embedding version, and content hash.
EmbeddingRun retains historical execution metadata. Enable the vector extension safely
in Alembic.

Use exact search for the demo dataset. Do not add HNSW or IVFFlat until measured volume
justifies index build time, memory, and approximate-result tradeoffs.

## Consequences

Project filters and vectors share one transactional database. A unique chunk constraint
prevents duplicate active vectors. Large datasets may later require a cosine HNSW index
and a new measured decision.
