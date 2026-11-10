# ADR 0017: Deterministic retrieval-only evaluation

- Status: Accepted
- Date: 2026-11-10

## Context

Retrieval quality must be measured before RAG, without an LLM judge or fabricated
answers.

## Decision

Evaluate stored ranked results against explicit relevant chunk IDs. Persist per-case
retrieved IDs, first relevant rank, hit, recall, and reciprocal rank; aggregate Hit@K,
Recall@K, and mean reciprocal rank.

## Consequences

Metrics are reproducible and auditable. The checked-in synthetic dataset uses content
selectors that deployment tooling resolves to generated chunk IDs after ingestion.
This is intentionally narrower than the planned full evaluation framework.
