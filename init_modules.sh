#!/bin/bash

# Module Initialization Script
# This script initializes all modules in the CompleteBytePOS system

set -e  # Exit on error

echo "=========================================="
echo "CompleteBytePOS - Module Initialization"
echo "=========================================="
echo ""

# Check if running in Docker or local
if [ -f /.dockerenv ] || [ -n "$DOCKER_CONTAINER" ]; then
    echo "Running in Docker container..."
    CMD_PREFIX=""
else
    # Check if we're in the be directory
    if [ ! -f "manage.py" ]; then
        if [ -f "be/manage.py" ]; then
            cd be
            echo "Changed to be/ directory"
        else
            echo "Error: manage.py not found. Please run this script from the project root or be/ directory."
            exit 1
        fi
    fi
    
    # Check if virtual environment exists
    if [ -d "venv" ]; then
        echo "Activating virtual environment..."
        source venv/bin/activate
    elif [ -d "../venv" ]; then
        echo "Activating virtual environment..."
        source ../venv/bin/activate
    else
        echo "Warning: Virtual environment not found. Make sure dependencies are installed."
    fi
    
    CMD_PREFIX="python manage.py"
fi

# Function to run command
run_cmd() {
    if [ -n "$CMD_PREFIX" ]; then
        $CMD_PREFIX "$@"
    else
        docker exec completebytepos_backend python manage.py "$@"
    fi
}

# Step 1: Initialize Modules
echo "Step 1: Initializing modules and features..."
run_cmd init_modules
echo "✓ Modules initialized"
echo ""

# Step 2: Initialize Accounting Accounts
echo "Step 2: Initializing accounting accounts..."
run_cmd init_accounts
echo "✓ Accounting accounts initialized"
echo ""

# Step 3: Initialize Expense Categories
echo "Step 3: Initializing expense categories..."
run_cmd init_expense_categories
echo "✓ Expense categories initialized"
echo ""

# Step 4: Setup Organization (optional - only if not exists)
echo "Step 4: Setting up organization..."
run_cmd setup_new_organization --skip-modules --skip-accounts --skip-categories
echo "✓ Organization setup complete"
echo ""

echo "=========================================="
echo "Module Initialization Complete!"
echo "=========================================="
echo ""
echo "All modules have been initialized successfully."
echo ""
echo "You can now:"
echo "  - Login to the system"
echo "  - Configure your organization"
echo "  - Add products, customers, and suppliers"
echo "  - Start creating sales"
echo ""
