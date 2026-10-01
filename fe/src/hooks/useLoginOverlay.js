import { useLayoutEffect, useState } from 'react';

import {
  getLoginOverlayState,
  subscribeLoginOverlay,
} from '../utils/loginOverlayQueue';

export function useLoginOverlayState() {
  const [overlay, setOverlay] = useState(getLoginOverlayState);
  useLayoutEffect(() => subscribeLoginOverlay(setOverlay), []);
  return overlay;
}
