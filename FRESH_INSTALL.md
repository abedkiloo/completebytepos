# Fresh Installation Guide

This guide walks you through installing CompleteBytePOS as if for a new customer - a completely fresh installation.

## Quick Start

### Option 1: Automated Fresh Install (Recommended)

Run the automated script that does everything:

```bash
./fresh_install.sh
```

This script will:
1. ✅ Delete existing database (if any)
2. ✅ Run all migrations
3. ✅ Create superuser (admin/admin)
4. ✅ Initialize all modules and features
5. ✅ Initialize accounting accounts
6. ✅ Initialize expense categories
7. ✅ Create default tenant and branch
8. ✅ Optionally populate test data (20 users, 100 customers, 1000 products)

### Option 2: Manual Step-by-Step

If you prefer to do it manually:

#### Step 1: Delete Existing Database

```bash
cd be
rm -f db.sqlite3
```

#### Step 2: Run Migrations

```bash
cd be
source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
```

#### Step 3: Create Superuser

```bash
python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.create_superuser('admin', 'admin@example.com', 'admin')
print('Superuser created: username=admin, password=admin')
EOF
```

#### Step 4: Initialize System Data

```bash
# Initialize modules and features
python manage.py init_modules

# Initialize accounting accounts
python manage.py init_accounts

# Initialize expense categories
python manage.py init_expense_categories

# Setup new organization (creates default tenant and branch)
python manage.py setup_new_organization
```

#### Step 5: (Optional) Populate Test Data

```bash
# Populate with test data: 20 users, 100 customers, 1000 products
python manage.py populate_test_data --users 20 --customers 100 --products 1000
```

#### Step 6: Start the Application

```bash
# Development mode
cd ../../
python run.py

# Or production mode
./run_production.sh
```

## What Gets Created

### System Setup
- ✅ Database with all tables
- ✅ Superuser account (admin/admin)
- ✅ All modules and features initialized
- ✅ Accounting chart of accounts
- ✅ Expense categories
- ✅ Default tenant (CompleteByte Business)
- ✅ Default branch (Headquarters)

### Test Data (if populated)
- ✅ 20 users with various roles
- ✅ 100 customers
- ✅ 1000 products with categories and variants

## Login Credentials

After installation:

- **Username**: `admin`
- **Password**: `admin`

**⚠️ Important**: Change the default password after first login in production!

## Verification

After installation, verify everything works:

1. **Login**: Go to http://localhost:3000 and login with admin/admin
2. **Check Modules**: Go to `/module-settings` and verify all modules are enabled
3. **Check Products**: Go to `/products` and verify products are listed (if test data was populated)
4. **Check Customers**: Go to `/customers` and verify customers are listed (if test data was populated)
5. **Test Sales**: Go to `/pos` and try creating a test sale

## Troubleshooting

### Database Already Exists Error

If you get errors about existing data:

```bash
cd be
rm -f db.sqlite3
# Then run fresh_install.sh again
```

### Migration Errors

If migrations fail:

```bash
cd be
source venv/bin/activate
python manage.py makemigrations --noinput
python manage.py migrate --noinput
```

### Module Initialization Errors

If modules don't initialize:

```bash
cd be
source venv/bin/activate
python manage.py init_modules
```

### Test Data Population Fails

If test data population fails, you can skip it and add data manually through the UI or run individual commands:

```bash
# Create users only
python manage.py create_users --count 20

# Generate products only
python manage.py generate_products --count 1000
```

## Next Steps After Installation

1. **Change Default Password**: Login and change the admin password
2. **Configure Module Settings**: Go to `/module-settings` and enable/disable features as needed
3. **Add Your Products**: If you didn't populate test data, add your actual products
4. **Add Your Customers**: Add your actual customer database
5. **Configure Branches**: If using multi-branch, add your branches
6. **Set Up Users**: Create user accounts for your staff
7. **Test Sales Flow**: Create a test sale to verify everything works

## Production Deployment

For production deployment:

1. Use `./run_production.sh` instead of `python run.py`
2. Set proper environment variables in `.env` file
3. Use a production database (PostgreSQL recommended)
4. Configure proper security settings
5. Set up SSL/HTTPS
6. Configure backup procedures

## Support

If you encounter issues during installation, check:

1. Python version (3.11+ required)
2. Node.js version (18+ required)
3. All dependencies installed (`pip install -r requirements.txt` and `npm install`)
4. Database permissions
5. Port availability (8000 for backend, 3000 for frontend)

---

**Happy Installing!** 🚀
