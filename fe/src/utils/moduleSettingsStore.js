/**
 * In-memory module settings store — dedupes GET /api/settings/{module}/ across hooks.
 */

import { moduleSettingsAPI } from '../services/api';
import { toast } from './toast';
import { isPendingApprovalResponse, PENDING_APPROVAL_MESSAGE } from './makerChecker';
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

export async function patchModuleSettings(module, values, options = {}) {
  const payload = { ...values };
  if (options.reason) {
    payload.reason = options.reason;
  }
  const res = await moduleSettingsAPI.patch(module, payload);
  if (isPendingApprovalResponse(res.status)) {
    toast.warning(PENDING_APPROVAL_MESSAGE);
    return getModuleSettingsSnapshot(module).settings;
  }
  const flat = applyModuleSettingsPayload(module, res.data);
  window.dispatchEvent(new CustomEvent('moduleSettingsUpdated', { detail: res.data }));
  return flat;
}

/** Test helper — reset in-memory state between tests. */
export function resetModuleSettingsStore(module) {
  if (module) {
    stores.delete(module);
    return;
  }
  stores.clear();
}
