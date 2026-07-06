import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ReportsHub from './ReportsHub';
import { reportsAPI } from '../../services/api';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({
    settings: {
      enable_sales_reports: true,
      enable_product_reports: true,
      enable_cash_reports: true,
      enable_inventory_reports: true,
      enable_invoice_reports: true,
      show_discount_in_reports: true,
      show_tax_in_reports: true,
      show_legacy_report_catalog: true,
    },
  }),
}));

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div data-testid="chart">{children}</div>,
  LineChart: ({ children }) => <div>{children}</div>,
  BarChart: ({ children }) => <div>{children}</div>,
  PieChart: ({ children }) => <div>{children}</div>,
  Line: () => null,
  Bar: () => null,
  Pie: () => null,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));

const emptyOverview = {
  summary: { gross_revenue: 0, sales_count: 0, avg_ticket: 0, items_sold: 0 },
  trend: [],
};
const emptyProducts = { items: [] };
const emptyCash = { summary: {}, by_method: [] };
const emptyInventory = { summary: {}, at_risk: [] };
const emptyOutstanding = { summary: {}, aging: [] };

jest.mock('../../services/api', () => ({
  reportsAPI: {
    salesOverview: jest.fn(),
    topProducts: jest.fn(),
    cashAndPayments: jest.fn(),
    inventoryHealth: jest.fn(),
    customerOutstanding: jest.fn(),
  },
}));

describe('ReportsHub period picker', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    reportsAPI.salesOverview.mockResolvedValue({ data: emptyOverview });
    reportsAPI.topProducts.mockResolvedValue({ data: emptyProducts });
    reportsAPI.cashAndPayments.mockResolvedValue({ data: emptyCash });
    reportsAPI.inventoryHealth.mockResolvedValue({ data: emptyInventory });
    reportsAPI.customerOutstanding.mockResolvedValue({ data: emptyOutstanding });
  });

  it('renders global period pills and defaults to this month', async () => {
    render(<ReportsHub />);

    expect(screen.getByRole('tablist', { name: 'Report period' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'This month' })).toHaveAttribute('aria-selected', 'true');

    await waitFor(() => {
      expect(reportsAPI.salesOverview).toHaveBeenCalledWith({ period: 'month' });
    });
  });

  it('refetches all tiles when the period changes', async () => {
    render(<ReportsHub />);

    await waitFor(() => expect(reportsAPI.salesOverview).toHaveBeenCalled());

    jest.clearAllMocks();
    reportsAPI.salesOverview.mockResolvedValue({ data: emptyOverview });
    reportsAPI.topProducts.mockResolvedValue({ data: emptyProducts });
    reportsAPI.cashAndPayments.mockResolvedValue({ data: emptyCash });
    reportsAPI.inventoryHealth.mockResolvedValue({ data: emptyInventory });
    reportsAPI.customerOutstanding.mockResolvedValue({ data: emptyOutstanding });

    fireEvent.click(screen.getByRole('tab', { name: 'Today' }));

    await waitFor(() => {
      expect(reportsAPI.salesOverview).toHaveBeenCalledWith({ period: 'today' });
      expect(reportsAPI.topProducts).toHaveBeenCalledWith({ period: 'today' });
      expect(reportsAPI.cashAndPayments).toHaveBeenCalledWith({ period: 'today' });
      expect(reportsAPI.inventoryHealth).toHaveBeenCalledWith({ period: 'today' });
      expect(reportsAPI.customerOutstanding).toHaveBeenCalledWith({ period: 'today' });
    });
  });
});
