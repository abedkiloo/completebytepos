/**
 * Backend API base URL (includes /api).
 * Set REACT_APP_API_URL in fe/.env or workspace root .env for Docker.
 *
 * Dev:  http://localhost:8000/api  or http://YOUR_SERVER_IP:8000/api
 * Prod: /api  (nginx proxies to backend). Gunicorn is not public.
 */

function nginxSpaPort(port) {
  return port === '3000' || port === '80' || port === '443' || port === '';
}

/**
 * Prod nginx on :3000 must not call public :8000 — that port is localhost-only.
 */
function productionNginxBase(configured) {
  if (process.env.NODE_ENV !== 'production' || typeof window === 'undefined') {
    return null;
  }
  const { hostname, port } = window.location;
  if (!nginxSpaPort(port)) return null;
  if (!configured || configured === '/api') return '/api';
  try {
    const baked = new URL(configured, window.location.origin);
    if (baked.hostname === hostname && baked.port === '8000') {
      return '/api';
    }
  } catch {
    return '/api';
  }
  return null;
}

export function resolveApiBaseUrl() {
  const configured = (process.env.REACT_APP_API_URL || '').trim();
  const nginxBase = productionNginxBase(configured);
  if (nginxBase) return nginxBase;

  // "/api" only works behind nginx. CRA dev server has no /api proxy.
  if (
    configured === '/api' &&
    process.env.NODE_ENV !== 'production' &&
    typeof window !== 'undefined'
  ) {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000/api`;
  }

  if (configured) return configured;

  return 'http://localhost:8000/api';
}
