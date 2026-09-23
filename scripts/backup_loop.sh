#!/bin/sh
# Stay running and dump SQL onto the host disk every BACKUP_INTERVAL_DAYS (default 14).
# Rechecks hourly so a container restart does not skip or double-dump.

set -eu

trap 'exit 0' TERM INT

log() {
  echo "[backup-loop $(date '+%Y-%m-%d %H:%M:%S')] $*"
}

INTERVAL_DAYS="${BACKUP_INTERVAL_DAYS:-14}"
log "Starting fortnightly SQL backup job (every ${INTERVAL_DAYS} days) -> ${BACKUP_DIR:-/backups}"

# First pass dumps immediately if none exists yet.
while true; do
  if ! /usr/local/bin/backup_postgres.sh; then
    log "Dump failed; will retry in 1 hour"
  fi
  sleep 3600 &
  wait $! || true
done
