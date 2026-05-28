import { installAPI } from '../services/api';

const CACHE_KEY = 'setup_status_cache';
const CACHE_MS = 30_000;

function readCache() {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const { at, data } = JSON.parse(raw);
    if (Date.now() - at > CACHE_MS) return null;
    return data;
  } catch {
    return null;
  }
}

export function clearSetupStatusCache() {
  sessionStorage.removeItem(CACHE_KEY);
}

export function markSetupInstalled() {
  const data = {
    installed: true,
    needs_install: false,
    user_count: 1,
    module_count: 1,
  };
  sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), data }));
  return data;
}

/**
 * @returns {Promise<{ installed: boolean, needs_install: boolean }>}
 */
export async function fetchSetupStatus({ force = false } = {}) {
  if (!force) {
    const cached = readCache();
    if (cached) return cached;
  }

  const response = await installAPI.status();
  const data = response.data || {};
  sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), data }));
  return data;
}
