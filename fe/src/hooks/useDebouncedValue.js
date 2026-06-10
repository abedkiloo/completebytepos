import { useEffect, useState } from 'react';

/** Default delay for list/search API calls (ms). */
export const SEARCH_DEBOUNCE_MS = 450;

/**
 * Returns a value that updates after `delay` ms of stability.
 * Use for search inputs: bind the input to `value`, run fetches on `debounced`.
 */
export function useDebouncedValue(value, delay = SEARCH_DEBOUNCE_MS) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
