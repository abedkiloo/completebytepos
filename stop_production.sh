#!/bin/bash

###############################################################################
# CompleteBytePOS Production Stop Script
# This script stops the production server
###############################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/be"

echo -e "${BLUE}Stopping CompleteBytePOS production server...${NC}"

# Stop gunicorn if running
if [ -f "$BACKEND_DIR/gunicorn.pid" ]; then
    PID=$(cat "$BACKEND_DIR/gunicorn.pid")
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "${YELLOW}Stopping Gunicorn (PID: $PID)...${NC}"
        kill $PID
        sleep 2
        
        # Force kill if still running
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Force stopping Gunicorn...${NC}"
            kill -9 $PID
        fi
        
        rm -f "$BACKEND_DIR/gunicorn.pid"
        echo -e "${GREEN}Gunicorn stopped${NC}"
    else
        echo -e "${YELLOW}Gunicorn process not found (PID: $PID)${NC}"
        rm -f "$BACKEND_DIR/gunicorn.pid"
    fi
else
    echo -e "${YELLOW}No Gunicorn PID file found${NC}"
fi

# Kill any remaining processes on ports
echo -e "${YELLOW}Cleaning up processes on ports 8000 and 3000...${NC}"
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

echo -e "${GREEN}Production server stopped${NC}"
