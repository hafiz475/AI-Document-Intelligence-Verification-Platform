#!/usr/bin/env sh
set -eu
: "${RESTORE_DATABASE_URL:?set RESTORE_DATABASE_URL to an isolated target}"
: "${BACKUP_FILE:?set BACKUP_FILE}"
pg_restore --clean --if-exists --no-owner --no-acl --dbname="$RESTORE_DATABASE_URL" "$BACKUP_FILE"
ASSUREAI_DATABASE_URL="$RESTORE_DATABASE_URL" alembic -c apps/api/alembic.ini upgrade head
