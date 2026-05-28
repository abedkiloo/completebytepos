import { useCallback, useEffect, useState } from 'react';
import { isProductVariantsEnabled } from '../utils/moduleFeatures';
import { modulesAPI } from '../services/api';

/**
 * Whether size/color variants are enabled (Module Settings → Products).
 * Refreshes when enabled_modules is written to localStorage.
 */
export function useProductVariantsEnabled() {
  const read = useCallback(() => isProductVariantsEnabled(), []);

  const [enabled, setEnabled] = useState(read);

  useEffect(() => {
    const refresh = () => setEnabled(read());

    const onStorage = (e) => {
      if (!e.key || e.key === 'enabled_modules') refresh();
    };
    window.addEventListener('storage', onStorage);

    // Layout may populate modules after first paint — one fetch if cache empty.
    const cached = localStorage.getItem('enabled_modules');
    if (!cached || cached === '{}') {
      modulesAPI
        .list()
        .then((res) => {
          const data = res.data || {};
          localStorage.setItem('enabled_modules', JSON.stringify(data));
          refresh();
        })
        .catch(() => {});
    }

    return () => window.removeEventListener('storage', onStorage);
  }, [read]);

  return enabled;
}
