#!/bin/bash

###############################################################################
# CompleteBytePOS Production Run Script
# This script builds and runs the application in production mode
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

# Configuration
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}
WORKERS=${WORKERS:-4}
THREADS=${THREADS:-2}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}CompleteBytePOS - Production Mode${NC}"
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

# Check if virtual environment exists
check_backend_setup() {
    print_info "Checking backend setup..."
    
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        print_error "Backend virtual environment not found!"
        print_info "Please run: cd $BACKEND_DIR && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
    
    # Activate virtual environment
    source "$BACKEND_DIR/venv/bin/activate"
    
    # Check if gunicorn is installed
    if ! python -c "import gunicorn" 2>/dev/null; then
        print_warning "Gunicorn not found. Installing production dependencies..."
        pip install gunicorn whitenoise
    fi
    
    print_success "Backend setup verified"
}

# Check if node_modules exists
check_frontend_setup() {
    print_info "Checking frontend setup..."
    
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        print_error "Frontend node_modules not found!"
        print_info "Please run: cd $FRONTEND_DIR && npm install"
        exit 1
    fi
    
    print_success "Frontend setup verified"
}

# Set production environment variables
setup_environment() {
    print_info "Setting up production environment..."
    
    export DEBUG=False
    export DJANGO_SETTINGS_MODULE=config.settings
    
    # Check if .env file exists
    if [ -f "$BACKEND_DIR/.env" ]; then
        print_info "Loading environment variables from .env file"
        export $(cat "$BACKEND_DIR/.env" | grep -v '^#' | xargs)
    else
        print_warning ".env file not found. Using defaults."
        print_warning "Create a .env file in $BACKEND_DIR for production settings"
    fi
    
    # Ensure DEBUG is False in production
    export DEBUG=False
    
    print_success "Environment configured"
}

# Build React frontend for production
build_frontend() {
    print_info "Building React frontend for production..."
    
    cd "$FRONTEND_DIR"
    
    # Check if build directory exists and is recent
    if [ -d "build" ]; then
        print_info "Build directory exists. Rebuilding..."
    fi
    
    # Build React app
    npm run build
    
    if [ $? -ne 0 ]; then
        print_error "Frontend build failed!"
        exit 1
    fi
    
    print_success "Frontend built successfully"
    cd "$PROJECT_ROOT"
}

# Setup database with migrations and initial data
setup_database() {
    print_info "Setting up database..."
    
    cd "$BACKEND_DIR"
    source venv/bin/activate
    
    # Step 1: Create migrations
    print_info "Creating migrations..."
    python manage.py makemigrations --noinput 2>&1 | grep -v "NodeNotFoundError" || true
    
    # Step 2: Run migrations
    print_info "Running migrations..."
    python manage.py migrate --noinput
    
    if [ $? -ne 0 ]; then
        print_error "Migrations failed!"
        exit 1
    fi
    
    print_success "Migrations completed"
    
    # Step 3: Check if superuser exists, create/update if needed
    print_info "Checking superuser..."
    python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    user = User.objects.get(username='admin')
    # Always update password to ensure it's correct
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
    
    # Step 4: Initialize modules (idempotent - always run to ensure they're set up)
    print_info "Initializing modules..."
    python manage.py init_modules 2>&1 | grep -v "NodeNotFoundError" || true
    
    # Step 5: Initialize accounting accounts (idempotent - always run)
    print_info "Initializing accounting accounts..."
    python manage.py init_accounts 2>&1 | grep -v "NodeNotFoundError" || true
    
    # Step 6: Initialize expense categories (idempotent - always run)
    print_info "Initializing expense categories..."
    python manage.py init_expense_categories 2>&1 | grep -v "NodeNotFoundError" || true
    
    # Step 7: Create default tenant if needed (for multi-tenant support)
    print_info "Setting up default tenant..."
    python manage.py shell << 'EOF'
from settings.models import Tenant
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    tenant = Tenant.objects.get(code='DEFAULT')
    print(f'Default tenant already exists: {tenant.name}')
except Tenant.DoesNotExist:
    superuser = User.objects.filter(is_superuser=True).first()
    if superuser:
        tenant = Tenant.objects.create(
            name='CompleteByte Business',
            code='DEFAULT',
            country='Kenya',
            owner=superuser,
            created_by=superuser
        )
        print(f'Default tenant created: {tenant.name}')
    else:
        print('No superuser found, skipping tenant creation')
EOF
    
    print_success "Database setup completed"
    cd "$PROJECT_ROOT"
}

