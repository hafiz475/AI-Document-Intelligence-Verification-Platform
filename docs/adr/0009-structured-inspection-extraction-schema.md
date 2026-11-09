# ADR 0009: Pydantic-owned structured inspection extraction

- Status: Accepted
- Date: 2026-11-07

## Context

Engineering reports contain recurring facts but provider JSON cannot be persisted as
trusted application data. Missing facts also need an explicit representation.

## Decision

Pydantic v2 models define twelve versioned inspection fields. Every field carries a
value or explicit missing reason plus zero or more chunk evidence references. Unknown
keys are forbidden. Provider output is parsed and validated against this schema before
any extracted field is persisted.

Scalar and list fields remain distinct. The persistence model records raw and normalized
values separately so future normalization changes cannot rewrite the provider output.

## Consequences

Malformed or partial provider JSON fails the whole extraction run. Adding or changing a
field requires a new schema and prompt version rather than silently changing historical
runs. This schema is intentionally inspection-specific, not a general document ontology.
