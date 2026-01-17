#!/bin/bash

###############################################################################
# CompleteBytePOS - Docker Run Script
# Builds and runs the application using Docker Compose
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}CompleteBytePOS - Docker Mode${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        print_info "Please install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running!"
        print_info "Please start Docker Desktop or Docker daemon"
        exit 1
    fi
    
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    elif docker-compose version &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        print_error "Docker Compose is not installed!"
        exit 1
    fi
    
    print_success "Docker is ready"
}

# Stop existing containers
stop_existing() {
    print_info "Stopping existing containers..."
    cd "$PROJECT_ROOT"
    
    # Stop dev containers
    if [ -f "docker-compose.dev.yml" ]; then
        $COMPOSE_CMD -f docker-compose.dev.yml down 2>/dev/null || true
    fi
    
    # Stop regular containers
    $COMPOSE_CMD down 2>/dev/null || true
}

# Build and start
start_containers() {
    print_info "Building and starting Docker containers in DEVELOPMENT mode..."
    print_info "Hot reloading is enabled for both frontend and backend"
    cd "$PROJECT_ROOT"
    
    # Use development compose file
    COMPOSE_FILE="docker-compose.dev.yml"
    
    # Check if docker-compose.dev.yml exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "Development compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    # Build without cache on first run, then use cache for faster rebuilds
    if [ "$1" == "--rebuild" ]; then
        print_info "Rebuilding images from scratch..."
        $COMPOSE_CMD -f $COMPOSE_FILE build --no-cache
    else
        print_info "Building images (using cache if available)..."
        $COMPOSE_CMD -f $COMPOSE_FILE build
    fi
    
    $COMPOSE_CMD -f $COMPOSE_FILE up -d
    
    print_info "Waiting for services to be ready..."
    sleep 5
    
    if docker ps | grep -q completebytepos_backend && docker ps | grep -q completebytepos_frontend; then
        print_success "Containers are running"
    else
        print_error "Some containers failed to start!"
        print_info "Check logs with: $COMPOSE_CMD -f $COMPOSE_FILE logs"
        exit 1
    fi
}

# Show status
show_status() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Docker containers started!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Frontend (Dev Server): ${BLUE}http://localhost:3000${NC}"
    echo -e "Backend API: ${BLUE}http://localhost:8000/api${NC}"
    echo -e "Admin Panel: ${BLUE}http://localhost:8000/admin${NC}"
    echo ""
    echo -e "${GREEN}✨ Hot Reloading Enabled:${NC}"
    echo -e "  • Frontend: Changes to ${BLUE}fe/src${NC} will auto-reload"
    echo -e "  • Backend: Changes to ${BLUE}be/**/*.py${NC} will auto-reload (via gunicorn --reload)"
    echo ""
    echo -e "Container Status:"
    docker ps --filter "name=completebytepos" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo -e "To view logs: ${YELLOW}$COMPOSE_CMD -f docker-compose.dev.yml logs -f${NC}"
    echo -e "To view backend logs: ${YELLOW}$COMPOSE_CMD -f docker-compose.dev.yml logs -f backend${NC}"
    echo -e "To view frontend logs: ${YELLOW}$COMPOSE_CMD -f docker-compose.dev.yml logs -f frontend${NC}"
    echo -e "To stop: ${YELLOW}./stop_docker.sh${NC} or ${YELLOW}$COMPOSE_CMD -f docker-compose.dev.yml down${NC}"
    echo -e "To rebuild: ${YELLOW}./run_docker.sh --rebuild${NC}"
    echo ""
    
    # Test connections
    print_info "Testing connections..."
    sleep 8  # Give more time for React dev server to start
    
    if curl -s http://localhost:8000/api/accounts/auth/me/ > /dev/null 2>&1; then
        print_success "Backend is responding"
    else
        print_warning "Backend may still be starting. Check logs if issues persist."
    fi
    
    # React dev server takes longer to start
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        print_success "Frontend dev server is responding"
    else
        print_warning "Frontend dev server may still be starting (this can take 30-60 seconds)."
        print_info "Check logs with: $COMPOSE_CMD -f docker-compose.dev.yml logs -f frontend"
    fi
}

# Main
main() {
    check_docker
    stop_existing
    
    # Check for --rebuild flag
    if [ "$1" == "--rebuild" ]; then
        start_containers --rebuild
    else
        start_containers
    fi
    
    show_status
}

trap 'print_info "Script interrupted. Use ./stop_docker.sh to stop containers."' INT TERM
main
