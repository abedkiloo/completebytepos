#!/bin/sh
# Production container entrypoint — always bind on all interfaces so nginx
# (other containers) can reach Gunicorn. Binding 127.0.0.1 makes healthchecks
# pass while the SPA gets 502 Connection refused.
set -e

mkdir -p /app/logs

python manage.py migrate --noinput
python manage.py init_permissions --noinput 2>/dev/null \
  || python manage.py init_permissions || true
python manage.py init_modules || true
python manage.py create_users || true
python manage.py collectstatic --noinput || true

WORKERS="${GUNICORN_WORKERS:-2}"
THREADS="${GUNICORN_THREADS:-4}"
TIMEOUT="${GUNICORN_TIMEOUT:-60}"
MAX_REQ="${GUNICORN_MAX_REQUESTS:-800}"

echo "Starting Gunicorn on 0.0.0.0:8000 (workers=${WORKERS} threads=${THREADS})"

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --worker-class gthread \
  --workers "${WORKERS}" \
  --threads "${THREADS}" \
  --timeout "${TIMEOUT}" \
  --keep-alive 5 \
  --max-requests "${MAX_REQ}" \
  --max-requests-jitter 80 \
  --worker-tmp-dir /dev/shm \
  --access-logfile - \
  --error-logfile -
