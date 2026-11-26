# Backup and restore

PostgreSQL is authoritative for project metadata, extraction/evidence/review history,
chunks, embedding metadata/vectors, RAG/citations, evaluation provenance, memberships,
and audit events. Object storage is authoritative for original document binaries.
Redis/Dramatiq state is transient queue state and is **not** a database backup.

## Backup

Run `scripts/backup-postgres.sh` with `DATABASE_URL` and a protected destination. Back up
the local document volume or enable Azure Blob versioning, soft delete, lifecycle
management, and a separately protected recovery copy. Coordinate database and object
backup timestamps and encrypt backups at rest and in transit.

## Restore drill

1. Restore PostgreSQL into an isolated database with `scripts/restore-postgres.sh`.
2. Restore the corresponding document-object snapshot without making it public.
3. Run `alembic upgrade head`, then `/ready` against the isolated environment.
4. Verify membership boundaries, one original object, extraction evidence, one grounded
   citation, and evaluation provenance before switching traffic.

Test restores periodically. A backup that has not been restored is not verified.
