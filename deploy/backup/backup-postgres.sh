#!/usr/bin/env bash
# Create a verified PostgreSQL custom-format dump from the Compose service.
set -Eeuo pipefail
umask 077

: "${COMPOSE_FILE:?COMPOSE_FILE is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/humary}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-}"

if ! [[ "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
    echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2
    exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for PostgreSQL backups" >&2
    exit 2
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Compose file does not exist: $COMPOSE_FILE" >&2
    exit 2
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

lock_file="$BACKUP_DIR/.backup.lock"
exec 9>"$lock_file"
if ! flock -n 9; then
    echo "A PostgreSQL backup is already running" >&2
    exit 0
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_name="humary-postgres-${timestamp}.dump"
temporary_file="$BACKUP_DIR/.${backup_name}.tmp"
backup_file="$BACKUP_DIR/$backup_name"

cleanup() {
    rm -f "$temporary_file"
}
trap cleanup EXIT

echo "Creating PostgreSQL backup: $backup_name"
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump --host=127.0.0.1 --username="$1" --dbname="$2" --format=custom --no-owner --no-privileges' \
    backup-postgres "$POSTGRES_USER" "$POSTGRES_DB" > "$temporary_file"

if [[ ! -s "$temporary_file" ]]; then
    echo "Backup is empty" >&2
    exit 1
fi

# A dump is useful only if PostgreSQL can read its archive index.
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    sh -ec 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore --host=127.0.0.1 --username="$1" --list' \
    backup-postgres "$POSTGRES_USER" < "$temporary_file" >/dev/null

mv "$temporary_file" "$backup_file"
echo "Backup verified: $backup_file"

find "$BACKUP_DIR" \
    -maxdepth 1 \
    -type f \
    -name 'humary-postgres-*.dump' \
    -mtime "+$BACKUP_RETENTION_DAYS" \
    -delete

# Configure this with an rclone crypt remote. It keeps an independent,
# encrypted copy outside the VPS without keeping credentials in this script.
if [[ -n "$BACKUP_RCLONE_REMOTE" ]]; then
    if ! command -v rclone >/dev/null 2>&1; then
        echo "BACKUP_RCLONE_REMOTE is set but rclone is not installed" >&2
        exit 1
    fi
    rclone copyto "$backup_file" "$BACKUP_RCLONE_REMOTE/$backup_name" --checksum
    echo "Backup copied to the remote storage"
fi
