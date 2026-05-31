/**
 * Shared auth storage helpers — used by logout, idle timeout, and API interceptors.
 */
import { clearStoreSettingsCache } from './storeSettingsCache';

const AUTH_STORAGE_KEYS = [
  'access_token',
  'refresh_token',
  'isAuthenticated',
  'user',
  'profile',
  'permissions',
  'enabled_modules',
  'last_activity_at',
];

const SESSION_TEARDOWN_KEY = 'session_teardown';

let teardownStarted = false;

export function isSessionTeardownActive() {
  return (
    teardownStarted ||
    sessionStorage.getItem(SESSION_TEARDOWN_KEY) === '1'
  );
}

export function clearSessionTeardownFlag() {
  teardownStarted = false;
  sessionStorage.removeItem(SESSION_TEARDOWN_KEY);
}

export function isAuthenticated() {
  if (isSessionTeardownActive()) return false;
  return Boolean(
    localStorage.getItem('access_token') &&
      localStorage.getItem('isAuthenticated') === 'true'
  );
}

export function clearAuthState() {
  AUTH_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
  clearStoreSettingsCache();
}

/**
 * Best-effort server logout — raw axios, never through the api interceptor.
 */
export async function revokeRefreshTokenOnServer(refreshToken) {
  if (!refreshToken) return;
  try {
    const [{ default: axios }, { resolveApiBaseUrl }] = await Promise.all([
      import('axios'),
      import('../config/apiBaseUrl'),
    ]);
    await axios.post(
      `${resolveApiBaseUrl()}/accounts/auth/logout/`,
      { refresh: refreshToken },
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: 4000,
      }
    );
  } catch {
    /* expired / offline — local session already cleared */
  }
}

/**
 * Clear local session once. Returns false if teardown already running.
 */
export function beginSessionTeardown() {
  if (isSessionTeardownActive()) return false;
  teardownStarted = true;
  sessionStorage.setItem(SESSION_TEARDOWN_KEY, '1');
  clearAuthState();
  return true;
}

/**
 * Revoke refresh token (best effort), clear storage, redirect to login.
 * Safe to call from many concurrent 401 handlers — runs at most once.
 */
export async function logoutAndRedirect({ reason = 'auth' } = {}) {
  const loginPath = reason === 'idle' ? '/login?expired=idle' : '/login';

  if (window.location.pathname.startsWith('/login')) {
    clearSessionTeardownFlag();
    return;
  }

  if (isSessionTeardownActive()) {
    window.location.replace(loginPath);
    return;
  }

  const refreshToken = localStorage.getItem('refresh_token');
  beginSessionTeardown();

  if (reason === 'idle') {
    sessionStorage.setItem('session_expired_reason', 'idle');
  }

  await revokeRefreshTokenOnServer(refreshToken);
  window.location.replace(loginPath);
}

/**
 * Manual logout from in-app UI (React Router navigation, no full reload).
 */
export async function logoutLocally() {
  const refreshToken = localStorage.getItem('refresh_token');
  beginSessionTeardown();
  await revokeRefreshTokenOnServer(refreshToken);
}
