/**
 * Resolve backend API base URL for the browser.
 *
 * Priority:
 *  1. window.__RUNTIME_CONFIG__.API_URL  (runtime-config.js — no rebuild)
 *  2. window.REACT_APP_API_URL           (legacy / ngrok-config.js)
 *  3. REACT_APP_API_URL at build time    (skipped if localhost but UI is remote)
 *  4. Same host, port 8000               (server IP / domain access)
 *  5. http://localhost:8000/api            (local dev only)
 */

function isLocalHostname(hostname) {
  return hostname === 'localhost' || hostname === '127.0.0.1';
}

function isLocalApiUrl(url) {
  if (!url) return false;
  try {
    const { hostname } = new URL(url, window.location.origin);
    return isLocalHostname(hostname);
  } catch {
    return url.includes('localhost') || url.includes('127.0.0.1');
  }
}

/**
 * @returns {string} API base including /api suffix (or relative /api)
 */
export function resolveApiBaseUrl() {
  const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
  const isLocal = isLocalHostname(host);

  const runtime = typeof window !== 'undefined' && window.__RUNTIME_CONFIG__;
  if (runtime?.API_URL) {
    return runtime.API_URL;
  }

  if (typeof window !== 'undefined' && window.REACT_APP_API_URL) {
    return window.REACT_APP_API_URL;
  }

  const envUrl = (process.env.REACT_APP_API_URL || '').trim();
  if (envUrl) {
    // Docker dev often sets localhost — wrong when user opens http://<server-ip>:3000
    if (!isLocalApiUrl(envUrl) || isLocal) {
      return envUrl;
    }
    if (process.env.NODE_ENV !== 'production') {
      console.warn(
        '[API] Ignoring REACT_APP_API_URL pointing at localhost while UI is remote; auto-detecting.'
      );
    }
  }

  if (typeof window !== 'undefined') {
    const isNgrok = host.includes('ngrok');
    const isHttps = window.location.protocol === 'https:';
    if (isNgrok || isHttps) {
      const backendNgrokUrl = localStorage.getItem('backend_ngrok_url');
      if (backendNgrokUrl) {
        return `${backendNgrokUrl.replace(/\/$/, '')}/api`;
      }
    }
  }

  if (typeof window !== 'undefined' && !isLocal) {
    const protocol = window.location.protocol;
    const port = process.env.REACT_APP_API_PORT || '8000';
    return `${protocol}//${host}:${port}/api`;
  }

  return 'http://localhost:8000/api';
}
