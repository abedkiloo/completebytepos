# Fresh Database Setup Instructions

## Problem
Django 4.2.27 has a migration dependency issue with the auth app that prevents automatic migration creation when starting from scratch.

## Solution: Manual Migration Creation

Since we're starting fresh, we need to create migrations manually. Here's the step-by-step process:

### Step 1: Clean Slate
```bash
cd be
source venv/bin/activate

# Delete database
rm -f db.sqlite3

# Delete all migration files (except __init__.py)
find . -path "*/migrations/*.py" ! -name "__init__.py" ! -path "*/venv/*" -delete
```

### Step 2: Create Database and Basic Tables
```bash
# Create database file
touch db.sqlite3

# Use Python to create basic Django tables
python << 'EOF'
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from datetime import datetime

with connection.cursor() as cursor:
    # Create django_migrations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS django_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            applied DATETIME NOT NULL
        )
    """)
    
    # Mark all Django built-in migrations as applied
    now = datetime.now().isoformat()
    migrations = [
        ('contenttypes', '0001_initial', now),
        ('auth', '0001_initial', now),
        ('admin', '0001_initial', now),
        ('sessions', '0001_initial', now),
        ('messages', '0001_initial', now),
        ('staticfiles', '0001_initial', now),
    ]
    cursor.executemany(
        "INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, ?)",
        migrations
    )
    connection.commit()
    print("✓ Created basic Django tables")
EOF
```

### Step 3: Create Migrations for Each App
For each app, you'll need to manually create the `0001_initial.py` migration file. However, the easiest way is to:

1. **Temporarily fix the Django auth migration issue** by creating a dummy migration file, OR
2. **Use `--skip-checks` flag** (if available), OR  
3. **Manually write migration files** based on your models

### Step 4: Recommended Approach - Use Django's inspectdb

Since we have all the models defined, the best approach is to:

1. **Create the database schema using `inspectdb`** after manually creating tables, OR
2. **Use a migration workaround script**

### Alternative: Use SQLite Directly

You can create all tables directly using SQL, then use Django's `inspectdb` to generate models (backwards), or manually create migration files.

## Quick Workaround Script

I've created `fresh_setup.py` which attempts to automate this, but it's hitting the Django auth migration issue.

## Manual Steps (Recommended)

1. **Delete database and migrations** (already done)
2. **Create a minimal working database** with just Django system tables
3. **Manually create `0001_initial.py` migration files** for each app by:
   - Looking at your models
   - Using Django's migration template
   - Copying from a working Django project with similar models

4. **Run migrations**:
   ```bash
   python manage.py migrate --fake-initial
   ```

5. **Initialize data**:
   ```bash
   python manage.py createsuperuser
   python manage.py init_modules
   python manage.py init_accounts
   python manage.py init_expense_categories
   ```

## Next Steps

Since the automatic migration creation is blocked by Django's internal migration system, you have two options:

1. **Upgrade/Downgrade Django** to a version without this issue
2. **Manually create migration files** - I can help create these based on your models
3. **Use a different database backend** temporarily (PostgreSQL/MySQL) which might handle migrations differently

Would you like me to:
- Create the migration files manually based on your models?
- Help upgrade/downgrade Django?
- Set up a different database backend?
