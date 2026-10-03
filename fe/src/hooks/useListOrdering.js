import { useState } from 'react';

export function useListOrdering(initial = '') {
  const [ordering, setOrdering] = useState(initial);
  return { ordering, setOrdering };
}
