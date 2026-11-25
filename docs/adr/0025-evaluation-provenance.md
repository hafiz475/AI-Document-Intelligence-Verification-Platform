# 0025: Immutable evaluation provenance

Status: Accepted

## Decision

At queue time each run snapshots case input, expected output, name, and metadata. It also
stores dataset/type, prompt version, provider/model, embedding provider/model/dimensions,
top-k, workflow version, and evaluator version. Results repeat their exact case snapshot.

## Consequences

Editing a dataset later cannot change what a historical run measured. Snapshots consume
additional JSON storage but avoid ambiguous historical results.
