/**
 * Backend API base URL (includes /api).
 * Set REACT_APP_API_URL in fe/.env or workspace root .env for Docker.
 *
 * Dev:  http://localhost:8000/api  or http://YOUR_SERVER_IP:8000/api
 * Prod: /api  (nginx proxies to backend)
 */
export function resolveApiBaseUrl() {
  return (process.env.REACT_APP_API_URL || 'http://localhost:8000/api').trim();
}
