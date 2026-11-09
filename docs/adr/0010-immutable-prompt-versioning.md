# ADR 0010: Immutable prompt versions

- Status: Accepted
- Date: 2026-11-07

## Context

Extraction results are not reproducible or auditable unless the exact instructions used
for each run are retained.

## Decision

Prompt templates and prompt versions are separate records. Versions have a unique
template/version number and are never updated through application services or HTTP
endpoints. Each extraction run references one prompt-version row by foreign key.

Milestone 2 seeds Inspection Extraction Prompt version 1 in the migration and preserves
its schema version with every historical run.

## Consequences

Prompt improvements create new rows. Historical runs remain tied to their original
instructions, at the cost of retaining prompt text indefinitely.
