#!/bin/bash

###############################################################################
# CompleteBytePOS - Fresh Installation Script with Docker
# This script performs a complete fresh installation using Docker containers
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/be"
FRONTEND_DIR="$PROJECT_ROOT/fe"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}CompleteBytePOS - Fresh Installation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        print_info "Please install Docker from: https://www.docker.com/get-started"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed!"
        print_info "Please install Docker Compose"
        exit 1
    fi
    
    print_success "Docker and Docker Compose are installed"
}

# Stop and remove existing containers
cleanup_containers() {
    print_info "Cleaning up existing containers..."
    docker-compose down -v 2>/dev/null || docker compose down -v 2>/dev/null || true
    print_success "Containers cleaned up"
}

# Build Docker images
build_images() {
    print_info "Building Docker images..."
    
    if docker compose version &> /dev/null; then
        docker compose build --no-cache
    else
        docker-compose build --no-cache
    fi
    
    print_success "Docker images built"
}

# Initialize database and setup
setup_database() {
    print_info "Setting up database and initializing system..."
    
    # Wait for backend to be ready
    print_info "Waiting for backend to be ready..."
    sleep 15
    
    # Check if backend is responding (curl may not be available, so just wait)
    print_info "Waiting for backend to initialize..."
    # Additional wait time for migrations and setup
    sleep 5
    
    # Run setup commands in backend container
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    # Create superuser
    print_info "Creating superuser..."
    $COMPOSE_CMD exec -T backend python manage.py shell << 'EOF' || true
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    user = User.objects.get(username='admin')
    user.set_password('admin')
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.email = 'admin@example.com'
    user.save()
    print('Superuser updated: username=admin, password=admin')
except User.DoesNotExist:
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created: username=admin, password=admin')
EOF
    
    # Initialize permissions and roles
    print_info "Initializing permissions and roles..."
    $COMPOSE_CMD exec -T backend python manage.py init_permissions || print_warning "Permissions initialization may have issues"
    
    # Initialize modules
    print_info "Initializing modules and features..."
    $COMPOSE_CMD exec -T backend python manage.py init_modules || print_warning "Module initialization may have issues"
    
    # Initialize accounting accounts
    print_info "Initializing accounting accounts..."
    $COMPOSE_CMD exec -T backend python manage.py init_accounts || print_warning "Accounts initialization may have issues"
    
    # Initialize expense categories
    print_info "Initializing expense categories..."
    $COMPOSE_CMD exec -T backend python manage.py init_expense_categories || print_warning "Expense categories initialization may have issues"
    
    # Setup new organization
    print_info "Setting up organization..."
    $COMPOSE_CMD exec -T backend python manage.py setup_new_organization || print_warning "Organization setup may have issues"
    
    print_success "Database setup complete"
}

# Populate test data (optional)
populate_test_data() {
    print_info "Populating test data..."
    
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    $COMPOSE_CMD exec -T backend python manage.py populate_test_data --users 20 --customers 100 --products 1000 || print_warning "Test data population may have issues"
    
    print_success "Test data populated"
}

# Start containers
start_containers() {
    print_info "Starting Docker containers..."
    
    if docker compose version &> /dev/null; then
        docker compose up -d
    else
        docker-compose up -d
    fi
    
    print_success "Containers started"
}

# Main execution
main() {
    # Check for --yes flag for non-interactive mode
    NON_INTERACTIVE=false
    INCLUDE_TEST_DATA=false
    
    for arg in "$@"; do
        case $arg in
            --yes|-y)
                NON_INTERACTIVE=true
                ;;
            --test-data)
                INCLUDE_TEST_DATA=true
                ;;
            *)
                ;;
        esac
    done
    
    if [ "$NON_INTERACTIVE" = false ]; then
        print_warning "This will perform a complete fresh installation using Docker!"
        print_warning "This will:"
        print_warning "  - Build Docker images for backend and frontend"
        print_warning "  - Run all database migrations"
        print_warning "  - Create superuser (admin/admin)"
        print_warning "  - Initialize all system data"
        print_warning "  - Start both containers"
        echo ""
        read -p "Do you want to continue? (yes/no): " confirm
        
        if [ "$confirm" != "yes" ]; then
            print_info "Installation cancelled"
            exit 0
        fi
    else
        print_info "Running in non-interactive mode..."
    fi
    
    # Check Docker
    check_docker
    
    # Cleanup
    cleanup_containers
    
    # Build images
    build_images
    
    # Start containers
    start_containers
    
    # Setup database
    setup_database
    
    # Handle test data
    if [ "$NON_INTERACTIVE" = false ]; then
        echo ""
        read -p "Do you want to populate test data (20 users, 100 customers, 1000 products)? (yes/no): " test_data
        if [ "$test_data" = "yes" ]; then
            INCLUDE_TEST_DATA=true
        fi
    fi
    
    if [ "$INCLUDE_TEST_DATA" = true ]; then
        populate_test_data
    else
        print_info "Skipping test data population"
    fi
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Services are running in Docker containers:"
    echo -e "  Backend:  ${BLUE}http://localhost:8000${NC}"
    echo -e "  Frontend: ${BLUE}http://localhost:3000${NC}"
    echo ""
    echo -e "Login credentials:"
    echo -e "  Username: ${YELLOW}admin${NC}"
    echo -e "  Password: ${YELLOW}admin${NC}"
    echo ""
    echo -e "To view logs:"
    echo -e "  ${BLUE}docker compose logs -f${NC} (or docker-compose logs -f)"
    echo ""
    echo -e "To stop containers:"
    echo -e "  ${BLUE}docker compose down${NC} (or docker-compose down)"
    echo ""
}

# Run main function with all arguments
main "$@"
