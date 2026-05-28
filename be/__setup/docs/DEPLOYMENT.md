# Production deployment (React build + nginx)

CompleteBytePOS follows the [Create React App production build](https://create-react-app.dev/docs/production-build/) pattern:

1. **`npm run build`** — minified JS/CSS into `fe/build/`
2. **Static hosting** — nginx serves those files (not `npm start`)
3. **API proxy** — browser calls `/api`; nginx forwards to Django

## Docker (recommended)

| Mode | Command | Frontend |
|------|---------|----------|
| **Development** | `./run_docker.sh` | React dev server (hot reload) |
| **Production** | `./run_docker.sh --prod` | Built static files + nginx |

Production stack (`docker-compose.yml`):

- **Frontend image** (`fe/Dockerfile`): Node build stage → `fe/build` → nginx on port 80
- **Backend**: Gunicorn without `--reload`, `DEBUG=False` by default
- **URL**: http://localhost:3000 (maps host 3000 → container 80)

```bash
./run_docker.sh --prod
# or
docker compose up -d --build
```

Verify production frontend (not dev):

```bash
# Response headers should show nginx, not webpack-dev-server
curl -sI http://localhost:3000/ | head -5

# Container should NOT run "npm start"
docker exec completebytepos_frontend ps
```

## Environment variables (React)

`REACT_APP_*` values are **baked in at image build time**. To change the API URL you must **rebuild** the frontend image:

```bash
docker compose build --build-arg REACT_APP_API_URL=/api frontend
```

For same-origin Docker setup, use `/api` (nginx proxies to `backend:8000`).

Copy `.env.production.example` to `.env.production` and set `SECRET_KEY` before real deploy.

## Manual build (without Docker)

```bash
cd fe
REACT_APP_API_URL=/api npm run build
# Serve fe/build with any static host (nginx, S3+CloudFront, etc.)
```

Do **not** run `npm start` in production.

## Development vs production

| | Development | Production |
|---|-------------|------------|
| Compose file | `docker-compose.dev.yml` | `docker-compose.yml` |
| Frontend Dockerfile | `Dockerfile.dev` | `Dockerfile` |
| Frontend process | `react-scripts start` | nginx + static `build/` |
| Backend reload | `--reload` | no reload |
| DEBUG | `True` | `False` |
