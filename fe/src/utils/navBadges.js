import { dailyTasksAPI, pendingChangesAPI } from '../services/api';

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
  return 0;
}

/**
 * Load open task + approval queue sizes for the signed-in user.
 * Callers should gate `mayFetchTasks` / `mayFetchApprovals` by permission.
 */
export async function fetchNavBadgeCounts({ mayFetchTasks = false, mayFetchApprovals = false } = {}) {
  const counts = { pendingTasks: 0, pendingApprovals: 0 };

  const tasksPromise = mayFetchTasks
    ? dailyTasksAPI.pending().then((res) => (Array.isArray(res.data) ? res.data.length : 0)).catch(() => 0)
    : Promise.resolve(0);

  const approvalsPromise = mayFetchApprovals
    ? pendingChangesAPI
        .pending()
        .then((res) => (Array.isArray(res.data) ? res.data.length : 0))
        .catch(() => 0)
    : Promise.resolve(0);

  const [pendingTasks, pendingApprovals] = await Promise.all([tasksPromise, approvalsPromise]);
  counts.pendingTasks = pendingTasks;
  counts.pendingApprovals = pendingApprovals;
  return counts;
}
