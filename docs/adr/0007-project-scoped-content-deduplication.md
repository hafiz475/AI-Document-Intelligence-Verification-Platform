# ADR 0007: Project-scoped SHA-256 duplicate protection

- Status: Accepted
- Date: 2026-11-06

## Context

Renaming a file must not trigger duplicate extraction, while identical reference files
may legitimately exist in separate projects.

## Decision

The API computes SHA-256 from validated bytes and enforces a database uniqueness
constraint on (project_id, sha256_hash). A duplicate upload returns HTTP 409 with the
existing document identifier. Filename is not part of duplicate identity.

## Consequences

Concurrent uploads are protected by the database as well as the preflight lookup.
SHA-256 collision risk is negligible for this use. Cross-project data remains isolated
and is not disclosed during duplicate checks.
