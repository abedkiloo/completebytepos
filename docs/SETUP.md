# CompleteBytePOS — Setup Guide

This guide covers **first-time installation**, **Docker (dev & production)**, **VPS deployment**, **organization setup (tenant & branch)**, **environment variables**, and **common fixes**.

For production build details (nginx, static assets), see [DEPLOYMENT.md](./DEPLOYMENT.md).  
For roles, personas, and testing, see [POS_UX_ROLES_AND_TESTING.md](./POS_UX_ROLES_AND_TESTING.md).  
For coverage layout and 95% targets by layer, see [TESTING.md](./TESTING.md).

---

## Table of contents

1. [Prerequisites](#prerequisites)
2. [Quick start with Docker](#quick-start-with-docker)
3. [Environment configuration](#environment-configuration)
4. [First-time organization setup](#first-time-organization-setup)
5. [VPS / remote server deployment](#vps--remote-server-deployment)
6. [UAT on the same VPS](#uat-on-the-same-vps)
7. [Local development (without Docker)](#local-development-without-docker)
8. [Default users](#default-users)
9. [Verification checklist](#verification-checklist)
10. [Running tests](#running-tests)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Docker + Docker Compose | Recent (Compose v2) |
| **Or** Python | 3.11+ |
| **Or** Node.js | 18+ (20 recommended) |

**Database:** PostgreSQL is the default in Docker. SQLite is optional for local backend-only work (`USE_SQLITE=true`).

---

## Quick start with Docker

### 1. Clone and configure

```bash
git clone <repository-url>
cd CompleteBytePOS
cp .env.example .env
```

Edit `.env`:

- Set a strong `SECRET_KEY` before any real deployment.
- For a **remote VPS**, set `PUBLIC_HOST` to your server IP or domain.
- See [Environment configuration](#environment-configuration) for `REACT_APP_API_URL`.

### 2. Development stack (hot reload)

```bash
./run_docker.sh
# or
docker compose -f docker-compose.dev.yml up -d --build
```

| Service | URL (default) |
|---------|----------------|
| Frontend (React dev server) | http://localhost:3000 |
| Backend API | http://localhost:8000/api |
| Django admin | http://localhost:8000/admin |

Containers: `completebytepos_frontend`, `completebytepos_backend`, `completebytepos_db`.

### 3. Production stack (recommended for VPS)

```bash
./run_docker.sh --prod
# or
docker compose up -d --build
```

| Service | URL (default) |
|---------|----------------|
| App (nginx + static React) | http://localhost:3000 |
| API (proxied via nginx) | http://localhost:3000/api |
| Django admin (direct) | http://localhost:8000/admin |

After UI changes: `./run_docker.sh --prod --rebuild`

### 3b. UAT stack (same VPS, own database)

```bash
cp .env.uat.example .env.uat
./run_uat.sh
docker exec omuwenga-uat_backend python manage.py setup_new_organization
```

| Service | URL |
|---------|-----|
| App (nginx + static React) | https://uat.omuwenga.com |
| API (same-origin via nginx) | https://uat.omuwenga.com/api |
| Public API / Django admin | https://api.uat.omuwenga.com |

See [UAT on the same VPS](#uat-on-the-same-vps).

### 4. Complete organization setup (required)

Docker startup runs `init_modules` and `create_users` but **does not** create a tenant/branch by default. Run:

```bash
docker exec completebytepos_backend python manage.py setup_new_organization
```

This creates:

- **Tenant:** `CompleteByte Business` (`code=DEFAULT`)
- **Branch:** `Headquarters` (`HQ001`, headquarters)

See [First-time organization setup](#first-time-organization-setup) for alternatives and UI install flow.

### 5. Log in

Use [default users](#default-users), then change passwords in production.

### 6. Product size/color variants (optional)

If you use **size/color variants** on products:

1. **Module Settings → Products** — enable **Product Variants**.
2. **Inventory → Sizes & colors** (sidebar) — add each size and color, or seed defaults:

```bash
docker exec completebytepos_backend python manage.py init_sizes_colors
```

3. **Products → Add product** — check **This product has size/color variants**, then select sizes/colors (Ctrl/Cmd for multiple).

A fresh database has **no** sizes/colors until you add them on that page or run `init_sizes_colors`.

---

## Environment configuration

### Single source of truth: root `.env` (and `.env.uat`)

Docker Compose reads env files from **`CompleteBytePOS/`** (repository root, beside `be/` and `fe/`).

| File | Used by |
|------|---------|
| `.env` (root) | Prod and local Docker (`./run_docker.sh --prod`) |
| `.env.uat` | UAT only (`./run_docker.sh --uat`) — never copy prod secrets into this file |
| `fe/.env` | Only when running `npm start` **on the host** (not required for Docker) |

**Important:** Keep **one** active `REACT_APP_API_URL` line in root `.env`. Duplicate keys (especially `/api` at the bottom) override the correct value.

### `REACT_APP_API_URL` by mode

| Mode | Compose file | Env file | `REACT_APP_API_URL` |
|------|--------------|----------|---------------------|
| **Dev Docker** (UI on :3000, webpack) | `docker-compose.dev.yml` | `.env` | `http://YOUR_SERVER_IP:8000/api` or `http://localhost:8000/api` |
| **Prod Docker** (nginx proxies `/api`) | `docker-compose.yml` | `.env` | Baked as `/api` (compose ignores a `:8000` value) |
| **UAT Docker** (nginx proxies `/api`) | `docker-compose.yml` (`-p omuwenga-uat`) | `.env.uat` | Baked as `/api`; mobile uses `https://api.uat.omuwenga.com/api` |

**Remote dev VPS example:**

```bash
REACT_APP_API_URL=http://193.37.213.177:8000/api
PUBLIC_HOST=193.37.213.177
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,backend,193.37.213.177
```

**Production VPS example (HTTPS domain → host nginx → Docker :3000):**

```bash
REACT_APP_API_URL=/api
PUBLIC_HOST=shop.omuwenga.com
ALLOWED_HOSTS=shop.omuwenga.com,www.shop.omuwenga.com,localhost,127.0.0.1,backend,completebytepos_backend
DEBUG=False
USE_SECURE_PROXY_SSL_HEADER=True
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
```

**UAT VPS example (frontend + dedicated API host):**

```bash
# .env.uat — copy from .env.uat.example
REACT_APP_API_URL=/api
PUBLIC_HOST=uat.omuwenga.com
ALLOWED_HOSTS=uat.omuwenga.com,api.uat.omuwenga.com,localhost,127.0.0.1,backend,omuwenga-uat_backend
CORS_ALLOWED_ORIGINS=https://uat.omuwenga.com,https://api.uat.omuwenga.com
CSRF_TRUSTED_ORIGINS=https://uat.omuwenga.com,https://api.uat.omuwenga.com
DEBUG=False
USE_SECURE_PROXY_SSL_HEADER=True
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
FRONTEND_PORT=3100
BACKEND_PORT=8001
POSTGRES_PORT=5435
```

If the SPA loads but shows “Cannot reach the server” and `/api/...` returns **400**,
Django rejected the `Host` header — set `PUBLIC_HOST` / `ALLOWED_HOSTS` to the domain
(include `api.uat.omuwenga.com` on UAT), then recreate the backend container.

### Shell exports override `.env`

If you previously ran `export REACT_APP_API_URL=/api`, Docker Compose uses that **instead of** `.env`:

```bash
unset REACT_APP_API_URL
docker compose -f docker-compose.dev.yml config | grep REACT_APP
docker compose -f docker-compose.dev.yml up -d --force-recreate frontend
docker exec completebytepos_frontend printenv REACT_APP_API_URL
```

### Apply env changes

| Change | Action |
|--------|--------|
| Root `.env` for dev frontend | `docker compose -f docker-compose.dev.yml up -d --force-recreate frontend` |
| `REACT_APP_*` for prod build | Rebuild frontend image: `docker compose build frontend` then `up -d` |
| `.env.uat` / UAT UI | `./run_docker.sh --uat --rebuild` |

### Dev fallback in code

If `REACT_APP_API_URL=/api` in development, the app rewrites the API base to `http://<browser-host>:8000/api` (see `fe/src/config/apiBaseUrl.js`). Fixing `.env` is still recommended.

---

## First-time organization setup

### Why tenant & branch matter

- **Branches** belong to a **tenant** (business/company).
- With **multi-branch support** enabled, POS holding sales and branch APIs require a tenant and usually a selected branch.
- `GET /api/settings/setup-status/` includes `tenant_count`. If it is `0`, run setup below.

### Option A — Management command (recommended)

```bash
docker exec completebytepos_backend python manage.py setup_new_organization
```

Verify:

```bash
docker exec completebytepos_backend python manage.py shell -c \
  "from settings.models import Tenant, Branch; print(Tenant.objects.count(), Branch.objects.count())"

curl -s http://localhost:8000/api/settings/setup-status/
```

Expect `tenant_count` ≥ 1. Log out and log back in; select **Headquarters** in the branch selector if shown.

### Option B — Full fresh install (destructive)

Resets DB and runs all seed steps including tenant/branch:

```bash
docker exec completebytepos_backend python manage.py fresh_install
# Optional demo data:
docker exec completebytepos_backend python manage.py fresh_install --test-data
```

Read command help before use on a server with real data.

### Option C — Install wizard (UI)

If `setup-status` reports `needs_install: true`, use the in-app install flow (`/settings/fresh-install/` API). For existing DBs with users but no tenant, prefer **Option A**.

### Option D — Django admin / API

Super admin can create tenants at `/api/settings/tenants/` and branches at `/api/settings/branches/` (branch create still requires an existing tenant).

### Single-store without branches

Disable **multi-branch support** under **System settings → Module settings**. Holding sales then do not require branch selection. You may still want a default tenant for future use.

---

## VPS / remote server deployment

### Recommended: production Docker on the VPS

```bash
cd ~/complete_byte/completebytepos   # your path
cp .env.example .env
nano .env                            # SECRET_KEY, PUBLIC_HOST, ALLOWED_HOSTS, REACT_APP_API_URL=/api

./run_docker.sh --prod
docker exec completebytepos_backend python manage.py setup_new_organization
```

### Firewall

| Port | Purpose |
|------|---------|
| 80 / 443 | Public HTTPS (Caddy/nginx on the host) |
| 3000 | Production web UI (nginx in Docker) |
| 3100 | UAT web UI (`./run_docker.sh --uat`) |
| 8000 | Prod Gunicorn — **127.0.0.1** only (Caddy/`/api` on :3000). Open 8000 only for **dev** mode. |
| 8001 | UAT Gunicorn — **127.0.0.1** only; public entry is `api.uat.omuwenga.com` |
| 5432 | Prod PostgreSQL — **127.0.0.1** only; use an SSH tunnel for remote admin |
| 5435 | UAT PostgreSQL — **127.0.0.1** only (`POSTGRES_PORT=5435`) |

### Do not run dev mode on a small production VPS

`docker-compose.dev.yml` runs `npm start` (webpack), which uses far more RAM than production nginx. Use `./run_docker.sh --prod` for live servers.

### HTTPS

Terminate TLS at nginx or a reverse proxy (Caddy, Traefik). Set in `.env` when behind HTTPS:

```bash
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
USE_SECURE_PROXY_SSL_HEADER=True
```

Add your public URL to `CSRF_TRUSTED_ORIGINS` and `CORS_ALLOWED_ORIGINS`. On UAT that is both `https://uat.omuwenga.com` and `https://api.uat.omuwenga.com`.

### Resource tuning (small VPS)

Prod compose defaults are sized for ≈2 GB RAM. Override in `.env` if the box is larger:

| Setting | Default | Notes |
|---------|---------|--------|
| `GUNICORN_WORKERS` | `2` | Each worker is a full Django process. Do not set 4+ on 2 GB. |
| `GUNICORN_THREADS` | `4` | Extra concurrent I/O without extra RAM. |
| `GUNICORN_TIMEOUT` | `60` | Fail hung requests instead of stacking workers. |
| `DB_CONN_MAX_AGE` | `300` | Reuse Postgres connections. |
| `POSTGRES_SHARED_BUFFERS` | `128MB` | Lower to `64MB` on 1 GB VPS. |

After changing compose or `.env`: `docker compose up -d`. Nginx gzip/keepalive needs a **frontend image rebuild**.

Watch live pressure with `docker stats`.

---

## UAT on the same VPS

Production (`shop.omuwenga.com`) and UAT share one VPS and the same images/code, but **not** the same database, env file, ports, or volumes.

| | Production | UAT |
|--|------------|-----|
| Env file | `.env` | `.env.uat` |
| Compose project | directory default | `omuwenga-uat` |
| Containers | `completebytepos_*` | `omuwenga-uat_*` |
| App port | 3000 | 3100 |
| Gunicorn (localhost) | 8000 | 8001 |
| Postgres (localhost) | 5432 | 5435 |
| Public UI | shop.omuwenga.com | uat.omuwenga.com |
| Public API | (via shop `/api`) | api.uat.omuwenga.com |
| Gunicorn workers | 2 (default) | 1 (leave RAM for prod) |

### 1. DNS

Point A records at the same VPS IP as shop:

- **uat.omuwenga.com** — frontend
- **api.uat.omuwenga.com** — backend (Gunicorn, Django admin, mobile API)

### 2. Env file

```bash
cp .env.uat.example .env.uat
nano .env.uat   # unique SECRET_KEY and POSTGRES_PASSWORD (never copy prod)
```

### 3. Start UAT (does not stop production)

```bash
./run_uat.sh
docker exec omuwenga-uat_backend python manage.py setup_new_organization
```

Same stack as `./run_docker.sh --uat`. Use `./run_uat.sh --clear-cache` to wipe Docker build cache first.

The UAT web app still calls `/api` on `https://uat.omuwenga.com` (nginx proxies to Gunicorn). Mobile and Postman should use `https://api.uat.omuwenga.com/api`. Django admin: `https://api.uat.omuwenga.com/admin`.

### 3b. Optional sofa-craft catalog (UAT only)

Products and size/color variants only — **no sales or receiving documents**. Opening stock is mixed: **3 out of stock**, **4 low stock**, the rest in stock.

```bash
docker exec omuwenga-uat_backend python manage.py seed_uat_sofa_catalog
```

Remove it when you are done:

```bash
docker exec omuwenga-uat_backend python manage.py seed_uat_sofa_catalog --revert
```

SKUs start with `UAT-SOFA-`. `--revert` does not touch production-like products or the default users.

### 4. Host reverse proxy

Terminate TLS by hostname. Example Caddyfile is in `deploy/Caddyfile.example`:

- `shop.omuwenga.com` → `127.0.0.1:3000`
- `uat.omuwenga.com` → `127.0.0.1:3100`
- `api.uat.omuwenga.com` → `127.0.0.1:8001`

### 5. Stop / rebuild

```bash
./stop_uat.sh               # UAT only (same as ./stop_docker.sh --uat)
./stop_production.sh        # prod only
./stop_docker.sh --all      # everything
./run_uat.sh                # rebuild UAT from scratch (like ./run_production.sh)
```

Do **not** run `docker compose down -v` on the default project — that would wipe production Postgres. To reset UAT data only:

```bash
docker compose -p omuwenga-uat --env-file .env.uat down -v
```

If `run_uat.sh` fails with **port already allocated**, something else on the VPS already bound that port. Inspect with `ss -tlnp | grep 5435` or `docker ps`. Django still uses `db:5432` inside Docker; only the host publish uses `POSTGRES_PORT`.

---

## Local development (without Docker)

### Backend

```bash
cd be
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # or be/.env — root .env is preferred
python manage.py migrate
python manage.py init_permissions
python manage.py init_modules
python manage.py create_users
python manage.py setup_new_organization
python manage.py runserver
```

SQLite-only quick test:

```bash
USE_SQLITE=true python manage.py migrate
USE_SQLITE=true python manage.py test
```

### Frontend

```bash
cd fe
npm install
echo "REACT_APP_API_URL=http://localhost:8000/api" > .env
npm start
```

Open http://localhost:3000

---

## Default users

Created by `python manage.py create_users` (Docker runs this on startup):

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Super Admin |
| `manager` | `manager123` | Manager |
| `sales` | `sales123` | Sales Personnel |

Change all passwords before production use.

Legacy `setup.py` may still create `admin` / `admin` for non-Docker flows — prefer `create_users` for Docker.

---

## Verification checklist

Run after install or deploy:

```bash
# Containers up
docker ps --filter name=completebytepos
docker ps --filter name=omuwenga-uat

# Prod API health (through nginx)
curl -s http://YOUR_HOST:3000/api/healthz/
curl -s http://YOUR_HOST:3000/api/settings/setup-status/ | python3 -m json.tool

# UAT: UI via nginx, API host via Caddy
curl -sI https://uat.omuwenga.com/ | head -5
curl -s https://api.uat.omuwenga.com/api/healthz/
curl -s https://api.uat.omuwenga.com/api/settings/setup-status/ | python3 -m json.tool

# Expect: "installed": true, "tenant_count": >= 1

# Container env (dev remote)
docker exec completebytepos_frontend printenv REACT_APP_API_URL

# Prod: should be nginx, not node
docker exec completebytepos_frontend ps aux | head -3

# Backend logs
docker exec completebytepos_backend tail -20 /app/logs/error.log
```

In the browser (DevTools → Network):

- API calls hit the correct host (`:8000` in dev remote, or `/api` on same origin in prod).
- Login succeeds at `POST .../api/accounts/auth/login/`.
- No repeated 400 on branches/holding after `setup_new_organization`.

---

## Running tests

### Backend (inside Docker)

```bash
# All tests
docker exec completebytepos_backend python manage.py test

# Example subset
docker exec completebytepos_backend python manage.py test \
  settings.tests sales.tests.test_services -v 1
```

Uses PostgreSQL in Docker (no `USE_SQLITE` needed).

### Backend (local SQLite)

```bash
cd be
USE_SQLITE=true python manage.py test
```

### Frontend unit tests

```bash
cd fe
npm test -- --watchAll=false
```

### E2E (Playwright)

Stack running on :3000, then:

```bash
cd fe
npm run test:e2e
npm run test:e2e:persona
```

---

## Troubleshooting

### `GET ...:3000/api/...` returns 404

**Cause:** Dev UI on port 3000 with `REACT_APP_API_URL=/api` (relative URL); webpack does not proxy `/api`.

**Fix:** Set `REACT_APP_API_URL=http://SERVER_IP:8000/api` in root `.env`, `unset REACT_APP_API_URL` in shell, recreate frontend container. Or use production Docker (`/api` proxied by nginx).

### `printenv` shows `/api` but `.env` has `:8000`

Shell `export` overrides `.env`. Run `unset REACT_APP_API_URL` before `docker compose up`.

### `No tenant found. Please ensure a tenant is configured.`

**Cause:** `tenant_count` is 0.

**Fix:**

```bash
docker exec completebytepos_backend python manage.py setup_new_organization
```

Log out/in; select headquarters branch if multi-branch is enabled.

### `POST .../sales/holding/` 400 — No branch selected

**Cause:** Multi-branch enabled, no branch in session.

**Fix:** Run `setup_new_organization`, log in again, select branch in header — or disable multi-branch in module settings.

### Duplicate `REACT_APP_API_URL` in `.env`

Docker Compose may use the **last** value. Comment out all but one line; prefer a single correct URL for your mode.

### Product images 404 (`/media/products/...`)

**Cause:** With `DEBUG=False`, Django did not serve uploaded files; nginx also had no `/media/` route.

**Fix:**

1. Set your VPS IP in root `.env`: `PUBLIC_HOST=193.37.213.177` (your real IP).
2. Ensure `SERVE_MEDIA=true` (default).
3. Rebuild and restart (nginx must proxy `/media/`):

```bash
docker compose build frontend backend
docker compose up -d
```

4. Open images via the app origin, e.g. `http://YOUR_IP:3000/media/products/webbing.jpg` (port **3000**, not 8000), or `:8000` after backend restart.

5. Confirm files exist in the media volume:

```bash
docker exec completebytepos_backend ls -la /app/media/products/
```

6. **Module Settings → Products → Product Images** must be enabled for uploads in the UI.

### Migrations / backend not starting

```bash
docker compose logs backend
docker exec completebytepos_backend python manage.py migrate
```

### CORS errors from browser

Set `PUBLIC_HOST` and add your frontend origin to `CORS_ALLOWED_ORIGINS` in `.env`. In development, `DEBUG=True` defaults to permissive CORS unless overridden.

---

## What Docker runs on startup

Production and dev backends typically run (see `docker-compose*.yml`):

1. `makemigrations` / `migrate`
2. `init_permissions`
3. `init_modules`
4. `create_users`
5. `collectstatic` (prod)
6. Gunicorn

**Not** run automatically: `setup_new_organization` — run once per new database as documented above.

---

## Related documentation

| Document | Contents |
|----------|----------|
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Production build, nginx, `REACT_APP_*` bake time |
| [POS_UX_ROLES_AND_TESTING.md](./POS_UX_ROLES_AND_TESTING.md) | Roles, personas, test matrix |
| [README_SETUP.md](../README_SETUP.md) | Legacy local `setup.py` / `run.py` flow |
| [.env.example](../.env.example) | Prod / local environment variables |
| [.env.uat.example](../.env.uat.example) | UAT env (`uat.omuwenga.com` + `api.uat.omuwenga.com`) |
| [Caddyfile.example](../deploy/Caddyfile.example) | Host TLS: shop, uat, api.uat |

---

**Last updated:** one-VPS prod + UAT (`uat.omuwenga.com` UI, `api.uat.omuwenga.com` API), Docker Compose `create_users` bootstrap, and `setup_new_organization` for tenant/branch seeding.
