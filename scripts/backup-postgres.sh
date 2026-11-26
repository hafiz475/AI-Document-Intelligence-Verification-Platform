#!/usr/bin/env sh
set -eu
: "${DATABASE_URL:?set DATABASE_URL}"
: "${BACKUP_FILE:?set BACKUP_FILE to an explicit protected path}"
pg_dump --format=custom --no-owner --no-acl --file="$BACKUP_FILE" "$DATABASE_URL"
pg_restore --list "$BACKUP_FILE" >/dev/null
