# ADR 0013: Provider-neutral embedding interface

- Status: Accepted
- Date: 2026-11-10

## Context

Retrieval must work offline in tests and demos while supporting a real embedding API
without leaking vendor SDK types into application services.

## Decision

Define an EmbeddingProvider protocol with batched embed_texts and embed_query methods.
Results contain vectors plus provider, model, dimensions, latency, and optional token
metadata. Implement a deterministic hashing provider for development/tests and an
OpenAI embeddings adapter for production configuration.

## Consequences

Tests require no credential and provider changes stay behind one boundary. The
deterministic provider is explicitly not a production-quality semantic model. OpenAI
credentials remain backend-only.
