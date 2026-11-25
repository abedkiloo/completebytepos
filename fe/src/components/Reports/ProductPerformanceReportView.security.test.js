import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import {
  reportsLegacyReportEnabled,
  reportsProductTrendsEnabled,
  userMayViewProductTrends,
} from '../../utils/reportDisplay';
import * as moduleFeatures from '../../utils/moduleFeatures';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({
    settings: {
      enable_sales_reports: true,
      enable_product_reports: false,
      enable_cash_reports: false,
      enable_inventory_reports: false,
      enable_invoice_reports: false,
      enable_financial_reports: false,
      show_legacy_report_catalog: false,
    },
  }),
}));

jest.mock('../../utils/moduleFeatures', () => ({
  isModuleFeatureEnabled: jest.fn(() => false),
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({ permissions: [] }),
  hasPermission: () => false,
}));

jest.mock('../../services/api', () => ({
  reportsAPI: {
    salesOverview: jest.fn(),
    topProducts: jest.fn(),
    cashAndPayments: jest.fn(),
    inventoryHealth: jest.fn(),
    customerOutstanding: jest.fn(),
    exportFile: jest.fn(),
  },
}));

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
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

jest.mock('../Inventory/CheckpointMarkersStrip', () => () => null);
jest.mock('./PeriodPills', () => () => null);
jest.mock('./ReportExportButtons', () => () => null);
jest.mock('../ui/card', () => ({
  Card: ({ children }) => <div>{children}</div>,
  CardHeader: ({ children }) => <div>{children}</div>,
  CardTitle: ({ children }) => <div>{children}</div>,
  CardContent: ({ children }) => <div>{children}</div>,
}));
jest.mock('../ui/skeleton', () => ({
  Skeleton: () => <div>skeleton</div>,
}));
jest.mock('lucide-react', () => ({
  ArrowRight: () => null,
  Package: () => null,
  Receipt: () => null,
  ShoppingCart: () => null,
  TrendingUp: () => null,
  Users: () => null,
  Wallet: () => null,
}));

import ReportsHub from './ReportsHub';

describe('Product performance report security / module gate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    moduleFeatures.isModuleFeatureEnabled.mockReturnValue(false);
  });

  it('denies product-performance when package feature or product reports are off', () => {
    expect(
      reportsLegacyReportEnabled({ enable_product_reports: false }, 'product-performance')
    ).toBe(false);
    expect(reportsProductTrendsEnabled({ enable_product_reports: true })).toBe(false);
    expect(
      userMayViewProductTrends([{ module: 'reports', action: 'view' }], {
        enable_product_reports: true,
      })
    ).toBe(false);
    expect(userMayViewProductTrends([], { enable_product_reports: true })).toBe(false);
  });

  it('hides the hub card when product performance is disabled', async () => {
    const { reportsAPI } = require('../../services/api');
    reportsAPI.salesOverview.mockResolvedValue({
      data: { summary: {}, trend: [] },
    });
    render(<ReportsHub />);
    await waitFor(() => {
      expect(reportsAPI.salesOverview).toHaveBeenCalled();
    });
    expect(screen.queryByTestId('product-performance-hub-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('product-performance-hub-open')).not.toBeInTheDocument();
    expect(screen.queryByText('Product performance')).not.toBeInTheDocument();
  });
});

