# ADR 0035: Coordinated metadata and binary recovery

PostgreSQL and object storage require coordinated protected backups and restore drills.
Redis is transient and is never treated as a backup. Migration/readiness and evidence
provenance are verified after restore.
