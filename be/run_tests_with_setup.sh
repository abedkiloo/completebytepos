#!/bin/bash

# Script to run tests with proper database setup
# Usage: ./run_tests_with_setup.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CompleteBytePOS Test Runner${NC}"
echo -e "${GREEN}========================================${NC}"

# Change to backend directory
cd "$(dirname "$0")" || exit 1

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${YELLOW}Activated virtual environment${NC}"
fi

# Check if database exists
if [ ! -f "db.sqlite3" ]; then
    echo -e "${YELLOW}Database not found. Setting up...${NC}"
    echo -e "${YELLOW}Note: Tests use a separate test database, but migrations need to exist${NC}"
    python manage.py migrate --run-syncdb
fi

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
python manage.py test --verbosity=2

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
