# 0027: Advisory regression thresholds

Status: Accepted

## Decision

Comparison accepts optional minimum quality and maximum latency/token regression
thresholds. A missed quality minimum is REGRESSION; exceeded resource thresholds are
WARNING; otherwise the result is PASS.

Thresholds are advisory UI/API output in M5. They do not block deployment, promote a
model, or trigger rollback automatically.
