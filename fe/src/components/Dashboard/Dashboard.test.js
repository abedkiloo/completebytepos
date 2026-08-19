import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import Dashboard from './Dashboard';
import { reportsAPI, productsAPI, salesAPI, authAPI } from '../../services/api';
import { getStoredAuth, hasPermission, resolvePersona } from '../../utils/roleAccess';
import {
  getDefaultPosRoute,
  isBillingPosEnabled,
  isRetailPosEnabled,
} from '../../utils/moduleFeatures';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({ settings: { enable_dashboard_summary: true } }),
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: jest.fn(),
  hasPermission: jest.fn(),
  resolvePersona: jest.fn(),
}));

jest.mock('../../utils/moduleFeatures', () => ({
  getDefaultPosRoute: jest.fn(),
  isBillingPosEnabled: jest.fn(),
  isRetailPosEnabled: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  reportsAPI: { dashboard: jest.fn() },
  salesAPI: { dashboardSummary: jest.fn(), list: jest.fn() },
  productsAPI: { list: jest.fn() },
  authAPI: { me: jest.fn() },
}));

const weekDays = [
  { date: '2026-08-12', label: 'Wed', sales_count: 0, total: 0 },
  { date: '2026-08-13', label: 'Thu', sales_count: 0, total: 0 },
  { date: '2026-08-14', label: 'Fri', sales_count: 1, total: 50 },
  { date: '2026-08-15', label: 'Sat', sales_count: 0, total: 0 },
  { date: '2026-08-16', label: 'Sun', sales_count: 0, total: 0 },
  { date: '2026-08-17', label: 'Mon', sales_count: 0, total: 0 },
  { date: '2026-08-18', label: 'Tue', sales_count: 2, total: 150 },
];

