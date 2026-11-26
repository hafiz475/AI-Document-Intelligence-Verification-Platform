# ADR 0036: Explicit retention and history-safe deletion

No automatic purge is enabled. OWNER project deletion removes objects before database
cascade. Document deletion is blocked when immutable extraction/RAG provenance exists;
policy owners define retention periods and audit export requirements.
