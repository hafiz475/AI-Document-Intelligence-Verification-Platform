# 0026: Dynamic prompt and model comparison

Status: Accepted

## Decision

Compare two completed runs from the same dataset dynamically rather than persisting a
comparison table. Return run A, run B, and measured delta for quality, latency, and token
metrics. Prompt/model choices are run provenance. A deployment may select only configured
providers; the deterministic provider has one fixed model.

Retrieval or RAG runs with different embedding configurations are rejected unless the
caller explicitly permits an incompatible comparison. M5 never performs silent re-embedding.
