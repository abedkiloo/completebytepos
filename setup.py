#!/usr/bin/env python3
"""
Setup script for CompleteBytePOS
Supports both Docker and local setup
"""
import os
import sys
import subprocess
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / 'be'
FRONTEND_DIR = PROJECT_ROOT / 'fe'

def run_command(command, cwd=None, check=True, show_output=True):
    """Run a shell command"""
    if show_output:
        print(f"Running: {' '.join(command) if isinstance(command, list) else command}")
    try:
        result = subprocess.run(
            command, 
            cwd=cwd, 
            check=check, 
            capture_output=not show_output,
            text=True, 
            shell=isinstance(command, str),
            timeout=600
        )
        if show_output:
            if result.stdout:
                print(result.stdout)
            if result.stderr and result.returncode != 0:
                print(result.stderr, file=sys.stderr)
        return result
    except subprocess.TimeoutExpired:
        print(f"Command timed out after 10 minutes")
        raise
    except Exception as e:
        print(f"Error running command: {e}")
        raise

def check_docker():
    """Check if Docker is available"""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            result2 = subprocess.run(['docker', 'compose', 'version'], capture_output=True, text=True)
            if result2.returncode != 0:
                result2 = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True)
            return result2.returncode == 0
    except:
        pass
    return False

def setup_with_docker():
    """Set up using Docker"""
    print("\n" + "="*50)
    print("Setting up CompleteBytePOS with Docker")
    print("="*50)
    
    # Check Docker
    if not check_docker():
        print("❌ Docker is not installed or not running!")
        print("Please install Docker from: https://www.docker.com/get-started")
        return False
    
    print("✅ Docker is available")
    
    # Stop existing containers
    print("\nStopping existing containers...")
    run_command("docker compose down -v 2>/dev/null || docker-compose down -v 2>/dev/null || true", cwd=PROJECT_ROOT, check=False)
    
    # Build images
    print("\nBuilding Docker images...")
    print("This may take several minutes on first run...")
    run_command("docker compose build --no-cache || docker-compose build --no-cache", cwd=PROJECT_ROOT)
    
    # Start containers
    print("\nStarting containers...")
    run_command("docker compose up -d || docker-compose up -d", cwd=PROJECT_ROOT)
    
    # Wait for backend to be ready
    print("\nWaiting for backend to be ready...")
    import time
    time.sleep(20)  # Give backend time to start and run migrations
    print("✅ Proceeding with setup...")
    
    # Determine compose command
    compose_cmd = "docker compose" if subprocess.run(['docker', 'compose', 'version'], capture_output=True).returncode == 0 else "docker-compose"
    
    # Run migrations
    print("\nRunning database migrations...")
    run_command(f"{compose_cmd} exec -T backend python manage.py makemigrations --noinput", cwd=PROJECT_ROOT, check=False)
    run_command(f"{compose_cmd} exec -T backend python manage.py migrate --noinput", cwd=PROJECT_ROOT)
    
    # Create superuser
    print("\nCreating superuser...")
    # Use heredoc for better script handling
    superuser_script = "from django.contrib.auth import get_user_model; User = get_user_model(); user, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True, 'is_active': True}); user.set_password('admin'); user.save(); print('Superuser created/updated: username=admin, password=admin')"
    run_command(f"{compose_cmd} exec -T backend python manage.py shell -c \"{superuser_script}\"", cwd=PROJECT_ROOT, check=False)
    
    # Initialize system
    print("\nInitializing system data...")
    run_command(f"{compose_cmd} exec -T backend python manage.py init_permissions", cwd=PROJECT_ROOT, check=False)
    run_command(f"{compose_cmd} exec -T backend python manage.py init_modules", cwd=PROJECT_ROOT, check=False)
    run_command(f"{compose_cmd} exec -T backend python manage.py init_accounts", cwd=PROJECT_ROOT, check=False)
    run_command(f"{compose_cmd} exec -T backend python manage.py init_expense_categories", cwd=PROJECT_ROOT, check=False)
    run_command(f"{compose_cmd} exec -T backend python manage.py setup_new_organization", cwd=PROJECT_ROOT, check=False)
    
    print("\n✅ Docker setup complete!")
    print("\nServices are running:")
    print("  Backend:  http://localhost:8000")
    print("  Frontend: http://localhost:3000")
    print("\nLogin credentials:")
    print("  Username: admin")
    print("  Password: admin")
    print("\nTo view logs: docker compose logs -f")
    print("To stop: docker compose down")
    
    return True