describe('Dashboard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getStoredAuth.mockReturnValue({
      permissions: [{ module: 'reports', action: 'view' }],
    });
    hasPermission.mockReturnValue(true);
    resolvePersona.mockReturnValue('manager');
    getDefaultPosRoute.mockReturnValue('/pos');
    isBillingPosEnabled.mockReturnValue(false);
    isRetailPosEnabled.mockReturnValue(true);
    authAPI.me.mockResolvedValue({
      data: { user: { username: 'Ada' }, profile: { role_display: 'Manager' } },
    });
    reportsAPI.dashboard.mockResolvedValue({
      data: {
        today: { sales_count: 2, total: 150 },
        week: { sales_count: 3, total: 200, days: weekDays },
        month: { total: 800 },
        low_stock_count: 1,
        profit: 9999,
        growth: { sales: 0, profit: 12 },
      },
    });
    productsAPI.list.mockResolvedValue({
      data: { results: [{ id: 4, name: 'Milk', sku: 'M-1', stock_quantity: 2 }] },
    });
    salesAPI.list.mockResolvedValue({
      data: {
        results: [
          { id: 1, sale_number: 'S-1', status: 'completed', total: 40, created_at: '2026-08-18T10:00:00Z' },
          { id: 2, sale_number: 'HOLD', status: 'holding', total: 9 },
        ],
      },
    });
  });

  it('shows weekly sales and hides profit', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('This week')).toBeInTheDocument();
    });

    expect(screen.getByText('Weekly sales')).toBeInTheDocument();
    expect(screen.getAllByText(/3 orders/).length).toBeGreaterThan(0);
    expect(screen.queryByText('Profit (est.)')).not.toBeInTheDocument();
    expect(screen.getByText('S-1')).toBeInTheDocument();
    expect(screen.queryByText('HOLD')).not.toBeInTheDocument();
    expect(screen.getAllByText(/Milk/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/2 orders today/).length).toBeGreaterThan(0);
  });

  it('shows a loading skeleton until data arrives', () => {
    reportsAPI.dashboard.mockReturnValue(new Promise(() => {}));
    const { container } = render(<Dashboard />);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it('falls back to the sales summary when reports.view is missing', async () => {
    hasPermission.mockReturnValue(false);
    getStoredAuth.mockReturnValue({ permissions: [] });
    salesAPI.dashboardSummary.mockResolvedValue({
      data: {
        today: { sales_count: 1, total: 10 },
        week: { sales_count: 1, total: 10, days: weekDays },
      },
    });
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText('This week')).toBeInTheDocument();
    });
    expect(salesAPI.dashboardSummary).toHaveBeenCalled();
    expect(reportsAPI.dashboard).not.toHaveBeenCalled();
    expect(screen.queryByText('Month revenue')).not.toBeInTheDocument();
  });

  it('uses sales quick actions and billing POS copy', async () => {
    resolvePersona.mockReturnValue('sales');
    isBillingPosEnabled.mockReturnValue(true);
    isRetailPosEnabled.mockReturnValue(false);
    getDefaultPosRoute.mockReturnValue('/pos/billing');
    authAPI.me.mockResolvedValue({
      data: { user: { first_name: 'Kai' }, profile: { custom_role: { name: 'Cashier' } } },
    });
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getAllByText(/Start sale/).length).toBeGreaterThan(0);
    });
    expect(screen.getByText('Terminal POS checkout')).toBeInTheDocument();
    expect(screen.queryByText('Low stock SKUs')).not.toBeInTheDocument();
    expect(screen.getByText(/Your shift focus/)).toBeInTheDocument();
  });

  it('tolerates failed loads and empty week days', async () => {
    authAPI.me.mockRejectedValue(new Error('nope'));
    reportsAPI.dashboard.mockRejectedValue(new Error('dash'));
    productsAPI.list.mockRejectedValue(new Error('stock'));
    salesAPI.list.mockRejectedValue(new Error('sales'));
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText('there')).toBeInTheDocument();
    });
    expect(screen.queryByText('Weekly sales')).not.toBeInTheDocument();
    expect(screen.getByText('No sales yet.')).toBeInTheDocument();
    expect(screen.getByText('All products are adequately stocked.')).toBeInTheDocument();
  });

  it('uses sales persona copy, singular order, and sale fallbacks', async () => {
    resolvePersona.mockReturnValue('sales');
    isBillingPosEnabled.mockReturnValue(false);
    isRetailPosEnabled.mockReturnValue(true);
    getDefaultPosRoute.mockReturnValue('/pos');
    reportsAPI.dashboard.mockResolvedValue({
      data: {
        today: { sales_count: 1, total: 40 },
        week: {
          sales_count: 1,
          total: 40,
          days: [{ date: '2026-08-18', label: 'Tue', sales_count: 1, total: 40 }],
        },
        month: { total: 40 },
        growth: { sales: 4 },
      },
    });
    salesAPI.list.mockResolvedValue({
      data: [{ id: 9, status: 'completed', total: 40 }],
    });
    productsAPI.list.mockResolvedValue({ data: [{ id: 4, name: 'Milk', sku: 'M-1', stock_quantity: 2 }] });
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getAllByText(/Start sale/).length).toBeGreaterThan(0);
    });
    expect(screen.getByText('Retail POS checkout')).toBeInTheDocument();
    expect(screen.getByText('This month')).toBeInTheDocument();
    expect(screen.getByText('1 order today')).toBeInTheDocument();
    expect(screen.getByText('Sale #9')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.queryByText('Low stock SKUs')).not.toBeInTheDocument();
    expect(screen.getByText(/walk-in cash\/card sales/)).toBeInTheDocument();
  });

  it('falls back to sales actions for an unknown persona', async () => {
    resolvePersona.mockReturnValue('warehouse');
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getAllByText(/Start sale/).length).toBeGreaterThan(0);
    });
  });

  it('mentions retail POS when both terminals are enabled', async () => {
    resolvePersona.mockReturnValue('sales');
    isBillingPosEnabled.mockReturnValue(true);
    isRetailPosEnabled.mockReturnValue(true);
    getDefaultPosRoute.mockReturnValue('/pos/billing');
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/Retail POS is also available/)).toBeInTheDocument();
    });
  });
});
