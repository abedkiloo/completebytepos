import React from 'react';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { periodToDateFilters } from '../../utils/reportPeriods';

const mockSearchParams = { current: new URLSearchParams('report=sales') };
const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [mockSearchParams.current, jest.fn()],
  Link: ({ to, children, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({
    settings: {
      enable_sales_reports: true,
      show_discount_in_reports: true,
      show_tax_in_reports: true,
      show_cost_and_profit: true,
    },
  }),
}));

jest.mock('../../services/api', () => ({
  reportsAPI: {
    sales: jest.fn(),
    purchase: jest.fn(),
    products: jest.fn(),
    inventory: jest.fn(),
    invoice: jest.fn(),
    supplier: jest.fn(),
    customer: jest.fn(),
    expense: jest.fn(),
    income: jest.fn(),
    tax: jest.fn(),
    profitLoss: jest.fn(),
    annual: jest.fn(),
    salesOverview: jest.fn(),
    topProducts: jest.fn(),
    cashAndPayments: jest.fn(),
    inventoryHealth: jest.fn(),
    customerOutstanding: jest.fn(),
    salesByPerson: jest.fn(),
    salesByPersonCsv: jest.fn(),
    exportFile: jest.fn(),
  },
}));

jest.mock('../page', () => ({
  PageShell: ({ children }) => <div>{children}</div>,
  PageHeader: ({ title, children }) => (
    <div>
      <h1>{title}</h1>
      {children}
    </div>
  ),
  FilterBar: ({ children }) => <div>{children}</div>,
  FilterField: ({ label, children, className }) => (
    <div className={className}>
      {label ? <span>{label}</span> : null}
      {children}
    </div>
  ),
  PageLoading: () => <div>Loading…</div>,
  EmptyState: ({ title }) => <div>{title}</div>,
}));

const Reports = require('./Reports').default;
const { reportsAPI } = require('../../services/api');

describe('Reports detail period filters', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearchParams.current = new URLSearchParams('report=sales');
    reportsAPI.sales.mockResolvedValue({
      data: {
        summary: { total_sales: 1, total_revenue: 100, total_items: 1 },
        by_payment_method: [],
        daily_breakdown: [],
      },
    });
  });

  it('loads sales report with default this-month date range', async () => {
    const monthRange = periodToDateFilters('month');

    render(<Reports />);

    await waitFor(() => {
      expect(reportsAPI.sales).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: monthRange.date_from,
          date_to: monthRange.date_to,
        })
      );
    });

    expect(
      within(screen.getByRole('tablist', { name: 'Report period' })).getByRole('tab', {
        name: 'This month',
      })
    ).toHaveAttribute('aria-selected', 'true');
  });

  it('updates API params when today period is selected', async () => {
    render(<Reports />);
    await waitFor(() => expect(reportsAPI.sales).toHaveBeenCalled());

    jest.clearAllMocks();
    reportsAPI.sales.mockResolvedValue({
      data: {
        summary: { total_sales: 0, total_revenue: 0, total_items: 0 },
        by_payment_method: [],
        daily_breakdown: [],
      },
    });

    const periodTabs = within(screen.getByRole('tablist', { name: 'Report period' }));
    fireEvent.click(periodTabs.getByRole('tab', { name: 'Today' }));

    const todayRange = periodToDateFilters('today');
    await waitFor(() => {
      expect(reportsAPI.sales).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: todayRange.date_from,
          date_to: todayRange.date_to,
        })
      );
    });
  });

  it('updates API params when this year period is selected', async () => {
    render(<Reports />);
    await waitFor(() => expect(reportsAPI.sales).toHaveBeenCalled());

    jest.clearAllMocks();
    reportsAPI.sales.mockResolvedValue({
      data: {
        summary: { total_sales: 0, total_revenue: 0, total_items: 0 },
        by_payment_method: [],
        daily_breakdown: [],
      },
    });

    const periodTabs = within(screen.getByRole('tablist', { name: 'Report period' }));
    fireEvent.click(periodTabs.getByRole('tab', { name: 'This year' }));

    const yearRange = periodToDateFilters('year');
    await waitFor(() => {
      expect(reportsAPI.sales).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: yearRange.date_from,
          date_to: yearRange.date_to,
        })
      );
    });
  });

  it('exports PDF of the current sales filters', async () => {
    reportsAPI.exportFile.mockResolvedValue('sales.pdf');
    const monthRange = periodToDateFilters('month');
    render(<Reports />);
    await waitFor(() => expect(reportsAPI.sales).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }));
    await waitFor(() => {
      expect(reportsAPI.exportFile).toHaveBeenCalledWith(
        'sales',
        expect.objectContaining({
          date_from: monthRange.date_from,
          date_to: monthRange.date_to,
        }),
        'pdf'
      );
    });
  });
});
