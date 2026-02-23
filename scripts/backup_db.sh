#!/usr/bin/env bash
# =============================================================================
# Database Backup Script — Kerala Delivery Route Optimizer
# =============================================================================
# Creates a compressed PostgreSQL dump of the routing_opt database.
# Designed to run:
#   - Manually: ./scripts/backup_db.sh
#   - Via cron: 0 2 * * * /path/to/scripts/backup_db.sh  (daily at 2 AM)
#
# The pg_dump runs INSIDE the running PostgreSQL container, so no external
# psql/pg_dump binary is needed on the host.
#
# Backup files are written to the BACKUP_DIR (default: ./backups/).
# Naming convention: routing_opt_YYYYMMDD_HHMMSS.sql.gz
#
# Retention: keeps the last N backups (default: 7) and deletes older ones.
# At ~50 deliveries/day, a full dump is ~5-10 MB compressed, so 7 backups
# use ~35-70 MB. Adjust RETAIN_COUNT for your needs.
#
# Restore instructions (printed at the end of each backup).
# =============================================================================
set -euo pipefail

# ── Configuration (override via environment variables) ────────────────────────
# Which compose file to use. Auto-detects prod vs dev.
COMPOSE_FILE="${COMPOSE_FILE:-}"
if [[ -z "$COMPOSE_FILE" ]]; then
    if [[ -f .env.production ]]; then
        COMPOSE_FILE="docker-compose.prod.yml"
        ENV_FILE=".env.production"
    else
        COMPOSE_FILE="docker-compose.yml"
        ENV_FILE=".env"
    fi
fi

# Container name of the PostgreSQL service.
DB_CONTAINER="${DB_CONTAINER:-}"
if [[ -z "$DB_CONTAINER" ]]; then
    # Detect from compose file
    if [[ "$COMPOSE_FILE" == *prod* ]]; then
        DB_CONTAINER="lpg-db-prod"
    else
        DB_CONTAINER="lpg-db"
    fi
fi

# Database credentials — extract ONLY the needed variables from the env file.
# SECURITY: We use grep instead of `source` to avoid loading ALL secrets
# (API_KEY, GOOGLE_MAPS_API_KEY, etc.) into the shell environment. If this
# script runs under cron with logging or with `set -x`, sourcing would leak
# secrets to log files. Extract only what we need: DB user and DB name.
DB_USER="routing"
DB_NAME="routing_opt"
if [[ -f "${ENV_FILE:-.env}" ]]; then
    _extracted_user=$(grep -E '^POSTGRES_USER=' "${ENV_FILE:-.env}" 2>/dev/null | cut -d= -f2- || true)
    _extracted_db=$(grep -E '^POSTGRES_DB=' "${ENV_FILE:-.env}" 2>/dev/null | cut -d= -f2- || true)
    [[ -n "$_extracted_user" ]] && DB_USER="$_extracted_user"
    [[ -n "$_extracted_db" ]] && DB_NAME="$_extracted_db"
fi

# Backup destination directory (on the host machine).
BACKUP_DIR="${BACKUP_DIR:-./backups}"

# How many backups to keep. Older backups are automatically deleted.
# 7 = one week of daily backups. Increase if you want more history.
RETAIN_COUNT="${RETAIN_COUNT:-7}"

# ── Create backup directory if it doesn't exist ──────────────────────────────
mkdir -p "$BACKUP_DIR"

# ── Generate timestamped filename ────────────────────────────────────────────
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Database Backup — Kerala Delivery Route Optimizer          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Database:   $DB_NAME"
echo "  Container:  $DB_CONTAINER"
echo "  Output:     $BACKUP_FILE"
echo "  Retention:  last $RETAIN_COUNT backups"
echo ""

# ── Check that the container is running ──────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    echo "❌ Error: Container '$DB_CONTAINER' is not running."
    echo "   Start the stack first: docker compose -f $COMPOSE_FILE up -d"
    exit 1
fi

# ── Run pg_dump inside the container ─────────────────────────────────────────
# Why pg_dump flags:
#   --format=custom: PostgreSQL's binary dump format. Supports parallel restore,
#     selective table restore, and is smaller than plain SQL.
#     Wait — we're piping through gzip, so use plain format instead.
#   --no-owner: don't include ownership commands (the restore user may differ).
#   --no-privileges: don't include GRANT/REVOKE (security: dump is portable).
#   --verbose: show progress (table by table).
#
# Why pipe through gzip on the host?
# The container may not have gzip installed. We stream the SQL output through
# Docker's stdout and compress on the host side. Works with any base image.
echo "⏳ Running pg_dump..."
# Why no `2>&1`? pg_dump writes the SQL dump to stdout and --verbose progress
# messages to stderr. If we merged them (2>&1), the progress messages would
# get mixed into the gzip file, producing a CORRUPT backup that can't be
# restored. By leaving stderr alone, progress messages print to the terminal
# while only the clean SQL goes through gzip.
docker exec "$DB_CONTAINER" \
    pg_dump \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-owner \
        --no-privileges \
        --verbose \
    | gzip > "$BACKUP_FILE"

# ── Verify the backup file exists and has content ────────────────────────────
if [[ ! -s "$BACKUP_FILE" ]]; then
    echo "❌ Error: Backup file is empty or was not created."
    rm -f "$BACKUP_FILE"
    exit 1
fi

BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
echo ""
echo "✅ Backup complete: $BACKUP_FILE ($BACKUP_SIZE)"

# ── Rotate old backups ───────────────────────────────────────────────────────
# Keep only the newest RETAIN_COUNT backup files. Delete the rest.
# Why ls -t? Sorts by modification time, newest first.
# tail -n +N: skip the first N-1 lines (keep the newest).
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -type f | wc -l)

if [[ "$BACKUP_COUNT" -gt "$RETAIN_COUNT" ]]; then
    DELETE_COUNT=$((BACKUP_COUNT - RETAIN_COUNT))
    echo "🗑️  Rotating: deleting $DELETE_COUNT old backup(s), keeping $RETAIN_COUNT"
    # shellcheck disable=SC2012
    ls -t "$BACKUP_DIR"/${DB_NAME}_*.sql.gz | tail -n +"$((RETAIN_COUNT + 1))" | xargs rm -f
fi

# ── Print restore instructions ───────────────────────────────────────────────
echo ""
echo "━━━ Restore instructions ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  # 1. Stop the API to prevent writes during restore:"
echo "  docker compose -f $COMPOSE_FILE stop api"
echo ""
echo "  # 2. Drop and recreate the database:"
echo "  docker exec -i $DB_CONTAINER psql -U $DB_USER -c 'DROP DATABASE IF EXISTS ${DB_NAME};'"
echo "  docker exec -i $DB_CONTAINER psql -U $DB_USER -c 'CREATE DATABASE ${DB_NAME};'"
echo ""
echo "  # 3. Restore the backup:"
echo "  gunzip -c $BACKUP_FILE | docker exec -i $DB_CONTAINER psql -U $DB_USER -d ${DB_NAME}"
echo ""
echo "  # 4. Restart the stack:"
echo "  docker compose -f $COMPOSE_FILE up -d"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
