# Operations runbook

## Triage

Check `/health` for process liveness and `/ready` for PostgreSQL, Redis, storage, and
required configuration. Inspect JSON logs by `request_id`, `trace_id`, project, run,
question, evaluation, or job identifier. Internal Prometheus metrics are available only
with `X-Metrics-Token` when `ASSUREAI_METRICS_TOKEN` is configured.

## Failed jobs

1. Query documents and each run table for `FAILED`; correlate the identifier with worker
   logs and Dramatiq's Redis broker state.
2. Fix configuration, dependency, or input causes before retrying.
3. Retry ingestion only when the original private object still exists. Re-create an
   extraction, embedding, RAG question, or evaluation run through its authorized API;
   completed immutable runs are never mutated.
4. Do not retry validation failures, malware rejection, unsupported/malformed files,
   authorization failures, or deterministic evidence/citation rejection without fixing
   the source condition.

Dramatiq retries are bounded with exponential backoff and hard time limits. Database
checkpoints make local persistence idempotent where practical. AssureAI does **not**
claim exactly-once provider execution: a process can crash after a provider accepted a
request but before the local checkpoint commits.

## Shutdown and recovery

Stop the web/API first to reject new work, allow workers to finish within their time
limit, then stop workers. API shutdown closes Redis, database, storage, secret, and
telemetry clients. After restart, inspect PROCESSING rows whose jobs are absent and
follow the safe retry rules above.
