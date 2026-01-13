# Fresh Install Guide - CompleteBytePOS

This guide explains how to perform a fresh installation with proper data population for a soft furnishings business.

## Quick Start

### Option 1: Using Docker (Recommended)

```bash
# 1. Start Docker containers
./run_docker.sh

# 2. Access the installation page
# Open http://localhost:3000 in your browser
# The installation wizard will guide you through the setup

# OR use command line inside the container:
docker exec -it completebytepos_backend python manage.py fresh_install --test-data
```

### Option 2: Using Command Line

```bash
# Navigate to backend directory
cd be

# Activate virtual environment (if using one)
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Run fresh install with soft furnishings data
python manage.py fresh_install --test-data
```

## Fresh Install Options

### Basic Fresh Install (No Data)

```bash
python manage.py fresh_install
```

This will:
- Delete existing database
- Run migrations
- Create superuser (admin/admin)
- Initialize permissions and roles
- Initialize modules and features
- Initialize accounting accounts
- Initialize expense categories
- Setup organization (tenant and branch)

### Fresh Install with Soft Furnishings Data (Recommended)

```bash
python manage.py fresh_install --test-data
```

This includes everything from basic install PLUS:
- **Users**: 20 users with roles (admin, manager, cashier)
- **Products**: 200 soft furnishings products (sofas, cushions, curtains, etc.) with color and size variants
- **Customers**: 50 customers (individual and business)
- **Sales**: 100 sales with various payment statuses:
  - Fully paid sales
  - Partially paid invoices
  - Unpaid invoices
  - Installments (1/4 remaining, 3/4 remaining, all complete)
- **Expenses**: 30 business expenses (fabric purchase, rent, salaries, etc.)

### Customize Data Amounts

```bash
python manage.py fresh_install --test-data \
    --users 30 \
    --products 300 \
    --customers 100 \
    --sales 200 \
    --expenses 50
```

## Installation Steps

The fresh install command performs these steps in order:

1. **Prepare Database** - Deletes existing database (unless `--skip-db-delete`)
2. **Create Migrations** - Generates database migrations
3. **Run Migrations** - Applies all migrations
4. **Create Superuser** - Creates admin user (username: admin, password: admin)
5. **Initialize Permissions** - Sets up all system permissions and roles
6. **Initialize Modules** - Sets up all modules and features
7. **Initialize Accounting** - Creates chart of accounts
8. **Initialize Categories** - Creates expense and income categories
9. **Setup Organization** - Creates default tenant and branch
10. **Populate Data** - Populates test/soft furnishings data (if requested)

## Command Options

```bash
python manage.py fresh_install [OPTIONS]

Options:
  --skip-db-delete          Skip database deletion
  --skip-test-data          Skip data population
  --test-data               Populate comprehensive soft furnishings data (recommended)
  --users N                 Number of users to create (default: 20)
  --products N              Number of products to create (default: 200)
  --customers N             Number of customers to create (default: 50)
  --sales N                 Number of sales to create (default: 100)
  --expenses N              Number of expenses to create (default: 30)
```

## What Gets Created

### With --test-data

**Products:**
- Sofas & Couches (with size and color variants)
- Cushions & Pillows (with size and color variants)
- Curtains & Drapes (with size and color variants)
- Cushion Covers (with size and color variants)
- Fabric & Upholstery (with color variants)
- Foam & Cushioning (with size variants)

**Customers:**
- Mix of individual and business customers
- Realistic Kenyan names and contact information

**Sales:**
- POS sales (fully paid)
- Normal sales with invoices
- Various payment statuses:
  - Fully paid
  - Partially paid (30-70%)
  - Unpaid
  - Installments (1/4 remaining, 3/4 remaining, all complete)

**Expenses:**
- Fabric Purchase
- Foam & Cushioning
- Hardware & Tools
- Rent & Utilities
- Transportation
- Marketing & Advertising
- Staff Salaries
- Insurance
- Maintenance & Repairs
- Office Supplies
- Professional Services
- Telecommunications

## After Installation

1. **Login** with:
   - Username: `admin`
   - Password: `admin`

2. **Change Password** - Important! Change the default password immediately

3. **Explore the Data**:
   - View products with variants
   - Check customers and their sales history
   - Review invoices with different payment statuses
   - See payment plans and installments
   - Review expenses

## Troubleshooting

### Database Already Exists

If you get errors about existing data:
```bash
python manage.py fresh_install --skip-db-delete
```

### Skip Data Population

If you only want the base setup:
```bash
python manage.py fresh_install --skip-test-data
```

### Docker Issues

If using Docker and having issues:
```bash
# Check container logs
docker compose logs backend

# Access container shell
docker exec -it completebytepos_backend bash

# Run commands inside container
docker exec -it completebytepos_backend python manage.py fresh_install --test-data
```

## Next Steps

After installation:
1. Review and customize module settings
2. Configure branches (if multi-branch is enabled)
3. Set up user roles and permissions
4. Customize product categories
5. Configure accounting accounts
6. Set up expense categories

## Example: Complete Fresh Install

```bash
# Using Docker
docker exec -it completebytepos_backend python manage.py fresh_install \
    --test-data \
    --users 30 \
    --products 300 \
    --customers 100 \
    --sales 200 \
    --expenses 50

# Or locally
cd be
source venv/bin/activate
python manage.py fresh_install \
    --test-data \
    --users 30 \
    --products 300 \
    --customers 100 \
    --sales 200 \
    --expenses 50
```

This will create a fully populated system ready for a soft furnishings business!
