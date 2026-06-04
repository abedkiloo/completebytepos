import { useCallback, useEffect, useState } from 'react';
import { isProductVariantsEnabled } from '../utils/moduleFeatures';
import { normalizeModuleSettings } from '../utils/moduleCache';
import { modulesAPI } from '../services/api';

/**
 * Whether size/color variants are enabled (Module Settings → Products).
 * Refreshes when enabled_modules is written or moduleSettingsUpdated fires.
 */
export function useProductVariantsEnabled() {
  const read = useCallback(() => isProductVariantsEnabled(), []);

  const [enabled, setEnabled] = useState(read);

  useEffect(() => {
    const refresh = () => setEnabled(read());

    const onStorage = (e) => {
      if (!e.key || e.key === 'enabled_modules') refresh();
    };
    const onModulesUpdated = () => refresh();

    window.addEventListener('storage', onStorage);
    window.addEventListener('moduleSettingsUpdated', onModulesUpdated);

    const cached = localStorage.getItem('enabled_modules');
    if (!cached || cached === '{}') {
      modulesAPI
        .list()
        .then((res) => {
          const flat = normalizeModuleSettings(res.data || {});
          delete flat.catalog;
          localStorage.setItem('enabled_modules', JSON.stringify(flat));
          refresh();
        })
        .catch(() => {});
    }

    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('moduleSettingsUpdated', onModulesUpdated);
    };
  }, [read]);

  return enabled;
}
