#!/bin/bash

###############################################################################
# CompleteBytePOS - Docker Stop Script
#   ./stop_docker.sh          prod + dev only (UAT keeps running)
#   ./stop_docker.sh --uat    UAT only
#   ./stop_docker.sh --all    prod, dev, and UAT
###############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STOP_UAT=false
STOP_PROD=true
for arg in "$@"; do
    case "$arg" in
        --uat) STOP_UAT=true; STOP_PROD=false ;;
        --all) STOP_UAT=true; STOP_PROD=true ;;
    esac
done

if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

cd "$PROJECT_ROOT"

if [ "$STOP_PROD" = true ]; then
    echo -e "${BLUE}Stopping production / dev containers...${NC}"
    if [ -f "docker-compose.dev.yml" ]; then
        $COMPOSE_CMD -f docker-compose.dev.yml down 2>/dev/null || true
    fi
    $COMPOSE_CMD down 2>/dev/null || true
fi

if [ "$STOP_UAT" = true ]; then
    echo -e "${BLUE}Stopping UAT containers (omuwenga-uat)...${NC}"
    extra=( -p omuwenga-uat )
    if [ -f ".env.uat" ]; then
        extra+=( --env-file .env.uat )
    fi
    $COMPOSE_CMD "${extra[@]}" -f docker-compose.yml down 2>/dev/null || true
fi

echo -e "${GREEN}Requested Docker containers stopped${NC}"
if [ "$STOP_PROD" = true ] && [ "$STOP_UAT" = false ]; then
    echo -e "${YELLOW}UAT left running.${NC} Stop it with: ./stop_docker.sh --uat"
fi
