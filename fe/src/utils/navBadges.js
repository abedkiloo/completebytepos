/**
 * Nav badge helpers for pending tasks, approvals, and customer debtors.
 */

import {
  dailyTasksAPI,
  pendingChangesAPI,
  customersAPI,
  expensesAPI,
} from '../services/api';

export const NAV_BADGES_REFRESH_EVENT = 'navBadgesRefresh';

/** Notify sidebar / login summary to reload pending counts. */
export function dispatchNavBadgesRefresh() {
  window.dispatchEvent(new CustomEvent(NAV_BADGES_REFRESH_EVENT));
}

export function formatNavBadgeCount(count) {
  const n = Number(count) || 0;
  if (n <= 0) return null;
  return n > 99 ? '99+' : String(n);
}

/** Map a nav link target to a badge count key. */
export function navBadgeCountForItem(item, counts = {}) {
  if (!item?.to) return 0;
  const path = item.to.split('?')[0];
  if (path === '/daily-notes') return counts.pendingTasks || 0;
  if (path === '/pending-approvals') return counts.pendingApprovals || 0;
  if (path === '/customers/debt') return counts.debtors || 0;
  return 0;
}

/**
 * Load open task + approval + debtor queue sizes for the signed-in user.
 * Callers should gate fetch flags by permission / feature settings.
 */
export async function fetchNavBadgeCounts({
  mayFetchTasks = false,
  mayFetchApprovals = false,
  mayFetchDebtors = false,
} = {}) {
  const counts = { pendingTasks: 0, pendingApprovals: 0, debtors: 0 };

  const tasksPromise = mayFetchTasks
    ? dailyTasksAPI.pending().then((res) => (Array.isArray(res.data) ? res.data.length : 0)).catch(() => 0)
    : Promise.resolve(0);

  const approvalsPromise = mayFetchApprovals
    ? Promise.all([
        pendingChangesAPI
          .pending()
          .then((res) => (Array.isArray(res.data) ? res.data.length : 0))
          .catch(() => 0),
        expensesAPI
          .list({ status: 'pending', show_all: 'true', page_size: 1 })
          .then((res) => {
            if (Number.isFinite(Number(res.data?.count))) {
              return Number(res.data.count);
            }
            return Array.isArray(res.data) ? res.data.length : 0;
          })
          .catch(() => 0),
      ]).then(([changes, expenses]) => changes + expenses)
    : Promise.resolve(0);

  const debtorsPromise = mayFetchDebtors
    ? customersAPI
        .debtorCount()
        .then((res) => Number(res.data?.count) || 0)
        .catch(() => 0)
    : Promise.resolve(0);

  const [pendingTasks, pendingApprovals, debtors] = await Promise.all([
    tasksPromise,
    approvalsPromise,
    debtorsPromise,
  ]);
  counts.pendingTasks = pendingTasks;
  counts.pendingApprovals = pendingApprovals;
  counts.debtors = debtors;
  return counts;
}
