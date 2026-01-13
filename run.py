#!/usr/bin/env python3
"""
CompleteBytePOS - Main Run Script
Supports both Docker and non-Docker modes
"""
import os
import sys
import subprocess
import signal
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / 'be'
FRONTEND_DIR = PROJECT_ROOT / 'fe'
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

def run_docker():
    """Run using Docker"""
    print("="*50)
    print("CompleteBytePOS - Starting with Docker")
    print("="*50)
    print()
    
    # Check if Docker is available
    try:
        subprocess.run(['docker', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Docker is not installed or not running!")
        print("   Please install Docker: https://docs.docker.com/get-docker/")
        print("   Or run without Docker: python run.py --no-docker")
        sys.exit(1)
    
    # Check if docker-compose is available
    compose_cmd = None
    try:
        subprocess.run(['docker', 'compose', 'version'], capture_output=True, check=True)
        compose_cmd = ['docker', 'compose']
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(['docker-compose', '--version'], capture_output=True, check=True)
            compose_cmd = ['docker-compose']
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Docker Compose is not installed!")
            print("   Please install Docker Compose")
            sys.exit(1)
    
    print("🐳 Starting Docker containers...")
    print("   This will build and start both backend and frontend")
    print()
    
    # Run docker-compose
    try:
        # Build and start
        subprocess.run(compose_cmd + ['up', '--build', '-d'], check=True)
        print("\n✅ Docker containers started!")
        print("\nAccess the application at: http://localhost:3000")
        print("API available at: http://localhost:8000/api")
        print("\nDefault login:")
        print("  Username: admin")
        print("  Password: admin")
        print("\nTo view logs: docker compose logs -f")
        print("To stop: ./stop_docker.sh or docker compose down")
        print("\nPress Ctrl+C to exit (containers will keep running)")
        
        # Follow logs
        try:
            subprocess.run(compose_cmd + ['logs', '-f'])
        except KeyboardInterrupt:
            print("\n\nContainers are still running. Use ./stop_docker.sh to stop them.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error starting Docker containers: {e}")
        print("   Check Docker logs: docker compose logs")
        sys.exit(1)

def main():
    """Main run function"""
    # Check for Docker mode
    use_docker = '--docker' in sys.argv or '-d' in sys.argv
    no_docker = '--no-docker' in sys.argv
    
    if use_docker and not no_docker:
        run_docker()
        return
    
    print("="*50)
    print("CompleteBytePOS - Starting Servers (Non-Docker)")
    print("="*50)
    print()
    print("💡 Tip: Use 'python run.py --docker' to run with Docker")
    print("   Or use './run_docker.sh' for Docker mode")
    print()
    print("⚠️  Non-Docker mode requires:")
    print("   - Python virtual environment in be/venv")
    print("   - Node.js and npm installed")
    print("   - Frontend dependencies installed (npm install)")
    print()
    
    response = input("Continue with non-Docker mode? (y/N): ")
    if response.lower() != 'y':
        print("Exiting. Use './run_docker.sh' for Docker mode.")
        sys.exit(0)
    
    print("\nStarting servers...")
    print("Backend: http://localhost:8000")
    print("Frontend: http://localhost:3000")
    print("\nPress Ctrl+C to stop all servers\n")

if __name__ == '__main__':
    main()
