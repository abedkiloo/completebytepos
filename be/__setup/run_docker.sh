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
echo -e "${BLUE}  Dev:  ./run_docker.sh${NC}"
echo -e "${BLUE}  Prod: ./run_docker.sh --prod  (React build + nginx)${NC}"
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

# Production: static React build + nginx (see fe/Dockerfile, docs/DEPLOYMENT.md)
start_containers_prod() {
    print_info "Building and starting Docker containers in PRODUCTION mode..."
    print_info "Frontend: npm run build → nginx (static files, NOT react-scripts start)"
    cd "$PROJECT_ROOT"

    COMPOSE_FILE="docker-compose.yml"

    if [ "$1" == "--rebuild" ]; then
        print_info "Rebuilding production images from scratch..."
        $COMPOSE_CMD -f $COMPOSE_FILE build --no-cache
    else
        $COMPOSE_CMD -f $COMPOSE_FILE build
    fi

    $COMPOSE_CMD -f $COMPOSE_FILE up -d

    print_info "Waiting for services to be ready..."
    sleep 8

    if docker ps | grep -q completebytepos_backend && docker ps | grep -q completebytepos_frontend; then
        print_success "Production containers are running"
        run_migrations
    else
        print_error "Some containers failed to start!"
        $COMPOSE_CMD -f $COMPOSE_FILE logs
        exit 1
    fi
}

show_status_prod() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Production stack is up${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Frontend (nginx + React build): ${BLUE}http://localhost:3000${NC}"
    echo -e "Backend API (via nginx proxy):  ${BLUE}http://localhost:3000/api${NC}"
    echo -e "Admin Panel:                  ${BLUE}http://localhost:8000/admin${NC}"
    echo ""
    echo -e "${YELLOW}This is NOT the dev server.${NC} UI changes require: ${BLUE}./run_docker.sh --prod --rebuild${NC}"
    echo ""
    docker ps --filter "name=completebytepos" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo -e "Logs: ${YELLOW}$COMPOSE_CMD -f docker-compose.yml logs -f${NC}"
    echo -e "Stop: ${YELLOW}./stop_docker.sh${NC}"
    echo ""

    if curl -sI http://localhost:3000/ 2>/dev/null | grep -qi nginx; then
        print_success "Frontend is nginx serving the production build"
    elif curl -s http://localhost:3000/ >/dev/null 2>&1; then
        print_success "Frontend is responding"
    else
        print_warning "Frontend may still be starting"
    fi
}

# Build and start (development)
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
        
        # Ensure migrations are run (safety check)
        run_migrations
    else
        print_error "Some containers failed to start!"
        print_info "Check logs with: $COMPOSE_CMD -f $COMPOSE_FILE logs"
        exit 1
    fi
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
        print_info "Check backend logs: $COMPOSE_CMD -f docker-compose.dev.yml logs backend"
        return 1
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
        
        # Bootstrap uses create_users (3 users only; no demo catalog).
        # Heavy populate_test_data is opt-in only — see docs/POS_UX_ROLES_AND_TESTING.md
        print_info "Bootstrap: admin/manager/sales (via create_users on container start)"
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

# Populate test data (only in Docker dev mode)
populate_test_data() {
    print_info "Checking if test data should be populated..."
    
    # Wait a bit more for backend to be fully ready
    sleep 3
    
    # Check if database is empty (no users exist except potential superuser)
    # Use a more robust check that handles errors gracefully
    USER_COUNT=0
    if docker exec completebytepos_backend python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.count())" 2>/dev/null | grep -qE '^[0-9]+$'; then
        USER_COUNT=$(docker exec completebytepos_backend python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.count())" 2>/dev/null | grep -E '^[0-9]+$' || echo "0")
    fi
    
    # Convert to integer for comparison
    USER_COUNT=${USER_COUNT:-0}
    
    print_info "Skipping auto populate_test_data (use only for load testing)."
    print_info "  docker exec completebytepos_backend python manage.py populate_test_data --users 5 --products 50"
    print_info "Fresh installs already have: admin, manager, sales + 3 demo products."
}

ensure_env_file() {
    cd "$PROJECT_ROOT"
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_warning "Created .env from .env.example — review passwords before production."
        else
            print_error "Missing .env file. Copy .env.example to .env and set POSTGRES_PASSWORD."
            exit 1
        fi
    fi
}

# Main
main() {
    check_docker
    ensure_env_file
    stop_existing

    PROD_MODE=false
    REBUILD=false
    for arg in "$@"; do
        case "$arg" in
            --prod|--production) PROD_MODE=true ;;
            --rebuild) REBUILD=true ;;
        esac
    done

    if [ "$PROD_MODE" = true ]; then
        if [ "$REBUILD" = true ]; then
            start_containers_prod --rebuild
        else
            start_containers_prod
        fi
        show_status_prod
    else
        if [ "$REBUILD" = true ]; then
            start_containers --rebuild
        else
            start_containers
        fi
        show_status
    fi
}

trap 'print_info "Script interrupted. Use ./stop_docker.sh to stop containers."' INT TERM
main "$@"
