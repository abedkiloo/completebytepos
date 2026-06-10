/**
 * In-memory module settings store — dedupes GET /api/settings/{module}/ across hooks.
 */

import { moduleSettingsAPI } from '../services/api';
import {
  isAppliedModuleSettingsResponse,
  isPendingApprovalResponse,
} from './makerChecker';
import {
  cacheModuleSettings,
  flattenModuleSettings,
  readCachedModuleSettings,
} from './moduleSettingsCache';

/** @type {Map<string, { settings: object, meta: object|null, loading: boolean, loaded: boolean, subscribers: Set<() => void>, fetchPromise: Promise<void>|null }>} */
const stores = new Map();

function getStore(module) {
  if (!stores.has(module)) {
    stores.set(module, {
      settings: readCachedModuleSettings(module),
      meta: null,
      loading: false,
      loaded: false,
      subscribers: new Set(),
      fetchPromise: null,
    });
  }
  return stores.get(module);
}

function notify(module) {
  getStore(module).subscribers.forEach((fn) => fn());
}

export function applyModuleSettingsPayload(module, payload) {
  const flat = flattenModuleSettings(payload);
  cacheModuleSettings(module, flat);
  const store = getStore(module);
  store.settings = flat;
  store.meta = payload;
  notify(module);
  return flat;
}

export function subscribeModuleSettings(module, listener) {
  const store = getStore(module);
  store.subscribers.add(listener);
  return () => store.subscribers.delete(listener);
}

export function getModuleSettingsSnapshot(module) {
  const store = getStore(module);
  return {
    settings: store.settings,
    meta: store.meta,
    loading: store.loading,
  };
}

export async function ensureModuleSettingsLoaded(module) {
  if (!localStorage.getItem('access_token')) {
    return getModuleSettingsSnapshot(module);
  }

  const store = getStore(module);
  if (store.loaded && !store.fetchPromise) {
    return getModuleSettingsSnapshot(module);
  }
  if (store.fetchPromise) {
    await store.fetchPromise;
    return getModuleSettingsSnapshot(module);
  }

  store.loading = true;
  notify(module);

  store.fetchPromise = moduleSettingsAPI
    .get(module)
    .then((res) => {
      applyModuleSettingsPayload(module, res.data);
      store.loaded = true;
    })
    .catch(() => {})
    .finally(() => {
      store.loading = false;
      store.fetchPromise = null;
      notify(module);
    });

  await store.fetchPromise;
  return getModuleSettingsSnapshot(module);
}

function applyOptimisticModuleSettings(module, values) {
  const store = getStore(module);
  const flat = { ...store.settings, ...values };
  cacheModuleSettings(module, flat);
  store.settings = flat;
  notify(module);
  return flat;
}

function rejectModuleSettingsResponse(res) {
  const error = new Error('Module settings patch failed');
  error.response = res;
  throw error;
}

/**
 * PATCH /api/settings/{module}/ — returns applied vs pending state for UI toasts.
 * @returns {Promise<{ settings: object, pending: boolean, status: number }>}
 */
export async function patchModuleSettings(module, values, options = {}) {
  const payload = { ...values };
  if (options.reason) {
    payload.reason = options.reason;
  }
  const res = await moduleSettingsAPI.patch(module, payload);
  const { status } = res;

  if (isPendingApprovalResponse(status)) {
    const settings = applyOptimisticModuleSettings(module, values);
    return { settings, pending: true, status };
  }

  if (!isAppliedModuleSettingsResponse(status)) {
    rejectModuleSettingsResponse(res);
  }

  if (!res.data?.settings) {
    rejectModuleSettingsResponse(res);
  }

  const flat = applyModuleSettingsPayload(module, res.data);
  window.dispatchEvent(new CustomEvent('moduleSettingsUpdated', { detail: res.data }));
  return { settings: flat, pending: false, status };
}

/** Test helper — reset in-memory state between tests. */
export function resetModuleSettingsStore(module) {
  if (module) {
    stores.delete(module);
    return;
  }
  stores.clear();
}
