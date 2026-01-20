#!/bin/bash
# Script to run Django development server on all interfaces (0.0.0.0)
# This allows the backend to be accessible from network IPs, not just localhost

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run server on 0.0.0.0:8000 to allow network access
echo "Starting Django server on 0.0.0.0:8000..."
echo "Backend will be accessible at:"
echo "  - http://localhost:8000"
echo "  - http://127.0.0.1:8000"
echo "  - http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python manage.py runserver 0.0.0.0:8000
