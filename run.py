#!/usr/bin/env python3
"""
Run script for CompleteBytePOS
Starts both Django backend and React frontend servers.
"""
import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / 'be'
FRONTEND_DIR = PROJECT_ROOT / 'fe'

# Store process references
processes = []

def signal_handler(sig, frame):
    """Handle Ctrl+C to stop all processes"""
    print("\n\nStopping servers...")
    for process in processes:
        try:
            process.terminate()
        except:
            pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def kill_port(port):
    """Kill process using a specific port"""
    import socket
    try:
        if sys.platform == 'win32':
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) > 4:
                        pid = parts[-1]
                        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
        else:
            result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-9', pid], capture_output=True)
                    except:
                        pass
    except Exception:
        pass

def start_backend():
    """Start Django backend server"""
    print("Starting Django backend server...")
    
    # Kill any process using port 8000
    kill_port(8000)
    time.sleep(1)
    
    # Determine Python executable
    if sys.platform == 'win32':
        python_exe = BACKEND_DIR / 'venv' / 'Scripts' / 'python.exe'
    else:
        python_exe = BACKEND_DIR / 'venv' / 'bin' / 'python'
    
    process = subprocess.Popen(
        [str(python_exe), 'manage.py', 'runserver', '0.0.0.0:8000'],
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    processes.append(process)
    
    # Print output in real-time
    def print_output():
        for line in process.stdout:
            print(f"[Backend] {line}", end='')
    
    import threading
    thread = threading.Thread(target=print_output, daemon=True)
    thread.start()
    
    return process

def start_frontend():
    """Start React frontend server"""
    print("Starting React frontend server...")
    
    # Kill any process using port 3000
    kill_port(3000)
    time.sleep(1)
    
    # Check if node_modules exists
    if not (FRONTEND_DIR / 'node_modules').exists():
        print("⚠️  node_modules not found. Run 'npm install' first.")
        return None
    
    process = subprocess.Popen(
        ['npm', 'start'],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env={**os.environ, 'BROWSER': 'none'}  # Don't auto-open browser
    )
    
    processes.append(process)
    
    # Print output in real-time
    def print_output():
        for line in process.stdout:
            print(f"[Frontend] {line}", end='')
    
    import threading
    thread = threading.Thread(target=print_output, daemon=True)
    thread.start()
    
    return process

def setup_database():
    """Set up database with migrations and initial data"""
    print("Setting up database...")
    
    # Determine Python executable
    if sys.platform == 'win32':
        python_exe = BACKEND_DIR / 'venv' / 'Scripts' / 'python.exe'
    else:
        python_exe = BACKEND_DIR / 'venv' / 'bin' / 'python'
    
    db_file = BACKEND_DIR / 'db.sqlite3'
    is_new_db = not db_file.exists()
    
    # Step 1: Create migrations
    print("  Creating migrations...")
    result = subprocess.run(
        [str(python_exe), 'manage.py', 'makemigrations'],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        if 'No changes detected' not in result.stdout:
            print("  ✅ New migrations created")
        else:
            print("  ✓ No new migrations needed")
    else:
        print("  ⚠️  Migration creation warning (continuing...)")
    
    # Step 2: Run migrations
    print("  Running migrations...")
    result = subprocess.run(
        [str(python_exe), 'manage.py', 'migrate', '--noinput'],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("  ✅ Migrations applied")
    else:
        print("  ❌ Migration failed!")
        if result.stderr:
            print(f"  Error: {result.stderr[:500]}")
        if result.stdout:
            print(f"  Output: {result.stdout[:500]}")
        return False
    
    # Step 3: Create superuser if it doesn't exist (always check, not just for new DB)
    print("  Checking superuser...")
    create_superuser_script = """
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
"""
    result = subprocess.run(
        [str(python_exe), 'manage.py', 'shell', '-c', create_superuser_script],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("  ✅ Superuser configured")
    else:
        print("  ⚠️  Superuser creation warning")
        if result.stderr:
            print(f"  Error: {result.stderr[:200]}")
    
    # Step 4: Initialize modules (idempotent - safe to run multiple times)
    # Always run these initialization commands - they're idempotent
    print("  Initializing modules...")
    result = subprocess.run(
        [str(python_exe), 'manage.py', 'init_modules'],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("  ✅ Modules initialized")
    else:
        print("  ⚠️  Module initialization warning")
        if result.stderr:
            print(f"  Error: {result.stderr[:200]}")
    
    # Step 5: Initialize accounting accounts (idempotent)
    print("  Initializing accounting accounts...")
    result = subprocess.run(
        [str(python_exe), 'manage.py', 'init_accounts'],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("  ✅ Accounting accounts initialized")
    else:
        print("  ⚠️  Accounts initialization warning")
        if result.stderr:
            print(f"  Error: {result.stderr[:200]}")
    
    # Step 6: Initialize expense categories (idempotent)
    print("  Initializing expense categories...")
    result = subprocess.run(
        [str(python_exe), 'manage.py', 'init_expense_categories'],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("  ✅ Expense categories initialized")
    else:
        print("  ⚠️  Expense categories warning")
        if result.stderr:
            print(f"  Error: {result.stderr[:200]}")
    
    # Step 7: Create default tenant if needed (for multi-tenant support)
    # Always check, not just for new DB, in case tenant was deleted
    print("  Checking default tenant...")
    create_tenant_script = """
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
"""
    result = subprocess.run(
        [str(python_exe), 'manage.py', 'shell', '-c', create_tenant_script],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("  ✅ Default tenant configured")
    else:
        print("  ⚠️  Tenant creation warning")
        if result.stderr:
            print(f"  Error: {result.stderr[:200]}")
    
    print("✅ Database setup complete!")
    return True

def check_dependencies():
    """Check if required dependencies are installed"""
    print("Checking dependencies...")
    
    # Check backend
    venv_path = BACKEND_DIR / 'venv'
    if not venv_path.exists():
        print("❌ Backend virtual environment not found!")
        print("   Run: python setup.py")
        return False
    
    # Check frontend
    node_modules = FRONTEND_DIR / 'node_modules'
    if not node_modules.exists():
        print("❌ Frontend node_modules not found!")
        print("   Run: python setup.py")
        return False
    
    # Setup database (migrations, initial data)
    if not setup_database():
        return False
    
    print("✅ Dependencies check passed")
    return True

def main():
    """Main run function"""
    print("="*50)
    print("CompleteBytePOS - Starting Servers")
    print("="*50)
    print()
    
    if not check_dependencies():
        sys.exit(1)
    
    print("\nStarting servers...")
    print("Backend: http://localhost:8000")
    print("Frontend: http://localhost:3000")
    print("\nPress Ctrl+C to stop all servers\n")
    
    try:
        backend_process = start_backend()
        time.sleep(2)  # Wait a bit for backend to start
        
        frontend_process = start_frontend()
        time.sleep(2)  # Wait a bit for frontend to start
        
        print("\n✅ Servers started!")
        print("\nAccess the application at: http://localhost:3000")
        print("API available at: http://localhost:8000/api")
        print("\nDefault login:")
        print("  Username: admin")
        print("  Password: admin")
        print("\nPress Ctrl+C to stop servers\n")
        
        # Wait for processes
        while True:
            if backend_process.poll() is not None:
                print("\n❌ Backend server stopped unexpectedly")
                break
            if frontend_process.poll() is not None:
                print("\n❌ Frontend server stopped unexpectedly")
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        signal_handler(None, None)

if __name__ == '__main__':
    main()

