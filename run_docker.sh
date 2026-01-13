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
    $COMPOSE_CMD down 2>/dev/null || true
}

# Build and start
start_containers() {
    print_info "Building and starting Docker containers..."
    cd "$PROJECT_ROOT"
    
    $COMPOSE_CMD build --no-cache
    $COMPOSE_CMD up -d
    
    print_info "Waiting for services to be ready..."
    sleep 5
    
    if docker ps | grep -q completebytepos_backend && docker ps | grep -q completebytepos_frontend; then
        print_success "Containers are running"
    else
        print_error "Some containers failed to start!"
        print_info "Check logs with: $COMPOSE_CMD logs"
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
    echo -e "Frontend: ${BLUE}http://localhost:3000${NC}"
    echo -e "Backend API: ${BLUE}http://localhost:8000/api${NC}"
    echo -e "Admin Panel: ${BLUE}http://localhost:8000/admin${NC}"
    echo ""
    echo -e "Container Status:"
    docker ps --filter "name=completebytepos" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo -e "To view logs: ${YELLOW}$COMPOSE_CMD logs -f${NC}"
    echo -e "To stop: ${YELLOW}./stop_docker.sh${NC} or ${YELLOW}$COMPOSE_CMD down${NC}"
    echo ""
    
    # Test connections
    print_info "Testing connections..."
    sleep 3
    if curl -s http://localhost:8000/api/accounts/auth/me/ > /dev/null 2>&1; then
        print_success "Backend is responding"
    else
        print_warning "Backend may still be starting. Check logs if issues persist."
    fi
    
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        print_success "Frontend is responding"
    else
        print_warning "Frontend may still be starting. Check logs if issues persist."
    fi
}

# Main
main() {
    check_docker
    stop_existing
    start_containers
    show_status
}

trap 'print_info "Script interrupted. Use ./stop_docker.sh to stop containers."' INT TERM
main
