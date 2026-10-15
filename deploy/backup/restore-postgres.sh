#!/usr/bin/env bash
# Restore a verified custom-format dump. Use only for a non-production dry run
# until the restore procedure has been tested.
set -Eeuo pipefail

: "${COMPOSE_FILE:?COMPOSE_FILE is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
BACKUP_FILE="${1:-}"

if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
    echo "Set CONFIRM_RESTORE=YES to restore a database" >&2
    exit 2
fi
if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
    echo "Pass an existing backup file as the first argument" >&2
    exit 2
fi

docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore --host=127.0.0.1 --username="$1" --list' \
    restore-postgres "$POSTGRES_USER" < "$BACKUP_FILE" >/dev/null

echo "Restoring database from $(basename "$BACKUP_FILE")"
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore --host=127.0.0.1 --username="$1" --dbname="$2" --clean --if-exists --exit-on-error --no-owner --no-privileges' \
    restore-postgres "$POSTGRES_USER" "$POSTGRES_DB" < "$BACKUP_FILE"

echo "Restore completed"
