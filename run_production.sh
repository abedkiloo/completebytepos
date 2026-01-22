#!/bin/bash

###############################################################################
# CompleteBytePOS - Production Run Script
# Runs the application in production mode using Docker
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}CompleteBytePOS - Production Mode${NC}"
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

# Clear Docker caches
clear_docker_cache() {
    print_info "Clearing Docker build cache and Buildx cache..."
    docker builder prune -af 2>/dev/null || true
    docker buildx prune -af 2>/dev/null || true
    print_success "Docker cache cleared"
}

# Run with Docker
run_docker() {
    print_info "Building and starting Docker containers in production mode..."
    
    cd "$PROJECT_ROOT"
    
    # Set production environment
    export DEBUG=False
    
    # Stop existing containers
    print_info "Stopping existing containers..."
    $COMPOSE_CMD down 2>/dev/null || true
    
    # Clear Docker caches to fix "file already closed" BuildKit errors
    if [[ "$*" == *"--clear-cache"* ]] || [[ "$*" == *"-c"* ]]; then
        clear_docker_cache
    else
        print_info "Clearing Docker Buildx cache..."
        docker buildx prune -f 2>/dev/null || true
    fi
    
    # Build and start
    print_info "Building Docker images..."
    # Try with BuildKit first, fallback to legacy builder if it fails
    if ! DOCKER_BUILDKIT=1 $COMPOSE_CMD build --no-cache --progress=plain; then
        print_warning "Build with BuildKit failed, trying without BuildKit..."
        DOCKER_BUILDKIT=0 $COMPOSE_CMD build --no-cache
    fi
    
    print_info "Starting containers..."
    $COMPOSE_CMD up -d
    
    # Wait for services
    print_info "Waiting for services to be ready..."
    sleep 10
    
    # Ensure migrations are run (safety check)
    run_migrations
    
    print_success "Production containers started!"
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Production server started!${NC}"
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
    echo -e "To stop: ${YELLOW}./stop_production.sh${NC} or ${YELLOW}$COMPOSE_CMD down${NC}"
    echo ""
}

# Run migrations explicitly (safety check)
run_migrations() {
    print_info "Ensuring database migrations are up to date..."
    
    # Wait a bit for backend to be ready
    sleep 3
    
    # Check if backend container is running
    if ! docker ps | grep -q completebytepos_backend; then
        print_warning "Backend container not running, skipping migration check"
        return
    fi
    
    # Run makemigrations (create new migrations if needed)
    if docker exec completebytepos_backend python manage.py makemigrations --noinput 2>/dev/null; then
        print_success "Migration files checked/created"
    else
        print_warning "makemigrations had issues (this is usually OK if no new migrations needed)"
    fi
    
    # Run migrate (apply migrations)
    if docker exec completebytepos_backend python manage.py migrate --noinput 2>/dev/null; then
        print_success "Database migrations applied"
    else
        print_error "Failed to run migrations!"
        print_info "Check backend logs: $COMPOSE_CMD logs backend"
        return 1
    fi
}

# Main
main() {
    if [[ "$*" == *"--help"* ]] || [[ "$*" == *"-h"* ]]; then
        echo "Usage: ./run_production.sh [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --clear-cache, -c    Clear all Docker caches before building"
        echo "  --help, -h           Show this help message"
        echo ""
        echo "Example:"
        echo "  ./run_production.sh --clear-cache"
        exit 0
    elif [[ "$*" == *"--no-docker"* ]]; then
        print_warning "Non-Docker production mode is not recommended"
        print_info "Please use Docker for production: ./run_production.sh"
        exit 1
    else
        check_docker
        run_docker "$@"
    fi
}

main "$@"
