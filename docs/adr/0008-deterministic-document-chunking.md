# ADR 0008: Deterministic paragraph-aware document chunking

- Status: Accepted
- Date: 2026-11-06

## Context

Milestone 1 needs reviewable text units without introducing embedding-specific or
model-specific tokenization.

## Decision

Normalized paragraphs are packed toward 1,000 characters. Separate PDF pages are never
combined. A 150-character overlap is used only when a single paragraph itself exceeds
the target and must be split. Chunk indexes are zero-based and deterministic. Page,
section, and source-section metadata are retained.

Retries delete existing chunks and insert replacements in the same transaction.

## Consequences

Chunks are understandable and reproducible without an AI dependency. Later retrieval
evaluation may justify a new versioned chunking strategy rather than silently changing
the stored meaning of existing chunks.
