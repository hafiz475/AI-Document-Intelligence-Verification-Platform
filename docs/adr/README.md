# Architecture decision records

ADRs capture decisions that are costly or confusing to rediscover. Use sequential four-digit identifiers, include context and tradeoffs, and do not rewrite an accepted decision to hide history; supersede it with a new ADR.

- [0001: Monorepo modular monolith](0001-monorepo-modular-monolith.md)
- [0002: FastAPI backend](0002-fastapi-backend.md)
- [0003: PostgreSQL and pgvector](0003-postgresql-pgvector.md)
- [0004: Dramatiq background jobs](0004-dramatiq-background-jobs.md)
- [0005: AI provider abstraction](0005-ai-provider-abstraction.md)
- [0006: Document storage abstraction](0006-document-storage-abstraction.md)
- [0007: Project-scoped content deduplication](0007-project-scoped-content-deduplication.md)
- [0008: Deterministic document chunking](0008-deterministic-document-chunking.md)
- [0009: Structured inspection extraction schema](0009-structured-inspection-extraction-schema.md)
- [0010: Immutable prompt versioning](0010-immutable-prompt-versioning.md)
- [0011: Controlled chunk evidence validation](0011-controlled-chunk-evidence-validation.md)
- [0012: Preserve original values during human review](0012-preserve-original-human-review.md)
- [0013: Provider-neutral embedding interface](0013-embedding-provider-abstraction.md)
- [0014: Dedicated active chunk embeddings in pgvector](0014-pgvector-chunk-embedding-storage.md)
- [0015: Cosine similarity for semantic retrieval](0015-cosine-similarity-retrieval.md)
- [0016: Transactional active-vector replacement](0016-transactional-reembedding.md)
- [0017: Deterministic retrieval-only evaluation](0017-retrieval-evaluation-metrics.md)
