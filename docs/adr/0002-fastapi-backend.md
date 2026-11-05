# ADR 0002: FastAPI for the HTTP API

- Status: Accepted
- Date: 2026-11-06

## Context

The platform needs typed request validation, OpenAPI documentation, async-compatible endpoints, dependency injection, and a strong Python ecosystem for document and AI work.

## Decision

Use FastAPI with Pydantic v2. Keep route handlers thin and use application services for workflows. Use async I/O only where the underlying operations benefit from it.

## Consequences

The API contract and Python models integrate well, and testing is straightforward. Blocking document/AI work must not run in request handlers and belongs in workers.
