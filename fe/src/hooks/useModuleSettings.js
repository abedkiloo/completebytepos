import { useCallback, useEffect, useState } from 'react';
import {
  applyModuleSettingsPayload,
  ensureModuleSettingsLoaded,
  getModuleSettingsSnapshot,
  patchModuleSettings,
  resetModuleSettingsStore,
  subscribeModuleSettings,
} from '../utils/moduleSettingsStore';

/**
 * Per-module settings from GET/PATCH /api/settings/{module}/.
 * Multiple hooks for the same module share one in-flight fetch and in-memory state.
 */
export function useModuleSettings(module) {
  const [, bump] = useState(0);
  const rerender = useCallback(() => bump((n) => n + 1), []);

  useEffect(() => {
    const unsubscribe = subscribeModuleSettings(module, rerender);
    ensureModuleSettingsLoaded(module).catch(() => {});

    const onUpdated = (event) => {
      if (event.detail?.module === module) {
        applyModuleSettingsPayload(module, event.detail);
      }
    };
    window.addEventListener('moduleSettingsUpdated', onUpdated);
    return () => {
      unsubscribe();
      window.removeEventListener('moduleSettingsUpdated', onUpdated);
    };
  }, [module, rerender]);

  const { settings, meta, loading } = getModuleSettingsSnapshot(module);

  const refresh = useCallback(async () => {
    resetModuleSettingsStore(module);
    await ensureModuleSettingsLoaded(module);
    return getModuleSettingsSnapshot(module).settings;
  }, [module]);

  const patch = useCallback(
    async (values, options) => patchModuleSettings(module, values, options),
    [module]
  );

  return { settings, meta, loading, refresh, patch };
}
