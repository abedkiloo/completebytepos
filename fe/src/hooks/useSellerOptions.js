import { useEffect, useState } from 'react';
import { salesAPI } from '../services/api';

/** "Sold by" filter options; only loaded for users who see store-wide sales. */
export function useSellerOptions(enabled) {
  const [options, setOptions] = useState([]);

  useEffect(() => {
    if (!enabled) {
      setOptions([]);
      return undefined;
    }
    let cancelled = false;
    salesAPI
      .sellers()
      .then((res) => {
        if (cancelled) return;
        const rows = Array.isArray(res?.data) ? res.data : [];
        setOptions(
          rows.map((row) => ({
            id: String(row.id),
            name: row.display_name || row.username || `User ${row.id}`,
          }))
        );
      })
      .catch(() => {
        if (!cancelled) setOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return options;
}
