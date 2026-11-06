# AssureAI architecture

## Current system

AssureAI remains a modular monolith with separately runnable web, API, and worker
processes. Milestone 1 adds the document-ingestion application and persistence modules
without introducing AI, retrieval, or embedding behavior.

~~~mermaid
flowchart TB
    Reviewer --> Web[React / TypeScript]
    Web -->|Project and document HTTP API| API[FastAPI]
    API --> DB[(PostgreSQL)]
    API --> Queue[(Redis broker)]
    API --> Files[(Private document storage)]
    Queue --> Worker[Dramatiq worker]
    Worker --> Files
    Worker --> DB
~~~

PostgreSQL still uses the pgvector image because later milestones plan vector retrieval,
but Milestone 1 creates no vector columns and performs no similarity search.

## Module boundaries

- apps/web: typed API clients, TanStack Query hooks, reusable states, and project/document
  screens.
- apps/api: HTTP routes, application services, SQLAlchemy models, Alembic migrations,
  extraction, chunking, storage protocol, and queue actor.
- apps/worker: the Dramatiq discovery entry point; processing logic stays in the shared
  API application package.
- docs/adr: durable decisions and tradeoffs.
- sample-data: synthetic, non-sensitive demonstration inputs.

The dependency direction is:

    HTTP routes / Dramatiq actor
                |
        application services
                |
      models and storage protocol
                ^
    SQLAlchemy / local storage adapters

HTTP handlers validate transport concerns and map domain errors. Services own
transactions and workflow orchestration. The worker does not duplicate extraction logic.

## Ingestion flow

1. The API verifies the project exists.
2. It reads at most the configured limit plus one byte.
3. Validation checks the display filename, allowed extension, declared MIME type, and
   PDF signature, DOCX container structure, or UTF-8 TXT content.
4. SHA-256 is computed and checked within the project.
5. A generated storage key and UPLOADED metadata row are created.
6. The private file is saved, status becomes QUEUED, and the transaction commits.
7. A Dramatiq message is sent to Redis and HTTP 202 is returned.
8. The worker sets PROCESSING and extracts normalized segments.
9. Existing chunks are deleted and deterministic replacements are inserted in one
   transaction.
10. Metadata and READY are committed. Any exception instead commits FAILED with a safe
    error message and remains visible to Dramatiq retry handling.

## Persistence

The Milestone 1 migration creates:

- projects
- documents
- document_chunks
- the document_status enum

Documents have a foreign key to projects with ON DELETE CASCADE. Chunks have a foreign
key to documents with ON DELETE CASCADE. Project ownership therefore controls the full
ingestion aggregate. This behavior is intentional: deleting a project in a future API
must explicitly confirm removal of metadata and chunks, and the application must also
delete associated stored objects.

The unique constraints on project/content hash and document/chunk index enforce
deduplication and retry idempotency at the database boundary.

## Project isolation

Document detail and chunk requests query by project_id and document_id together. A valid
document identifier presented through another project returns 404. Duplicate checks are
also project-scoped. Storage keys never cross the HTTP boundary.

Authentication and user ownership are deferred, so Milestone 1 isolation protects
project boundaries within the current unauthenticated application but is not a complete
multi-tenant authorization system.

## Text preparation

PDF extraction retains one-based page numbers. DOCX extraction retains paragraph order
and section labels. TXT uses UTF-8 with optional BOM. Normalization standardizes line
endings, removes control noise, collapses horizontal whitespace, and preserves paragraph
breaks.

Chunks target 1,000 characters and respect paragraph boundaries. PDF pages do not mix.
A 150-character overlap is applied only when splitting one oversized paragraph. This is
deterministic preparation, not embedding-aware chunking.

## Reliability and operations

- /health reports only process liveness.
- /ready checks the database and Redis when configured.
- API startup applies Alembic migrations in the container.
- API and worker share a named local-storage volume.
- JSON lifecycle logs contain project/document identifiers but not extracted content.
- Chunk replacement is transactional and safe to repeat.
- Queue submission failure is recorded as FAILED and returned as service unavailable.

Local filesystem storage is suitable for Compose and a single host. A production
multi-host deployment requires an object-storage adapter, managed secrets, TLS,
backups, monitoring, and an explicit migration job.

## Deferred work

No authentication, embeddings, vector search, LLM extraction, RAG, chat, citations,
verification, prompt engineering, or evaluation exists in Milestone 1.

## Decisions

See [docs/adr](docs/adr), especially:

- ADR 0004: Dramatiq with Redis
- ADR 0006: document storage abstraction
- ADR 0007: project-scoped content deduplication
- ADR 0008: deterministic document chunking
