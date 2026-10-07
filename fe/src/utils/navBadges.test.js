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
    pendingCount: jest.fn(),
  },
  pendingChangesAPI: {
    pending: jest.fn(),
    pendingCount: jest.fn(),
  },
  salesAPI: {
    list: jest.fn(),
  },
  customersAPI: {
    debtorCount: jest.fn(),
  },
  expensesAPI: {
    list: jest.fn(),
  },
}));

import {
  dailyTasksAPI,
  pendingChangesAPI,
  customersAPI,
  expensesAPI,
  salesAPI,
} from '../services/api';

describe('navBadges', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('formatNavBadgeCount caps at 99+', () => {
    expect(formatNavBadgeCount(0)).toBeNull();
    expect(formatNavBadgeCount(3)).toBe('3');
    expect(formatNavBadgeCount(120)).toBe('99+');
  });

  test('navBadgeCountForItem maps daily notes, approvals, and debt paths', () => {
    const counts = { pendingTasks: 4, pendingApprovals: 2, debtors: 7, saleApprovals: 6 };
    expect(navBadgeCountForItem({ to: '/daily-notes' }, counts)).toBe(4);
    expect(navBadgeCountForItem({ to: '/pending-approvals' }, counts)).toBe(2);
    expect(navBadgeCountForItem({ to: '/customers/debt' }, counts)).toBe(7);
    expect(navBadgeCountForItem({ to: '/sales/approvals' }, counts)).toBe(6);
    expect(navBadgeCountForItem({ to: '/products' }, counts)).toBe(0);
  });

  test('fetchNavBadgeCounts loads all queues when allowed', async () => {
    dailyTasksAPI.pendingCount.mockResolvedValue({ data: { count: 2 } });
    pendingChangesAPI.pendingCount.mockImplementation((params) => {
      if (params?.action_type === 'debt_collection') {
        return Promise.resolve({ data: { count: 2 } });
      }
      return Promise.resolve({ data: { count: 1 } });
    });
    expensesAPI.list.mockResolvedValue({ data: { count: 3, results: [] } });
    customersAPI.debtorCount.mockResolvedValue({ data: { count: 5 } });
    salesAPI.list.mockResolvedValue({ data: { count: 4, results: [] } });

    await expect(
      fetchNavBadgeCounts({
        mayFetchTasks: true,
        mayFetchApprovals: true,
        mayFetchDebtors: true,
        mayFetchSaleApprovals: true,
      })
    ).resolves.toEqual({
      pendingTasks: 2,
      pendingApprovals: 4,
      debtors: 5,
      saleApprovals: 6,
    });
    expect(dailyTasksAPI.pendingCount).toHaveBeenCalled();
    expect(pendingChangesAPI.pendingCount).toHaveBeenCalledWith({
      exclude_action_type: 'sale_complete,debt_collection',
    });
    expect(expensesAPI.list).toHaveBeenCalledWith({
      status: 'pending',
      show_all: 'true',
      page_size: 1,
    });
    expect(salesAPI.list).toHaveBeenCalledWith({
      status: 'pending_approval',
      page_size: 1,
    });
  });

  test('fetchNavBadgeCounts skips disallowed queues', async () => {
    await expect(
      fetchNavBadgeCounts({
        mayFetchTasks: false,
        mayFetchApprovals: false,
        mayFetchDebtors: false,
        mayFetchSaleApprovals: false,
      })
    ).resolves.toEqual({
      pendingTasks: 0,
      pendingApprovals: 0,
      debtors: 0,
      saleApprovals: 0,
    });
    expect(dailyTasksAPI.pendingCount).not.toHaveBeenCalled();
    expect(pendingChangesAPI.pendingCount).not.toHaveBeenCalled();
    expect(expensesAPI.list).not.toHaveBeenCalled();
    expect(customersAPI.debtorCount).not.toHaveBeenCalled();
    expect(salesAPI.list).not.toHaveBeenCalled();
  });

  test('dispatchNavBadgesRefresh fires a window event', () => {
    const handler = jest.fn();
    window.addEventListener(NAV_BADGES_REFRESH_EVENT, handler);
    dispatchNavBadgesRefresh();
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener(NAV_BADGES_REFRESH_EVENT, handler);
  });
});
