# 0021: Make insufficient evidence a successful safe outcome

## Status

Accepted

## Decision

Represent evidence insufficiency as a completed answer with
INSUFFICIENT_EVIDENCE, zero citations, and one canonical response. Do not invent a
numeric confidence or force an answer.

## Consequences

Users can distinguish lack of evidence from provider/system failure. Provider wording
cannot turn an insufficient result into an unsupported factual answer.
