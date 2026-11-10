# ADR 0015: Cosine similarity for semantic retrieval

- Status: Accepted
- Date: 2026-11-10

## Context

The API must define its ranking number precisely and use the same metric in production
and deterministic tests.

## Decision

Rank compatible embeddings by pgvector cosine distance and return
cosine_similarity = 1 - cosine_distance. Development and SQLite tests calculate the
equivalent normalized dot product. Results are ordered by descending similarity.

## Consequences

Scores range from -1 to 1 and are never mislabeled as distance. Provider, model, and
dimensions are filtered before comparison.
