#!/bin/bash

###############################################################################
# CompleteBytePOS - Production Stop Script
# Stops production Docker containers
###############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}Stopping CompleteBytePOS production server...${NC}"

if docker ps --filter "name=completebytepos" --format "{{.Names}}" | grep -q completebytepos; then
    echo -e "${YELLOW}Stopping Docker containers...${NC}"
    
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    cd "$PROJECT_ROOT"
    $COMPOSE_CMD down
    
    echo -e "${GREEN}Production containers stopped${NC}"
else
    echo -e "${YELLOW}No Docker containers found${NC}"
fi
