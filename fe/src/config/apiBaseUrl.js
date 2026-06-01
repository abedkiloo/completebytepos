/**
 * Backend API base URL (includes /api).
 * Set REACT_APP_API_URL in fe/.env or workspace root .env for Docker.
 *
 * Dev:  http://localhost:8000/api  or http://YOUR_SERVER_IP:8000/api
 * Prod: /api  (nginx proxies to backend)
 */
export function resolveApiBaseUrl() {
  const configured = (process.env.REACT_APP_API_URL || '').trim();

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
