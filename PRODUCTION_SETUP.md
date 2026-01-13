# CompleteBytePOS - Production Setup Guide

This guide explains how to run CompleteBytePOS in production mode.

## Prerequisites

1. **Python 3.8+** installed
2. **Node.js 14+** and npm installed
3. **Virtual environment** set up for backend
4. **Dependencies** installed (backend and frontend)

## Quick Start

### 1. Install Production Dependencies

```bash
# Backend
cd be
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../fe
npm install
```

### 2. Configure Environment Variables

Create a `.env` file in the `be` directory:

```bash
# be/.env
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=your-domain.com,localhost
REACT_APP_API_URL=https://your-domain.com/api
```

**Important**: 
- Set `DEBUG=False` for production
- Use a strong, unique `SECRET_KEY`
- Update `ALLOWED_HOSTS` with your actual domain(s)

### 3. Run Production Server

```bash
# From project root
./run_production.sh
```

This script will:
- Build the React frontend for production
- Run database migrations
- Collect static files
- Start Gunicorn server on port 8000

### 4. Stop Production Server

```bash
./stop_production.sh
```

## Configuration Options

You can customize the production server by setting environment variables:

```bash
export BACKEND_PORT=8000      # Backend server port (default: 8000)
export WORKERS=4              # Number of Gunicorn workers (default: 4)
export THREADS=2             # Threads per worker (default: 2)

./run_production.sh
```

### Recommended Worker Count

The number of workers should be: `(2 × CPU cores) + 1`

For example:
- 2 CPU cores → 5 workers
- 4 CPU cores → 9 workers
- 8 CPU cores → 17 workers

## Production Checklist

- [ ] Set `DEBUG=False` in `.env` file
- [ ] Set a strong `SECRET_KEY`
- [ ] Update `ALLOWED_HOSTS` with your domain
- [ ] Configure database (if not using SQLite)
- [ ] Set up SSL/HTTPS certificate
- [ ] Configure firewall rules
- [ ] Set up log rotation
- [ ] Configure backup strategy
- [ ] Set up monitoring/alerting
- [ ] Review security settings

## Serving Static Files

The production setup uses **WhiteNoise** to serve static files directly from Django. This is suitable for small to medium deployments.

For high-traffic production, consider:
- Using a reverse proxy (nginx/Apache) to serve static files
- Using a CDN for static assets
- Using cloud storage (AWS S3, etc.) for media files

## Using Nginx as Reverse Proxy (Recommended)

For production, it's recommended to use Nginx as a reverse proxy:

### Nginx Configuration Example

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Serve static files directly
    location /static/ {
        alias /path/to/CompleteBytePOS/be/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Serve media files
    location /media/ {
        alias /path/to/CompleteBytePOS/be/media/;
        expires 7d;
    }

    # Proxy API requests to Gunicorn
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy admin panel
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Serve React app
    location / {
        root /path/to/CompleteBytePOS/fe/build;
        try_files $uri $uri/ /index.html;
    }
}
```

## Systemd Service (Optional)

Create a systemd service for automatic startup:

```bash
# /etc/systemd/system/completebytepos.service
[Unit]
Description=CompleteBytePOS Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/CompleteBytePOS/be
Environment="PATH=/path/to/CompleteBytePOS/be/venv/bin"
ExecStart=/path/to/CompleteBytePOS/be/venv/bin/gunicorn \
    --workers 4 \
    --threads 2 \
    --bind 127.0.0.1:8000 \
    config.wsgi:application

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable completebytepos
sudo systemctl start completebytepos
sudo systemctl status completebytepos
```

## Monitoring

### View Logs

```bash
# Access logs
tail -f be/logs/access.log

# Error logs
tail -f be/logs/error.log
```

### Check Server Status

```bash
# Check if Gunicorn is running
ps aux | grep gunicorn

# Check process by PID
cat be/gunicorn.pid
ps -p $(cat be/gunicorn.pid)
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### Static Files Not Loading

1. Ensure `collectstatic` was run: `python manage.py collectstatic`
2. Check `STATIC_ROOT` path in settings
3. Verify WhiteNoise middleware is in `MIDDLEWARE` list
4. Check file permissions on `staticfiles` directory

### Database Issues

```bash
# Run migrations
cd be
source venv/bin/activate
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser
```

## Security Considerations

1. **Never commit `.env` files** to version control
2. **Use strong SECRET_KEY** - generate with: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
3. **Enable HTTPS** in production
4. **Restrict ALLOWED_HOSTS** to your actual domains
5. **Keep dependencies updated** - regularly run `pip list --outdated`
6. **Use environment-specific settings** - consider separate settings files for production

## Performance Tips

1. **Enable database connection pooling** (for PostgreSQL/MySQL)
2. **Use Redis for caching** (install django-redis)
3. **Enable Gzip compression** (already enabled via WhiteNoise)
4. **Use CDN for static assets** in high-traffic scenarios
5. **Monitor database queries** - use Django Debug Toolbar in development
6. **Optimize database indexes** based on query patterns

## Backup Strategy

```bash
# Backup database (SQLite)
cp be/db.sqlite3 backups/db_$(date +%Y%m%d_%H%M%S).sqlite3

# Backup media files
tar -czf backups/media_$(date +%Y%m%d_%H%M%S).tar.gz be/media/
```

## Support

For issues or questions, please refer to the main README.md or open an issue in the project repository.
