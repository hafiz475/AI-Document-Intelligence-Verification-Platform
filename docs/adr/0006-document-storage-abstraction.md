# ADR 0006: Local document storage behind an abstraction

- Status: Accepted
- Date: 2026-11-06

## Context

Milestone 1 needs durable private uploads in local Compose while future deployments may
use S3, R2, or Azure Blob Storage. Original filenames are untrusted and must never become
host paths or API-visible storage locations.

## Decision

Application services depend on a DocumentStorage protocol with save, open, delete, and
exists operations. The first adapter writes generated UUID keys to a private mounted
directory. API and worker containers share a named volume. Original filenames are stored
only as bounded display metadata.

## Consequences

Local files survive container restarts and storage paths stay private. A production object
storage adapter can replace the local adapter, but distributed production deployments
must not use a single-host filesystem.
