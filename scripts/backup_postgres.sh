#!/bin/sh
# Dump PostgreSQL to a plain .sql file on the host-mounted backup disk.
# Used by the compose `backup` service and can be run by hand:
#   docker exec completebytepos_backup /usr/local/bin/backup_postgres.sh
#   FORCE=1 docker exec completebytepos_backup /usr/local/bin/backup_postgres.sh

set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
STACK_NAME="${STACK_NAME:-completebytepos}"
PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-completebytepos}}"
PGUSER="${PGUSER:-${POSTGRES_USER:-completebytepos}}"
PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
BACKUP_KEEP="${BACKUP_KEEP:-8}"
BACKUP_INTERVAL_DAYS="${BACKUP_INTERVAL_DAYS:-14}"
FORCE="${FORCE:-0}"
STAMP_FILE="${BACKUP_DIR}/.last_backup"

log() {
  echo "[backup $(date '+%Y-%m-%d %H:%M:%S')] $*"
}

die() {
  log "ERROR: $*"
  exit 1
}

now_epoch() {
  date +%s
}

is_due() {
  if [ "$FORCE" = "1" ]; then
    return 0
  fi
  if [ ! -f "$STAMP_FILE" ]; then
    return 0
  fi
  last="$(cat "$STAMP_FILE" 2>/dev/null || echo 0)"
  case "$last" in
    ''|*[!0-9]*) last=0 ;;
  esac
  interval_secs=$((BACKUP_INTERVAL_DAYS * 86400))
  now="$(now_epoch)"
  due=$((last + interval_secs))
  [ "$now" -ge "$due" ]
}

prune_old() {
  keep="$BACKUP_KEEP"
  if [ "$keep" -lt 1 ]; then
    return 0
  fi
  # Newest first; drop anything past the keep count.
  old="$(ls -1t "$BACKUP_DIR/${STACK_NAME}_"*.sql 2>/dev/null | tail -n +"$((keep + 1))" || true)"
  if [ -z "$old" ]; then
    return 0
  fi
  echo "$old" | while IFS= read -r file; do
    [ -n "$file" ] || continue
    rm -f "$file"
    log "Removed old dump $file"
  done
}

command -v pg_dump >/dev/null 2>&1 || die "pg_dump not found"

mkdir -p "$BACKUP_DIR"

if ! is_due; then
  log "Not due yet (every ${BACKUP_INTERVAL_DAYS} days). Use FORCE=1 to dump now."
  exit 0
fi

stamp="$(date '+%Y%m%d_%H%M%S')"
outfile="${BACKUP_DIR}/${STACK_NAME}_${PGDATABASE}_${stamp}.sql"

log "Dumping ${PGDATABASE} from ${PGHOST}:${PGPORT} -> ${outfile}"

pg_dump \
  --host="$PGHOST" \
  --port="$PGPORT" \
  --username="$PGUSER" \
  --dbname="$PGDATABASE" \
  --no-owner \
  --no-acl \
  --clean \
  --if-exists \
  --format=plain \
  --file="$outfile"

[ -s "$outfile" ] || die "Dump file is empty: $outfile"

now_epoch > "$STAMP_FILE"
prune_old
log "Wrote $(wc -c < "$outfile" | tr -d ' ') bytes to $outfile"
