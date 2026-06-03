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

LABEL="${1:-}"

echo "Running tests (USE_SQLITE=$USE_SQLITE)…"
if [ -n "$LABEL" ]; then
  coverage run --source='.' manage.py test "$LABEL" --verbosity=1
else
  coverage run --source='.' manage.py test --verbosity=1
fi

echo ""
coverage report -m
echo ""
echo "HTML report: file://$(pwd)/htmlcov/index.html"
