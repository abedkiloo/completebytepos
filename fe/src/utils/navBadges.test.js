import {
  dispatchNavBadgesRefresh,
  fetchNavBadgeCounts,
  formatNavBadgeCount,
  navBadgeCountForItem,
  NAV_BADGES_REFRESH_EVENT,
} from './navBadges';

jest.mock('../services/api', () => ({
  dailyTasksAPI: {
    pending: jest.fn(),
  },
  pendingChangesAPI: {
    pending: jest.fn(),
  },
}));

import { dailyTasksAPI, pendingChangesAPI } from '../services/api';

describe('navBadges', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('formatNavBadgeCount caps at 99+', () => {
    expect(formatNavBadgeCount(0)).toBeNull();
    expect(formatNavBadgeCount(3)).toBe('3');
    expect(formatNavBadgeCount(120)).toBe('99+');
  });

  test('navBadgeCountForItem maps daily notes and approvals paths', () => {
    const counts = { pendingTasks: 4, pendingApprovals: 2 };
    expect(navBadgeCountForItem({ to: '/daily-notes' }, counts)).toBe(4);
    expect(navBadgeCountForItem({ to: '/pending-approvals' }, counts)).toBe(2);
    expect(navBadgeCountForItem({ to: '/products' }, counts)).toBe(0);
  });

  test('fetchNavBadgeCounts loads both queues when allowed', async () => {
    dailyTasksAPI.pending.mockResolvedValue({ data: [{ id: 1 }, { id: 2 }] });
    pendingChangesAPI.pending.mockResolvedValue({ data: [{ id: 9 }] });

    await expect(
      fetchNavBadgeCounts({ mayFetchTasks: true, mayFetchApprovals: true })
    ).resolves.toEqual({ pendingTasks: 2, pendingApprovals: 1 });
  });

  test('fetchNavBadgeCounts skips disallowed queues', async () => {
    await expect(fetchNavBadgeCounts({ mayFetchTasks: false, mayFetchApprovals: false })).resolves.toEqual({
      pendingTasks: 0,
      pendingApprovals: 0,
    });
    expect(dailyTasksAPI.pending).not.toHaveBeenCalled();
    expect(pendingChangesAPI.pending).not.toHaveBeenCalled();
  });

  test('dispatchNavBadgesRefresh fires a window event', () => {
    const handler = jest.fn();
    window.addEventListener(NAV_BADGES_REFRESH_EVENT, handler);
    dispatchNavBadgesRefresh();
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener(NAV_BADGES_REFRESH_EVENT, handler);
  });
});
