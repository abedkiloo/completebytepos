import { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { fetchNavBadgeCounts, NAV_BADGES_REFRESH_EVENT } from '../utils/navBadges';
import {
  hasPermission,
  getStoredAuth,
  userMayEditFinancialFieldsFromStorage,
  PERSONA,
} from '../utils/roleAccess';
import { useModuleSettings } from './useModuleSettings';
import { salesDailyNotesAccessEnabled } from '../utils/dailyNotesAccess';
import { customersShowWalletBalance } from '../utils/customerDisplay';
import { getPersonaFromStorage } from '../utils/navAccess';

const EMPTY_COUNTS = { pendingTasks: 0, pendingApprovals: 0, debtors: 0 };

/**
 * Pending daily-task, approval, and debtor counts for nav badges and login summary.
 */
export function useNavBadgeCounts() {
  const location = useLocation();
  const persona = getPersonaFromStorage();
  const { permissions } = getStoredAuth();
  const { settings: dailyNotesSettings, loading: dailyNotesLoading } = useModuleSettings('daily_notes');
  const { settings: customerSettings, loading: customersLoading } = useModuleSettings('customers');
  const [counts, setCounts] = useState(EMPTY_COUNTS);

  const mayFetchTasks =
    !dailyNotesLoading &&
    hasPermission(permissions, 'daily_notes', 'view') &&
    (persona !== PERSONA.SALES || salesDailyNotesAccessEnabled(dailyNotesSettings));

  const mayFetchApprovals = userMayEditFinancialFieldsFromStorage();

  const mayFetchDebtors =
    !customersLoading &&
    hasPermission(permissions, 'debt_management', 'view') &&
    customersShowWalletBalance(customerSettings);

  const refresh = useCallback(async () => {
    if (!mayFetchTasks && !mayFetchApprovals && !mayFetchDebtors) {
      setCounts(EMPTY_COUNTS);
      return;
    }
    const next = await fetchNavBadgeCounts({
      mayFetchTasks,
      mayFetchApprovals,
      mayFetchDebtors,
    });
    setCounts(next);
  }, [mayFetchTasks, mayFetchApprovals, mayFetchDebtors]);

  useEffect(() => {
    refresh();
  }, [refresh, location.pathname]);

  useEffect(() => {
    const onRefresh = () => {
      refresh();
    };
    const onFocus = () => {
      refresh();
    };
    window.addEventListener(NAV_BADGES_REFRESH_EVENT, onRefresh);
    window.addEventListener('focus', onFocus);
    const intervalId = window.setInterval(refresh, 120000);
    return () => {
      window.removeEventListener(NAV_BADGES_REFRESH_EVENT, onRefresh);
      window.removeEventListener('focus', onFocus);
      window.clearInterval(intervalId);
    };
  }, [refresh]);

  return counts;
}
