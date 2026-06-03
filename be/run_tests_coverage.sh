#!/bin/bash
# Run backend tests with coverage report.
# Usage: ./run_tests_coverage.sh [django test label]
# Example: ./run_tests_coverage.sh accounts.tests

set -e
cd "$(dirname "$0")"

export USE_SQLITE="${USE_SQLITE:-true}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings}"

if [ -d "venv" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

GATES=false
LABEL=""
for arg in "$@"; do
  case "$arg" in
    --gates) GATES=true ;;
    *) LABEL="$arg" ;;
  esac
done

echo "Running tests (USE_SQLITE=$USE_SQLITE)…"
TEST_EXIT=0
if [ -n "$LABEL" ]; then
  coverage run --source='.' manage.py test "$LABEL" --verbosity=1 || TEST_EXIT=$?
else
  coverage run --source='.' manage.py test --verbosity=1 || TEST_EXIT=$?
fi

echo ""
coverage report -m
coverage json -o coverage.json -q
echo ""
echo "HTML report: file://$(pwd)/htmlcov/index.html"

if [ "$GATES" = true ]; then
  echo ""
  python3 testing/check_gates.py || TEST_EXIT=1
fi

exit "$TEST_EXIT"