def setup_backend():
    """Set up Django backend (local)"""
    print("\n" + "="*50)
    print("Setting up Django Backend")
    print("="*50)
    
    # Check if virtual environment exists
    venv_path = BACKEND_DIR / 'venv'
    if not venv_path.exists():
        print("Creating virtual environment...")
        run_command([sys.executable, '-m', 'venv', 'venv'], cwd=BACKEND_DIR)
    
    # Determine Python executable
    if sys.platform == 'win32':
        python_exe = BACKEND_DIR / 'venv' / 'Scripts' / 'python.exe'
        pip_exe = BACKEND_DIR / 'venv' / 'Scripts' / 'pip.exe'
    else:
        python_exe = BACKEND_DIR / 'venv' / 'bin' / 'python'
        pip_exe = BACKEND_DIR / 'venv' / 'bin' / 'pip'
    
    # Install requirements
    print("\nInstalling Python dependencies...")
    print("This may take a few minutes...")
    run_command([str(pip_exe), 'install', '--upgrade', 'pip'], cwd=BACKEND_DIR, check=False, show_output=False)
    run_command([str(pip_exe), 'install', '-r', 'requirements.txt'], cwd=BACKEND_DIR, show_output=False)
    print("✅ Python dependencies installed")
    
    # Check if .env exists
    env_file = BACKEND_DIR / '.env'
    if not env_file.exists():
        print("\nCreating .env file...")
        env_content = """# Django Settings
SECRET_KEY=django-insecure-change-this-in-production
DEBUG=True

# Database Configuration (SQLite - no config needed)
# For MySQL/PostgreSQL, uncomment and configure:
# DB_NAME=completebytepos
# DB_USER=root
# DB_PASSWORD=
# DB_HOST=localhost
# DB_PORT=3306
"""
        env_file.write_text(env_content)
        print("Created .env file. Using SQLite database (no configuration needed).")
    
    # Make migrations for all apps
    print("\nCreating database migrations...")
    result = run_command([str(python_exe), 'manage.py', 'makemigrations'], cwd=BACKEND_DIR, check=False, show_output=True)
    if result.returncode == 0:
        output = result.stdout if hasattr(result, 'stdout') else ''
        if 'No changes detected' in output:
            print("No new migrations needed.")
        else:
            print("✅ Migrations created successfully.")
    else:
        print("⚠️  Warning: Some migrations may have failed, continuing...")
    
    # Run migrations
    print("\nRunning migrations...")
    run_command([str(python_exe), 'manage.py', 'migrate', '--noinput'], cwd=BACKEND_DIR, show_output=True)
    print("✅ Migrations applied")
    
    # Create superuser (non-interactive) - always update password
    print("\nSetting up superuser (admin/admin)...")
    create_superuser_script = """
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
    print('Superuser password updated: username=admin, password=admin')
except User.DoesNotExist:
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created: username=admin, password=admin')
"""
    result = run_command(
        [str(python_exe), 'manage.py', 'shell', '-c', create_superuser_script],
        cwd=BACKEND_DIR,
        check=False,
        show_output=True
    )
    if result.returncode != 0:
        print("⚠️  Warning: Superuser creation may have failed. You can create it manually with:")
        print(f"  {python_exe} manage.py createsuperuser")
    else:
        print("✅ Superuser configured")
    
    # Initialize chart of accounts
    print("\nInitializing chart of accounts...")
    result = run_command(
        [str(python_exe), 'manage.py', 'init_accounts'],
        cwd=BACKEND_DIR,
        check=False,
        show_output=True
    )
    if result.returncode != 0:
        print("⚠️  Warning: Chart of accounts initialization may have failed.")
        print("You can run 'python manage.py init_accounts' manually later")
    else:
        print("✅ Chart of accounts initialized")
    
    # Initialize module settings
    print("\nInitializing module settings...")
    result = run_command(
        [str(python_exe), 'manage.py', 'init_modules'],
        cwd=BACKEND_DIR,
        check=False,
        show_output=True
    )
    if result.returncode != 0:
        print("⚠️  Warning: Module settings initialization may have failed.")
        print("You can run 'python manage.py init_modules' manually later")
    else:
        print("✅ Module settings initialized")
    
    # Initialize permissions and roles
    print("\nInitializing permissions and roles...")
    result = run_command(
        [str(python_exe), 'manage.py', 'init_permissions'],
        cwd=BACKEND_DIR,
        check=False,
        show_output=True
    )
    if result.returncode != 0:
        print("⚠️  Warning: Permissions and roles initialization may have failed.")
        print("You can run 'python manage.py init_permissions' manually later")
    else:
        print("✅ Permissions and roles initialized")
    
    print("\n✅ Backend setup complete!")

def setup_frontend():
    """Set up React frontend"""
    print("\n" + "="*50)
    print("Setting up React Frontend")
    print("="*50)
    
    # Check if node_modules exists
    node_modules = FRONTEND_DIR / 'node_modules'
    if not node_modules.exists():
        print("Installing Node dependencies...")
        print("This may take a few minutes...")
        run_command(['npm', 'install'], cwd=FRONTEND_DIR, show_output=False)
        print("✅ Node dependencies installed")
    else:
        print("✅ Node dependencies already installed")
    
    print("\n✅ Frontend setup complete!")

def main():
    """Main setup function"""
    print("="*50)
    print("CompleteBytePOS Setup")
    print("="*50)
    print("\nThis script will set up CompleteBytePOS for you.")
    print("\nChoose setup method:")
    print("1. Docker (Recommended - containers for backend and frontend)")
    print("2. Local (Traditional - installs locally)")
    print()
    
    choice = input("Enter choice (1 or 2, default: 1): ").strip() or "1"
    
    if choice == "1":
        if setup_with_docker():
            return
        else:
            print("\n⚠️  Docker setup failed. Falling back to local setup...")
            choice = "2"
    
    if choice == "2":
        setup_backend()
        setup_frontend()
        print("\n" + "="*50)
        print("Setup Complete!")
        print("="*50)
        print("\nTo start the application:")
        print("  python run.py")
        print("\nLogin credentials:")
        print("  Username: admin")
        print("  Password: admin")
    else:
        print("Invalid choice. Please run the script again.")

if __name__ == '__main__':
    main()
