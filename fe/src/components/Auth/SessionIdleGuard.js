import { useEffect } from 'react';

import {
  startIdleSessionWatch,
  stopIdleSessionWatch,
} from '../../utils/sessionIdle';

/** Starts the inactivity timer for authenticated routes. */
export default function SessionIdleGuard() {
  useEffect(() => {
    startIdleSessionWatch();
    return () => stopIdleSessionWatch();
  }, []);

  return null;
}
