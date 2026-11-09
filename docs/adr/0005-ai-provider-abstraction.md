# ADR 0005: Provider-independent AI interfaces

- Status: Accepted
- Date: 2026-11-06

## Context

OpenAI is the initial intended provider, but models, structured-output capabilities, embeddings, pricing, and availability change. Domain behavior must also remain testable without network calls.

## Decision

Define a typed, capability-specific protocol for structured extraction. Put vendor SDKs
in adapters selected by backend configuration. Validate outputs against domain-owned
schemas and record provider/model/prompt metadata. Offline tests and the public demo use
an explicitly named deterministic development adapter, never fake production responses.

Milestone 2 implements an OpenAI Responses API adapter with structured outputs and an
offline deterministic development adapter. Embedding interfaces remain deferred until
the retrieval milestone.

## Consequences

Provider changes and deterministic tests are easier, and vendor objects do not leak through the application. The abstraction must stay capability-oriented; pretending all providers are identical would hide meaningful differences.
