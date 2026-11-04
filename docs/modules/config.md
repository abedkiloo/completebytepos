# config

## Purpose

Django project settings, root URL map, healthz, JWT, WSGI/ASGI, env/db helpers. App mounts live only in `config/urls.py`.

## Key models

*(none)*

## Public APIs

Prefix: `/api/` (root: healthz, token, app includes)

## Bounds & invariants

- No secrets in repo; env-driven settings for deploy.
- New apps must be registered in `INSTALLED_APPS` and mounted in `urls.py`.
- Keep `be/STRUCTURE.md` App map in sync when adding apps.

## Gaps

- Public API docstrings: **done** for ``env.py`` and ``health.py`` helpers; ``settings.py`` remains informal — document non-obvious env vars when touched.
