#!/bin/bash

###############################################################################
# CompleteBytePOS - Docker Stop Script
# Stops and removes Docker containers
###############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}Stopping CompleteBytePOS Docker containers...${NC}"

if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

cd "$PROJECT_ROOT"

# Stop dev containers first
if [ -f "docker-compose.dev.yml" ]; then
    $COMPOSE_CMD -f docker-compose.dev.yml down 2>/dev/null || true
fi

# Also stop any containers using regular compose file
$COMPOSE_CMD down 2>/dev/null || true

echo -e "${GREEN}Docker containers stopped${NC}"
