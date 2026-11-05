# ADR 0004: Dramatiq with Redis for background jobs

- Status: Accepted
- Date: 2026-11-06

## Context

Parsing, chunking, embedding, and extraction are too slow and failure-prone for request handlers. The project needs retries and independently scalable workers without adopting a large workflow platform.

## Decision

Use Dramatiq with Redis as broker. Actors receive identifiers, not document bodies; services load authoritative state from PostgreSQL. Jobs are idempotent and persist explicit status transitions and errors.

## Consequences

Dramatiq is smaller than Celery and supports the required broker/retry model. Complex DAGs, scheduled workflows, or extensive operational tooling may require reassessment. Redis and workers become required runtime dependencies once jobs ship.