# Collect static files
collect_static() {
    print_info "Collecting static files..."
    
    cd "$BACKEND_DIR"
    source venv/bin/activate
    
    python manage.py collectstatic --noinput --clear
    
    if [ $? -ne 0 ]; then
        print_error "Static files collection failed!"
        exit 1
    fi
    
    print_success "Static files collected"
    cd "$PROJECT_ROOT"
}

# Copy React build to Django static files (if serving via Django)
copy_react_build() {
    print_info "Copying React build to Django static files..."
    
    # Create static root if it doesn't exist
    mkdir -p "$BACKEND_DIR/staticfiles"
    
    # Copy React build to static files
    if [ -d "$FRONTEND_DIR/build" ]; then
        cp -r "$FRONTEND_DIR/build"/* "$BACKEND_DIR/staticfiles/" 2>/dev/null || true
        print_success "React build copied to static files"
    else
        print_warning "React build directory not found. Skipping copy."
    fi
}

# Start Gunicorn server
start_gunicorn() {
    print_info "Starting Gunicorn server on port $BACKEND_PORT..."
    
    cd "$BACKEND_DIR"
    source venv/bin/activate
    
    # Create logs directory if it doesn't exist
    mkdir -p logs
    
    # Start gunicorn
    gunicorn config.wsgi:application \
        --bind 0.0.0.0:$BACKEND_PORT \
        --workers $WORKERS \
        --threads $THREADS \
        --timeout 120 \
        --access-logfile logs/access.log \
        --error-logfile logs/error.log \
        --log-level info \
        --capture-output \
        --daemon \
        --pid gunicorn.pid
    
    if [ $? -eq 0 ]; then
        print_success "Gunicorn started (PID: $(cat gunicorn.pid))"
    else
        print_error "Failed to start Gunicorn!"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
}

# Stop existing servers
stop_servers() {
    print_info "Stopping existing servers..."
    
    # Stop gunicorn if running
    if [ -f "$BACKEND_DIR/gunicorn.pid" ]; then
        kill $(cat "$BACKEND_DIR/gunicorn.pid") 2>/dev/null || true
        rm -f "$BACKEND_DIR/gunicorn.pid"
        print_info "Stopped existing Gunicorn process"
    fi
    
    # Kill any process on backend port
    lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
    
    # Kill any process on frontend port
    lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
    
    sleep 2
}

# Main execution
main() {
    # Stop any existing servers
    stop_servers
    
    # Setup checks
    check_backend_setup
    check_frontend_setup
    setup_environment
    
    # Production build steps
    build_frontend
    setup_database
    collect_static
    copy_react_build
    
    # Start production server
    start_gunicorn
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Production server started!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Backend API: ${BLUE}http://localhost:$BACKEND_PORT/api${NC}"
    echo -e "Admin Panel: ${BLUE}http://localhost:$BACKEND_PORT/admin${NC}"
    echo -e "Static Files: ${BLUE}http://localhost:$BACKEND_PORT/static/${NC}"
    echo ""
    echo -e "Gunicorn PID: ${YELLOW}$(cat $BACKEND_DIR/gunicorn.pid)${NC}"
    echo -e "Workers: ${YELLOW}$WORKERS${NC}"
    echo -e "Threads per worker: ${YELLOW}$THREADS${NC}"
    echo ""
    echo -e "Logs:"
    echo -e "  Access: ${BLUE}$BACKEND_DIR/logs/access.log${NC}"
    echo -e "  Error:  ${BLUE}$BACKEND_DIR/logs/error.log${NC}"
    echo ""
    echo -e "To stop the server: ${YELLOW}./stop_production.sh${NC} or ${YELLOW}kill \$(cat $BACKEND_DIR/gunicorn.pid)${NC}"
    echo ""
}

# Handle script termination
trap 'print_info "Script interrupted. Use ./stop_production.sh to stop the server."' INT TERM

# Run main function
main
