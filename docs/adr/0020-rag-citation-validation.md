# 0020: Treat provider citations as untrusted claims

## Status

Accepted

## Decision

After schema validation, independently verify chunk existence, project ownership,
membership in the persisted retrieval set, document/page equality, and normalized exact
quote inclusion. SUPPORTED and PARTIALLY_SUPPORTED require a valid citation.

## Consequences

Invented, cross-project, unretrieved, and fabricated citations fail the question rather
than becoming trusted data. Validation intentionally avoids fuzzy quote matching.
