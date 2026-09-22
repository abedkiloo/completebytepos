#!/usr/bin/env bash
# Backfill stored contact phones with the default country prefix (254).
# Usage:
#   ./normalize_phone_numbers.sh --dry-run
#   ./normalize_phone_numbers.sh
#   ./normalize_phone_numbers.sh --uat --dry-run
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

UAT=0
DRY=()
for arg in "$@"; do
  case "$arg" in
    --uat) UAT=1 ;;
    --dry-run) DRY=(--dry-run) ;;
    -h|--help)
      sed -n '2,7p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

COMPOSE=(docker compose)
if [[ "$UAT" -eq 1 ]]; then
  COMPOSE=(docker compose --env-file .env.uat)
fi

exec "${COMPOSE[@]}" exec backend python manage.py normalize_phone_numbers "${DRY[@]}"
