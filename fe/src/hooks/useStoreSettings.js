import { useCallback, useState, useEffect } from 'react';
import { storeSettingsAPI } from '../services/api';
import {
  cacheStoreSettings,
  readCachedStoreSettings,
} from '../utils/storeSettingsCache';

/**
 * Read store-wide settings (payments, receipt, catalog rules).
 * Values are cached in localStorage after the first successful fetch.
 */
export function useStoreSettings() {
  const [settings, setSettings] = useState(() => readCachedStoreSettings());

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    storeSettingsAPI
      .get()
      .then((res) => {
        cacheStoreSettings(res.data);
        setSettings(res.data);
      })
      .catch(() => {});
  }, []);

  const refresh = useCallback(async () => {
    const res = await storeSettingsAPI.get();
    cacheStoreSettings(res.data);
    setSettings(res.data);
    return res.data;
  }, []);

  const applyLocal = useCallback((patch) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      cacheStoreSettings(next);
      return next;
    });
  }, []);

  return { settings, refresh, applyLocal };
}
