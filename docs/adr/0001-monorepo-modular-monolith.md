# ADR 0001: Monorepo with a modular monolith

- Status: Accepted
- Date: 2026-11-06

## Context

The web, API, and worker share one product lifecycle and need coordinated contracts, tooling, and documentation. Premature microservices would add deployment and consistency costs before team or scaling boundaries are known.

## Decision

Use a monorepo containing separately runnable `apps/web`, `apps/api`, and `apps/worker`. Keep business logic in an installable Python package used by both API and worker. Enforce internal domain/application/adapter boundaries while deploying a modular monolith.

## Consequences

Atomic changes and local setup are simpler. CI can target each application. Internal boundaries require review discipline, and independently versioning components would require a later decision.
