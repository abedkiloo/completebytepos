#!/bin/bash

###############################################################################
# CompleteBytePOS - UAT Run Script
# Runs the UAT stack on the same VPS as production (does not stop prod).
#   UI:  https://uat.omuwenga.com
#   API: https://api.uat.omuwenga.com
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_PROJECT="omuwenga-uat"
ENV_FILE=".env.uat"
BACKEND_CONTAINER="omuwenga-uat_backend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}CompleteBytePOS - UAT Mode${NC}"
echo -e "${BLUE}  uat.omuwenga.com  +  api.uat.omuwenga.com${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

compose() {
    $COMPOSE_CMD -p "$COMPOSE_PROJECT" --env-file "$ENV_FILE" -f docker-compose.yml "$@"
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

ensure_env_file() {
    cd "$PROJECT_ROOT"
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f ".env.uat.example" ]; then
            cp .env.uat.example "$ENV_FILE"
            print_warning "Created $ENV_FILE from .env.uat.example — set SECRET_KEY and DB password before use."
        else
            print_error "Missing $ENV_FILE. Copy .env.uat.example to $ENV_FILE."
            exit 1
        fi
    fi
}

env_value() {
    grep -E "^$1=" "$PROJECT_ROOT/$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '[:space:]'
}

port_in_use() {
    local port="$1"
    [ -z "$port" ] || [ "$port" = "0" ] && return 1
    if command -v ss >/dev/null 2>&1; then
        ss -tln 2>/dev/null | grep -qE "[:.]$port([[:space:]]|$)" && return 0
    fi
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 && return 0
    fi
    docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -qE "[:.]$port->" && return 0
    return 1
}

# Django talks to Postgres on the Docker network (db:5432).
# Host publish for UAT is 127.0.0.1:5435.
ensure_postgres_port() {
    local port
    port="$(env_value POSTGRES_PORT)"
    if [ -z "$port" ] || [ "$port" = "0" ] || [ "$port" = "5433" ]; then
        print_info "Setting POSTGRES_PORT=5435 in $ENV_FILE"
        local tmp
        tmp="$(mktemp)"
        if grep -qE '^POSTGRES_PORT=' "$PROJECT_ROOT/$ENV_FILE"; then
            awk -F= '/^POSTGRES_PORT=/{print "POSTGRES_PORT=5435"; next} {print}' "$PROJECT_ROOT/$ENV_FILE" > "$tmp"
        else
            cat "$PROJECT_ROOT/$ENV_FILE" > "$tmp"
            printf '\nPOSTGRES_PORT=5435\n' >> "$tmp"
        fi
        mv "$tmp" "$PROJECT_ROOT/$ENV_FILE"
        port=5435
    fi
}

check_required_ports() {
    local fe be pg
    fe="$(env_value FRONTEND_PORT)"; fe="${fe:-3100}"
    be="$(env_value BACKEND_PORT)"; be="${be:-8001}"
    pg="$(env_value POSTGRES_PORT)"; pg="${pg:-5435}"
    local busy=0
    if port_in_use "$fe"; then
        print_error "Frontend port $fe is already in use (needed for uat.omuwenga.com)."
        busy=1
    fi
    if port_in_use "$be"; then
        print_error "Backend port $be is already in use (needed for api.uat.omuwenga.com)."
        busy=1
    fi
    if port_in_use "$pg"; then
        print_error "Postgres host port $pg is already in use."
        print_info "See what holds it:  ss -tlnp | grep $pg   or   docker ps"
        busy=1
    fi
    if [ "$busy" = 1 ]; then
        print_info "See what holds the port:  ss -tlnp | grep -E '3100|8001|5435'   or   docker ps"
        exit 1
    fi
}

clear_docker_cache() {
    print_info "Clearing Docker build cache and Buildx cache..."
    docker builder prune -af 2>/dev/null || true
    docker buildx prune -af 2>/dev/null || true
    print_success "Docker cache cleared"
}

