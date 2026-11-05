# Engineering instructions

These rules apply throughout the repository.

## Product integrity

- Do not invent performance, accuracy, usage, or business metrics.
- Do not claim that DNV or any other organization uses AssureAI.
- Use only synthetic or appropriately licensed public sample documents.
- Never fabricate AI responses, citations, evidence, job completion, or provider availability.
- Clearly label deterministic development providers and planned features.

## Architecture

- Keep HTTP handlers thin; put orchestration in services and persistence in repositories.
- Keep domain code independent from AI vendor SDKs and web frameworks where practical.
- Validate all structured AI output before it becomes trusted application data.
- Carry project scope through persistence, retrieval, jobs, and authorization boundaries.
- Record significant decisions in `docs/adr/`.
- Prefer the smallest maintainable implementation; do not add speculative abstractions.

## Backend

- Support Python 3.12 or newer and use type hints.
- Use Pydantic v2, SQLAlchemy 2-style APIs, explicit transactions, and Alembic migrations.
- Use domain-specific exceptions and map them to appropriate HTTP status codes.
- Keep secrets and provider credentials on the backend only.
- Add tests for behavior, error paths, authorization boundaries, and bug fixes.
- Run Ruff, mypy, and pytest for backend changes.

## Frontend

- Keep TypeScript strict and do not introduce `any`.
- Use reusable accessible components and semantic HTML.
- Isolate HTTP calls in an API client layer and remote-state behavior in query hooks.
- Always implement loading, error, empty, and success states where applicable.
- Run ESLint, TypeScript checking, Vitest, and the production build for frontend changes.

## Security and operations

- Never commit secrets, uploaded customer documents, or local `.env` files.
- Validate file type, size, name, and content; prevent path traversal.
- Do not allow retrieval across project boundaries.
- Use structured logs and propagate request/correlation identifiers.
- Keep health checks lightweight; readiness should verify required dependencies as they are introduced.

## Working agreement

- Keep changes scoped and preserve unrelated work.
- Update documentation when behavior, setup, or architecture changes.
- Do not commit or push automatically.
- A milestone is complete only when its tests, linters, type checks, builds, and relevant infrastructure validation pass or blockers are documented.
