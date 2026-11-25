# 0022: Separate instructions from retrieved document data

## Status

Accepted

## Decision

Keep system instructions, user question, and retrieved evidence in explicit boundaries.
State that document text is untrusted data and instructions within it have no authority.
Validate citations after generation.

## Consequences

This reduces prompt-injection impact and limits grounded claims to stored evidence, but
does not eliminate prompt-injection risk. M4 adds no arbitrary tools, browsing, or
agents that retrieved text could invoke.
