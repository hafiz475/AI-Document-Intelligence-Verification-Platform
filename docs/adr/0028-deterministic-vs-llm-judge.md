# 0028: Deterministic evaluation before LLM judge

Status: Accepted

## Decision

M5 uses deterministic metrics only. LLM-as-judge is deferred. If introduced later it
must be clearly labelled, store judge provider/model/prompt provenance, never replace
deterministic metrics, and never be required by deterministic CI tests.

## Consequences

M5 does not claim semantic faithfulness beyond its measured support, citation, and exact
phrase checks.
