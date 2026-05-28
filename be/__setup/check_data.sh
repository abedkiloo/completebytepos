#!/bin/bash

# Script to check if database has data
# Usage: ./check_data.sh [--detailed] [--min-count N]

echo "Checking database data..."
echo ""

# Check if we're in Docker or local
if [ -f "docker-compose.yml" ] && docker ps | grep -q "completebytepos_backend"; then
    echo "Running in Docker environment..."
    docker exec completebytepos_backend python manage.py check_data "$@"
else
    echo "Running locally..."
    cd be
    python manage.py check_data "$@"
    cd ..
fi