run_migrations() {
    print_info "Ensuring database migrations are up to date..."
    sleep 3

    if ! docker ps | grep -q "$BACKEND_CONTAINER"; then
        print_warning "Backend container not running, skipping migration check"
        return
    fi

    if docker exec "$BACKEND_CONTAINER" python manage.py makemigrations --noinput 2>/dev/null; then
        print_success "Migration files checked/created"
    else
        print_warning "makemigrations had issues (this is usually OK if no new migrations needed)"
    fi

    if docker exec "$BACKEND_CONTAINER" python manage.py migrate --noinput; then
        print_success "Database migrations applied"
    else
        print_error "Failed to run migrations!"
        print_info "Check backend logs: compose -p $COMPOSE_PROJECT logs backend"
        print_info "POSTGRES_PASSWORD in $ENV_FILE must match the UAT postgres volume."
        return 1
    fi
}

run_docker() {
    print_info "Building and starting Docker containers in UAT mode..."
    cd "$PROJECT_ROOT"
    export DEBUG=False

    print_info "Stopping existing UAT containers (production is left running)..."
    compose down 2>/dev/null || true
    docker rm -f omuwenga-uat_db omuwenga-uat_backend omuwenga-uat_frontend 2>/dev/null || true

    ensure_postgres_port
    check_required_ports

    if [[ "$*" == *"--clear-cache"* ]] || [[ "$*" == *"-c"* ]]; then
        clear_docker_cache
    else
        print_info "Clearing Docker Buildx cache..."
        docker buildx prune -f 2>/dev/null || true
    fi

    print_info "Building Docker images..."
    if ! DOCKER_BUILDKIT=1 compose build --no-cache --progress=plain; then
        print_warning "Build with BuildKit failed, trying without BuildKit..."
        DOCKER_BUILDKIT=0 compose build --no-cache
    fi

    print_info "Starting containers..."
    compose up -d

    print_info "Waiting for services to be ready..."
    sleep 10

    run_migrations

    print_success "UAT containers started!"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}UAT server started!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Frontend:     ${BLUE}http://127.0.0.1:3100${NC}  →  ${BLUE}https://uat.omuwenga.com${NC}"
    echo -e "API (nginx):  ${BLUE}http://127.0.0.1:3100/api${NC}"
    echo -e "API host:     ${BLUE}http://127.0.0.1:8001${NC}  →  ${BLUE}https://api.uat.omuwenga.com${NC}"
    echo -e "Admin:        ${BLUE}https://api.uat.omuwenga.com/admin${NC}"
    echo ""
    echo -e "Container Status:"
    docker ps --filter "name=omuwenga-uat" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo -e "To view logs: ${YELLOW}docker compose -p $COMPOSE_PROJECT --env-file $ENV_FILE logs -f${NC}"
    echo -e "To stop:      ${YELLOW}./stop_uat.sh${NC}  (does not stop production)"
    echo ""
}

main() {
    if [[ "$*" == *"--help"* ]] || [[ "$*" == *"-h"* ]]; then
        echo "Usage: ./run_uat.sh [OPTIONS]"
        echo ""
        echo "Starts the UAT stack (omuwenga-uat) without stopping production."
        echo "  UI:  https://uat.omuwenga.com"
        echo "  API: https://api.uat.omuwenga.com"
        echo ""
        echo "Options:"
        echo "  --clear-cache, -c    Clear all Docker caches before building"
        echo "  --help, -h           Show this help message"
        echo ""
        echo "Example:"
        echo "  ./run_uat.sh --clear-cache"
        exit 0
    elif [[ "$*" == *"--no-docker"* ]]; then
        print_warning "Non-Docker UAT mode is not supported"
        print_info "Please use Docker for UAT: ./run_uat.sh"
        exit 1
    else
        check_docker
        ensure_env_file
        run_docker "$@"
    fi
}

main "$@"
