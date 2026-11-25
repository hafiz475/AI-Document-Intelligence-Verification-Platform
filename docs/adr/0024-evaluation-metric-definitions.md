# 0024: Deterministic metric definitions

Status: Accepted

## Decision

Evaluator v1 defines extraction exact match, explicit case/whitespace normalized match,
field accuracy, missing rate, and optional exact evidence precision/recall. Retrieval
defines chunk and document Hit@K, Recall@K, and MRR separately. RAG defines support
status, required/forbidden citations and phrases, M4 citation validity,
insufficient-evidence correctness, and groundedness as the fraction of citations that
pass M4 validation.

No fuzzy or semantic equivalence is implied. Historical runs retain evaluator version v1.
