# CompleteBytePOS - Setup & Run Guide

## Quick Start

### Prerequisites

1. **Python 3.11+** installed
2. **Node.js 18+** and npm installed
3. ~~**MySQL** server~~ (Not needed - using SQLite)
4. ~~**MySQL database**~~ (Not needed - SQLite creates automatically)

### Step 1: Setup

Run the setup script to install dependencies and configure the project:

```bash
python setup.py
```

This will:
- Create Python virtual environment
- Install all Python dependencies
- Create `.env` file with default settings
- Run database migrations (SQLite database created automatically)
- Create a default superuser (admin/admin)

**Note**: Using SQLite - no database server setup required! The database file (`db.sqlite3`) will be created automatically.

### Step 2: Run the Application

Start both backend and frontend servers:

```bash
python run.py
```

This will start:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000

Access the application at: **http://localhost:3000**

**Database**: SQLite database file (`be/db.sqlite3`) is created automatically - no setup needed!

### Default Login

- **Username**: `admin`
- **Password**: `admin`

**⚠️ Change the default password in production!**

---

## Manual Setup (Alternative)

If you prefer to set up manually:

### Backend Setup

```bash
cd be
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file with database settings
cp .env.example .env  # Edit .env with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start server
python manage.py runserver
```

### Frontend Setup

```bash
cd fe
npm install

# Create .env file
echo "REACT_APP_API_URL=http://localhost:8000/api" > .env

# Start server
npm start
```

---

## Project Structure

```
CompleteBytePOS/
├── be/                 # Django backend
│   ├── config/        # Django project settings
│   ├── products/      # Products app
│   ├── sales/         # Sales app
│   ├── inventory/     # Inventory app
│   ├── accounts/      # Authentication app
│   ├── reports/       # Reports app
│   └── manage.py
├── fe/                 # React frontend
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   └── utils/
│   └── package.json
├── setup.py           # Setup script
└── run.py             # Run script
```

---

## Database Configuration

### SQLite (Current - Default)

The project is configured to use SQLite by default. **No setup required!**

- Database file: `be/db.sqlite3` (created automatically)
- No database server needed
- Perfect for development and single-user deployments
- Easy backup (just copy the file)

### MySQL (Future - Optional)

To switch to MySQL, update `be/config/settings.py` and uncomment MySQL configuration.

Make sure:
1. MySQL server is running
2. Database `completebytepos` exists (or create it)
3. User has proper permissions

To create database:
```sql
CREATE DATABASE completebytepos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### PostgreSQL (Future - Optional)

To switch to PostgreSQL, update `be/config/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'completebytepos'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}
```

And update `be/requirements.txt`:
- Remove `PyMySQL`
- Add `psycopg2-binary`

---

## API Endpoints

### Products
- `GET /api/products/` - List products
- `GET /api/products/search/?q=query` - Search products
- `POST /api/products/` - Create product
- `GET /api/products/{id}/` - Get product
- `PUT /api/products/{id}/` - Update product
- `DELETE /api/products/{id}/` - Delete product

### Sales
- `GET /api/sales/` - List sales
- `POST /api/sales/` - Create sale
- `GET /api/sales/{id}/` - Get sale
- `GET /api/sales/{id}/receipt/` - Get receipt

### Inventory
- `GET /api/inventory/` - List stock movements
- `POST /api/inventory/adjust/` - Adjust stock

### Reports
- `GET /api/reports/dashboard/` - Dashboard data
- `GET /api/reports/sales/` - Sales report
- `GET /api/reports/products/` - Product sales report

### Authentication
- `POST /api/accounts/auth/login/` - Login
- `POST /api/accounts/auth/logout/` - Logout
- `GET /api/accounts/auth/me/` - Get current user

---

## Troubleshooting

### Database Errors

**SQLite**: If you see database errors:
1. Delete `be/db.sqlite3` and run migrations again
2. Check file permissions in `be/` directory

**MySQL** (if switched):
1. Check MySQL is running: `mysql -u root -p`
2. Verify database exists
3. Check credentials in `be/.env`
4. Ensure MySQL user has proper permissions

### Port Already in Use

If port 8000 or 3000 is in use:

**Backend**: Edit `run.py` and change port:
```python
'runserver', '0.0.0.0:8001'  # Change 8000 to 8001
```

**Frontend**: Create `fe/.env`:
```
PORT=3001
REACT_APP_API_URL=http://localhost:8000/api
```

### Migration Errors

If migrations fail:
```bash
cd be
source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
```

### Module Not Found Errors

Make sure virtual environment is activated:
```bash
cd be
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

---

## Development

### Running Tests

**Backend**:
```bash
cd be
source venv/bin/activate
python manage.py test
```

**Frontend**:
```bash
cd fe
npm test
```

### Creating Migrations

After model changes:
```bash
cd be
source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
```

### Accessing Django Admin

1. Start backend server
2. Go to: http://localhost:8000/admin
3. Login with superuser credentials

---

## Production Deployment

For production:

1. Set `DEBUG=False` in `be/.env`
2. Generate new `SECRET_KEY`
3. Set proper `ALLOWED_HOSTS`
4. Use PostgreSQL instead of MySQL
5. Set up proper web server (Nginx + Gunicorn)
6. Configure SSL/HTTPS
7. Set up database backups

---

## Support

For issues or questions, check:
- Backend logs in terminal
- Frontend console in browser
- Django admin panel
- Database connection

---

**Happy coding! 🚀**

