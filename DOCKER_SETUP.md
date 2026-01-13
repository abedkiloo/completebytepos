# Docker Setup Guide

CompleteBytePOS now supports full Docker containerization for both backend and frontend.

## Quick Start with Docker

### Option 1: Using setup.py (Recommended)

```bash
python setup.py
```

Choose option 1 (Docker) when prompted. This will:
- ✅ Build Docker images for backend and frontend
- ✅ Install all Python requirements in container
- ✅ Build React frontend package
- ✅ Run all database migrations
- ✅ Create superuser (admin/admin)
- ✅ Initialize all system data (permissions, modules, accounts, etc.)
- ✅ Start both containers automatically

### Option 2: Using fresh_install.sh

```bash
./fresh_install.sh
```

This performs a complete fresh installation using Docker containers.

## Manual Docker Commands

### Build and Start

```bash
# Build images
docker compose build

# Start containers
docker compose up -d

# View logs
docker compose logs -f

# Stop containers
docker compose down
```

### Run Setup Commands

```bash
# Run migrations
docker compose exec backend python manage.py migrate

# Create superuser
docker compose exec backend python manage.py createsuperuser

# Initialize system
docker compose exec backend python manage.py init_permissions
docker compose exec backend python manage.py init_modules
docker compose exec backend python manage.py init_accounts
docker compose exec backend python manage.py init_expense_categories
docker compose exec backend python manage.py setup_new_organization
```

## Services

After setup, services are available at:

- **Backend API**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **Admin Panel**: http://localhost:8000/admin

## Default Credentials

- **Username**: `admin`
- **Password**: `admin`

⚠️ **Important**: Change the default password after first login!

## Docker Compose Services

### Backend Container
- **Image**: Python 3.12-slim
- **Port**: 8000
- **Command**: Gunicorn with 4 workers
- **Volumes**: 
  - Code: `./be:/app`
  - Static files: `backend_static`
  - Media: `backend_media`
  - Database: `backend_db`

### Frontend Container
- **Image**: Node 18 (build) + Nginx (production)
- **Port**: 3000 (mapped to 80 in container)
- **Build**: React app built and served via Nginx
- **Proxy**: API requests proxied to backend

## Troubleshooting

### Containers won't start
```bash
# Check logs
docker compose logs

# Rebuild from scratch
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### Database issues
```bash
# Reset database
docker compose exec backend rm -f /app/db/db.sqlite3
docker compose exec backend python manage.py migrate
```

### Frontend not building
```bash
# Rebuild frontend
docker compose build --no-cache frontend
docker compose up -d frontend
```

### View container status
```bash
docker compose ps
```

### Access container shell
```bash
# Backend
docker compose exec backend bash

# Frontend
docker compose exec frontend sh
```

## Development vs Production

### Development
- Uses volume mounts for live code reloading
- Backend runs with `--reload` flag
- Frontend serves built files via Nginx

### Production
- Remove volume mounts for code
- Use production-ready settings
- Set `DEBUG=False` in environment
- Use proper database (PostgreSQL recommended)

## Environment Variables

Set in `docker-compose.yml` or `.env` file:

```yaml
environment:
  - DEBUG=True
  - SECRET_KEY=your-secret-key
  - DATABASE_URL=sqlite:///db/db.sqlite3
```

## Volumes

Data persists in Docker volumes:
- `backend_static`: Static files
- `backend_media`: User uploads
- `backend_db`: Database files

To remove all data:
```bash
docker compose down -v
```
