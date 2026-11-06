# AssureAI

AssureAI is a document intelligence foundation for traceable technical-assurance
workflows. Milestone 1 implements reliable, project-isolated document ingestion and
deterministic text preparation. It does not call an AI provider.

> **Status:** Milestone 1 document ingestion is implemented. Embeddings, vector
> retrieval, structured LLM extraction, RAG, citations, verification, chat, and
> evaluation remain planned.

## Implemented

- Create, list, and inspect isolated projects.
- Upload PDF, DOCX, and UTF-8 TXT documents up to a configurable size.
- Validate extension, declared MIME type, and basic file structure/signature.
- Store files under private generated keys through a storage abstraction.
- Protect against duplicate content within a project using SHA-256 and a database
  uniqueness constraint; duplicates return HTTP 409.
- Queue extraction through Redis and Dramatiq.
- Extract PDF text by page, DOCX text by ordered paragraph, and TXT text as UTF-8.
- Normalize and deterministically chunk text while retaining page/section provenance.
- Persist UPLOADED, QUEUED, PROCESSING, READY, and FAILED states.
- Poll active processing from the React interface and display chunks or safe errors.
- Scope every document and chunk lookup by both project and document identifier.
- Apply PostgreSQL schema changes with Alembic.

## Planned, not implemented

- Embeddings and pgvector similarity retrieval
- Structured LLM extraction and prompt management
- Evidence-backed RAG, chat, and citations
- Human verification workflows and rules
- Evaluation datasets and run tracking
- Authentication and multi-user authorization
- Production object storage

## Architecture

~~~mermaid
flowchart LR
    U[Reviewer] --> W[React web app]
    W --> A[FastAPI API]
    A --> P[(PostgreSQL)]
    A --> R[(Redis)]
    R --> J[Dramatiq worker]
    A --> S[(Private document storage)]
    J --> S
    J --> P
~~~

See [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/adr](docs/adr).

## Run with Docker Compose

Requirements: Docker Desktop with Compose.

1. Copy .env.example to .env. The defaults are for local development only.
2. Start the stack:

       docker compose up --build

3. Open:

   - Web: <http://localhost:5173>
   - API documentation: <http://localhost:8000/docs>
   - Liveness: <http://localhost:8000/health>
   - Dependency readiness: <http://localhost:8000/ready>

The API applies Alembic migrations before starting. PostgreSQL, Redis, and uploaded
documents use named volumes. API and worker share the private document volume.

To exercise the vertical slice, create “Wind Farm Alpha” and upload a file from
[sample-data](sample-data). The included data is synthetic.

## Run without Docker

Use Python 3.12+ and Node 22.

API:

    cd apps/api
    python -m venv .venv
    # Activate the environment for your shell.
    python -m pip install -e ".[dev]"
    # Set ASSUREAI_DATABASE_URL and ASSUREAI_REDIS_URL.
    alembic upgrade head
    uvicorn assureai_api.main:app --reload

Worker:

    # From the repository root with the API environment active:
    set PYTHONPATH=apps/api/src;apps/worker/src
    dramatiq assureai_worker.tasks

Web:

    cd apps/web
    npm ci
    npm run dev

## API behavior

Project endpoints:

- POST /api/v1/projects
- GET /api/v1/projects
- GET /api/v1/projects/{project_id}

Document endpoints:

- POST /api/v1/projects/{project_id}/documents
- GET /api/v1/projects/{project_id}/documents
- GET /api/v1/projects/{project_id}/documents/{document_id}
- GET /api/v1/projects/{project_id}/documents/{document_id}/chunks

The upload endpoint accepts multipart/form-data and returns HTTP 202 after durable
metadata/file storage and successful queue submission. The same SHA-256 content in the
same project returns HTTP 409 and identifies the existing document. Storage keys and
host paths are never returned.

## Processing and chunking

The worker sets PROCESSING, parses and normalizes text, replaces existing chunks in one
transaction, and then sets READY. Failures set FAILED with a safe message and are logged
without document contents. This replacement strategy makes retries idempotent.

Paragraphs are packed toward 1,000 characters. Separate PDF pages are never combined.
Only a single oversized paragraph is split with approximately 150 characters of
overlap. See [ADR 0008](docs/adr/0008-deterministic-document-chunking.md).

## Quality checks

Backend, from apps/api:

    ruff check .
    ruff format --check .
    mypy src tests
    pytest

Frontend, from apps/web:

    npm run format:check
    npm run lint
    npm run typecheck
    npm test -- --run
    npm run build

Infrastructure:

    docker compose config --quiet
    docker compose build

## Security and limitations

Files are checked using bounded reads, allowed extensions, declared types, signatures or
container structure, and UTF-8 decoding. Original filenames are display metadata only.
Project scope is carried through document and chunk queries. Uploaded contents and
secrets are ignored by version control and are never logged.

Milestone 1 has no authentication, malware scanning, OCR, encrypted object storage, or
distributed storage adapter. Image-only PDFs fail cleanly when no extractable text is
found. Local filesystem storage is intended for development and single-host operation.

## License

MIT. See [LICENSE](LICENSE).
