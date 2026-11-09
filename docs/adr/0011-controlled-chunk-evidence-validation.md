# ADR 0011: Controlled chunk evidence validation

- Status: Accepted
- Date: 2026-11-07

## Context

Models can fabricate citations, page numbers, quotes, and identifiers. A structured
response alone does not make evidence trustworthy.

## Decision

The provider receives controlled blocks containing CHUNK_ID, PAGE, and TEXT. It may
return only chunk IDs and quotes; it never returns authoritative page numbers. After
schema validation, the backend verifies that each chunk exists in the current document,
its stored page metadata is valid, and the whitespace/case-normalized quote occurs in
the stored chunk.

Pages are copied from validated chunk metadata. Invalid references are discarded and
the field is marked UNSUPPORTED or PARTIALLY_SUPPORTED. They are never silently stored
as evidence.

## Consequences

Evidence is traceable and project/document boundaries are enforced after every provider
call. Paraphrased evidence is rejected in Milestone 2; more sophisticated matching must
be introduced only with explicit tests and thresholds.
