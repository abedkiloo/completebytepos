#!/bin/bash

###############################################################################
# CompleteBytePOS - UAT Stop Script
# Stops UAT Docker containers only (production keeps running)
###############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}Stopping CompleteBytePOS UAT server...${NC}"

if docker ps --filter "name=omuwenga-uat" --format "{{.Names}}" | grep -q omuwenga-uat; then
    echo -e "${YELLOW}Stopping UAT Docker containers...${NC}"

    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    cd "$PROJECT_ROOT"
    extra=( -p omuwenga-uat )
    if [ -f ".env.uat" ]; then
        extra+=( --env-file .env.uat )
    fi
    $COMPOSE_CMD "${extra[@]}" -f docker-compose.yml down

    echo -e "${GREEN}UAT containers stopped${NC}"
    echo -e "${YELLOW}Production was not stopped.${NC}"
else
    echo -e "${YELLOW}No UAT Docker containers found${NC}"
fi
