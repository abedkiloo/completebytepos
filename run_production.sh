#!/bin/bash

###############################################################################
# CompleteBytePOS - Production Run Script
# Builds and runs the application in production mode using Docker.
#
# Default: cached builds for the full stack (backend then frontend).
# Selective: --be / --fe so a frontend failure does not block a backend release.
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET="all"          # all | be | fe
NO_CACHE=false
CLEAR_CACHE=false
FORCE_DOWN=false

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    cat <<'EOF'
Usage: ./run_production.sh [OPTIONS]

Default builds the full stack with Docker layer cache (faster).
Use --be or --fe to release one side without rebuilding the other.

Options:
  --be                 Build and restart backend (+ db) only; keep frontend as-is
  --fe                 Build and restart frontend only; keep backend as-is
  --no-cache           Rebuild selected image(s) without Docker layer cache
  --clear-cache, -c    Prune Buildx/builder cache, then rebuild with --no-cache
  --down               Stop the stack before starting (full or selected services)
  --help, -h           Show this help

Examples:
  ./run_production.sh              # full stack, cached
  ./run_production.sh --be         # API/migrate only (FE failure cannot block this)
  ./run_production.sh --fe         # React/nginx image only
  ./run_production.sh --be --no-cache
  ./run_production.sh --clear-cache
EOF
}

parse_args() {
    local saw_be=false
    local saw_fe=false
    for arg in "$@"; do
        case "$arg" in
            --be) saw_be=true ;;
            --fe) saw_fe=true ;;
            --no-cache) NO_CACHE=true ;;
            --clear-cache|-c) CLEAR_CACHE=true; NO_CACHE=true ;;
            --down) FORCE_DOWN=true ;;
            --help|-h) usage; exit 0 ;;
            --no-docker)
                print_warning "Non-Docker production mode is not recommended"
                print_info "Please use Docker for production: ./run_production.sh"
                exit 1
                ;;
            *)
                print_error "Unknown option: $arg"
                usage
                exit 1
                ;;
        esac
    done
    if [ "$saw_be" = true ] && [ "$saw_fe" = true ]; then
        TARGET="all"
    elif [ "$saw_be" = true ]; then
        TARGET="be"
    elif [ "$saw_fe" = true ]; then
        TARGET="fe"
    else
        TARGET="all"
    fi
}

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

clear_docker_cache() {
    print_info "Clearing Docker build cache and Buildx cache..."
    docker builder prune -af 2>/dev/null || true
    docker buildx prune -af 2>/dev/null || true
    print_success "Docker cache cleared"
}

# Build one compose service. Uses cache unless --no-cache / --clear-cache.
build_service() {
    local service="$1"
    local extra=()
    if [ "$NO_CACHE" = true ]; then
        extra+=(--no-cache)
        print_info "Building ${service} (no cache)..."
    else
        print_info "Building ${service} (reusing cache when layers are unchanged)..."
    fi

    if ! DOCKER_BUILDKIT=1 $COMPOSE_CMD build --progress=plain "${extra[@]}" "$service"; then
        print_warning "BuildKit ${service} failed, trying without BuildKit..."
        DOCKER_BUILDKIT=0 $COMPOSE_CMD build "${extra[@]}" "$service"
    fi
}

run_migrations() {
    print_info "Ensuring database migrations are up to date..."
    sleep 3

    if ! docker ps --format '{{.Names}}' | grep -qx 'completebytepos_backend'; then
        print_warning "Backend container not running, skipping migration check"
        return 0
    fi

    # Apply committed migrations only — do not makemigrations on the VPS.
    if docker exec completebytepos_backend python manage.py migrate --noinput; then
        print_success "Database migrations applied"
    else
        print_error "Failed to run migrations!"
        print_info "Check backend logs: $COMPOSE_CMD logs backend"
        return 1
    fi
}

show_status() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Production update complete${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Frontend: ${BLUE}http://localhost:3000${NC}"
    echo -e "Backend API: ${BLUE}http://localhost:8000/api${NC}"
    echo -e "Admin Panel: ${BLUE}http://localhost:8000/admin${NC}"
    echo ""
    echo -e "Container Status:"
    docker ps --filter "name=completebytepos" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo -e "Logs: ${YELLOW}$COMPOSE_CMD logs -f${NC}"
    echo -e "Stop: ${YELLOW}./stop_production.sh${NC}"
    echo ""
}

release_backend() {
    print_info "Releasing backend only (frontend left as-is)..."
    if [ "$FORCE_DOWN" = true ]; then
        $COMPOSE_CMD stop backend 2>/dev/null || true
    fi
    build_service backend
    print_info "Starting db + backend..."
    $COMPOSE_CMD up -d db backend
    run_migrations
    print_success "Backend released"
}

release_frontend() {
    print_info "Releasing frontend only (backend left as-is)..."
    if [ "$FORCE_DOWN" = true ]; then
        $COMPOSE_CMD stop frontend 2>/dev/null || true
    fi
    if ! build_service frontend; then
        print_error "Frontend build failed. Backend was not touched and should still be running."
        exit 1
    fi
    print_info "Starting frontend..."
    $COMPOSE_CMD up -d --no-deps frontend
    print_success "Frontend released"
}

release_all() {
    print_info "Releasing full stack (backend, then frontend)..."
    if [ "$FORCE_DOWN" = true ]; then
        print_info "Stopping existing containers (--down)..."
        $COMPOSE_CMD down 2>/dev/null || true
    else
        print_info "Keeping running containers until new images are ready (no full down)..."
    fi

    build_service backend

    if ! build_service frontend; then
        print_error "Frontend build failed after backend image was built."
        print_info "Starting/keeping backend so the API stays available..."
        $COMPOSE_CMD up -d db backend
        run_migrations || true
        print_warning "Backend is up. Fix the frontend build, then run: ./run_production.sh --fe"
        exit 1
    fi

    print_info "Starting containers..."
    $COMPOSE_CMD up -d
    print_info "Waiting for services..."
    sleep 8
    run_migrations
    print_success "Full stack released"
}

main() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}CompleteBytePOS - Production Mode${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    parse_args "$@"
    check_docker
    cd "$PROJECT_ROOT"
    export DEBUG=False

    if [ "$CLEAR_CACHE" = true ]; then
        clear_docker_cache
    fi

    case "$TARGET" in
        be) release_backend ;;
        fe) release_frontend ;;
        all) release_all ;;
    esac

    show_status
}

main "$@"
