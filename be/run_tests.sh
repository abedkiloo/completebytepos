#!/bin/bash

# Script to run backend tests
# Usage: ./run_tests.sh [test_module]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Running CompleteBytePOS Backend Tests${NC}"
echo -e "${GREEN}========================================${NC}"

# Change to backend directory (script is already in be/)
cd "$(dirname "$0")" || exit 1

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${YELLOW}Activated virtual environment${NC}"
fi

# Run specific test module or all tests
if [ -n "$1" ]; then
    echo -e "${YELLOW}Running tests for: $1${NC}"
    python manage.py test "$1" --verbosity=2
else
    echo -e "${YELLOW}Running all tests...${NC}"
    python manage.py test --verbosity=2
fi

# Check exit status
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}All tests passed! ✓${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "\n${RED}========================================${NC}"
    echo -e "${RED}Some tests failed! ✗${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi
