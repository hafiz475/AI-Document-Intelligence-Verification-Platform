# ADR 0003: PostgreSQL with pgvector

- Status: Accepted
- Date: 2026-11-06

## Context

AssureAI needs transactional project/document metadata and, later, vector similarity search with strict project filters. Operating separate primary and vector databases would create synchronization and authorization risk at the initial scale.

## Decision

Use PostgreSQL as the system of record and pgvector for embeddings. Access it through SQLAlchemy 2 and version schemas with Alembic. Retrieval queries must apply tenant/project filters in SQL.

## Consequences

Metadata and vectors share transactions and backup/authorization controls. Very large retrieval workloads may eventually justify a specialized store, which must be supported by measured need and a new ADR.
