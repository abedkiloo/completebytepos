#!/bin/sh
# Unit tests for backup_postgres.sh (no Postgres / Docker required).

set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/backup_postgres.sh"
FAILS=0

assert() {
  if [ "$1" = "$2" ]; then
    echo "  ok  $3"
  else
    echo "  FAIL $3 (expected '$2', got '$1')"
    FAILS=$((FAILS + 1))
  fi
}

assert_file() {
  if [ -f "$1" ]; then
    echo "  ok  $2"
  else
    echo "  FAIL $2 (missing $1)"
    FAILS=$((FAILS + 1))
  fi
}

WORKDIR="$(mktemp -d)"
trap '/bin/rm -rf "$WORKDIR"' EXIT

mkdir -p "$WORKDIR/bin" "$WORKDIR/out"

cat > "$WORKDIR/bin/pg_dump" <<'EOF'
#!/bin/sh
# Honour --file=PATH from pg_dump flags.
file=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --file=*) file="${1#--file=}" ;;
    --file)
      shift
      file="$1"
      ;;
  esac
  shift
done
[ -n "$file" ] || exit 2
printf '%s\n' "-- CompleteBytePOS SQL backup fixture" > "$file"
printf '%s\n' "SELECT 1;" >> "$file"
EOF
chmod +x "$WORKDIR/bin/pg_dump" "$SCRIPT"

export PATH="$WORKDIR/bin:$PATH"
export BACKUP_DIR="$WORKDIR/out"
export STACK_NAME="teststack"
export PGDATABASE="testdb"
export PGUSER="testuser"
export PGHOST="db"
export PGPORT="5432"
export BACKUP_KEEP="2"
export BACKUP_INTERVAL_DAYS="14"
export FORCE="1"

echo "dump creates a .sql file on the backup disk"
sh "$SCRIPT"
count="$(ls -1 "$BACKUP_DIR"/teststack_testdb_*.sql | wc -l | tr -d ' ')"
assert "$count" "1" "one sql dump after first run"
assert_file "$BACKUP_DIR/.last_backup" "records last backup time"
head -n 1 "$BACKUP_DIR"/teststack_testdb_*.sql | grep -q "SQL backup" || {
  echo "  FAIL dump contents"
  FAILS=$((FAILS + 1))
}

echo "FORCE=0 skips when the last dump is recent"
export FORCE="0"
before="$(ls -1 "$BACKUP_DIR"/teststack_testdb_*.sql | wc -l | tr -d ' ')"
sh "$SCRIPT"
after="$(ls -1 "$BACKUP_DIR"/teststack_testdb_*.sql | wc -l | tr -d ' ')"
assert "$after" "$before" "no extra dump while still within 14 days"

echo "old stamp is treated as due"
echo "0" > "$BACKUP_DIR/.last_backup"
export FORCE="0"
sleep 1
sh "$SCRIPT"
count="$(ls -1 "$BACKUP_DIR"/teststack_testdb_*.sql | wc -l | tr -d ' ')"
# 2 dumps so far (first + due-again). Keep=2 so a third pass should prune.
assert "$count" "2" "second dump after interval elapsed"

echo "retention keeps only BACKUP_KEEP newest files"
echo "0" > "$BACKUP_DIR/.last_backup"
sleep 1
sh "$SCRIPT"
count="$(ls -1 "$BACKUP_DIR"/teststack_testdb_*.sql | wc -l | tr -d ' ')"
assert "$count" "2" "pruned down to 2 dumps"

echo "missing pg_dump fails"
mkdir -p "$WORKDIR/emptybin"
export PATH="$WORKDIR/emptybin"
export FORCE="1"
if sh "$SCRIPT" >/dev/null 2>&1; then
  echo "  FAIL expected missing pg_dump to fail"
  FAILS=$((FAILS + 1))
else
  echo "  ok  missing pg_dump exits non-zero"
fi

if [ "$FAILS" -ne 0 ]; then
  echo "FAILED: $FAILS assertion(s)"
  exit 1
fi
echo "All backup script tests passed."
