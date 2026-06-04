import { useCallback, useEffect, useState } from 'react';
import { productsAPI } from '../services/api';

const FALLBACK_UNITS = [
  { id: 'piece', name: 'Piece' },
  { id: 'kg', name: 'Kilogram' },
  { id: 'roll', name: 'Roll' },
];

export function useProductUnits() {
  const [options, setOptions] = useState(FALLBACK_UNITS);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await productsAPI.units.options();
      const rows = res.data?.results || [];
      if (rows.length) {
        setOptions(rows.map((u) => ({ id: u.code, name: u.label })));
      }
    } catch {
      setOptions(FALLBACK_UNITS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { options, loading, refresh };
}
