import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import TradingProfitReportView from './TradingProfitReportView';
import { reportsAPI } from '../../services/api';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
  useNavigate: () => jest.fn(),
}));

jest.mock('../../services/api', () => ({
  reportsAPI: {
    tradingProfit: jest.fn(),
    tradingProfitBreakdown: jest.fn(),
    exportFile: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

jest.mock('../../utils/moduleFeatures', () => ({
  isModuleFeatureEnabled: () => true,
}));

const summaryPayload = {
  period: 'month',
  date_from: '2026-11-01',
  date_to: '2026-11-06',
  summary: {
    gross_sales: 350,
    refunds: 0,
    net_sales: 350,
    cogs: 80,
    gross_profit: 270,
    expenses: 0,
    expenses_excluded: 0,
    other_income: 0,
    net_profit: 270,
    collected_on_sales: 350,
    debt_collections: 0,
    cash_in_period: 350,
    unpaid_on_sales: 0,
    cash_gross_profit: 270,
    cash_net_profit: 270,
    tax_amount: 0,
    purchases: 0,
    sale_count: 2,
  },
};

const grossBreakdown = {
  metric: 'gross_sales',
  title: 'Gross sales',
  formula: 'Sum of sale totals',
  explanation: 'Sum of completed sale totals in this period (business date).',
  total: 350,
  row_count: 2,
  rows_shown: 2,
  truncated: false,
  date_from: '2026-11-01',
  date_to: '2026-11-06',
  rows: [
    {
      id: 1,
      label: 'S-GS-CASH',
      sublabel: '2026-11-06 · cash · paid 100',
      amount: 100,
      lines: [{ product_name: 'GS Item', quantity: 1, unit_price: 100, line_total: 100 }],
    },
    {
      id: 2,
      label: 'S-GS-MPESA',
      sublabel: '2026-11-06 · mpesa · paid 250',
      amount: 250,
      lines: [{ product_name: 'GS Item', quantity: 1, unit_price: 250, line_total: 250 }],
    },
  ],
};

describe('Trading profit Gross sales breakdown export', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    reportsAPI.tradingProfit.mockResolvedValue({ data: summaryPayload });
    reportsAPI.tradingProfitBreakdown.mockResolvedValue({ data: grossBreakdown });
    reportsAPI.exportFile.mockResolvedValue('gross-sales.xlsx');
  });

  it('opens Gross sales and downloads Excel/CSV that use the same period metric', async () => {
    render(<TradingProfitReportView />);

    await waitFor(() => {
      expect(screen.getByText('Gross sales')).toBeInTheDocument();
    });

    const grossLabel = screen.getByText('Gross sales');
    const grossRow = grossLabel.closest('div');
    const grossButton = grossRow.querySelector('button');
    expect(grossButton).toBeTruthy();
    fireEvent.click(grossButton);

    await waitFor(() => {
      expect(reportsAPI.tradingProfitBreakdown).toHaveBeenCalledWith(
        expect.objectContaining({ period: 'month', metric: 'gross_sales' })
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/Items \(2\)/i)).toBeInTheDocument();
    });

    expect(screen.getByTestId('gross-sales-download-excel')).toBeInTheDocument();
    expect(screen.getByTestId('gross-sales-download-csv')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('gross-sales-download-excel'));
    await waitFor(() => {
      expect(reportsAPI.exportFile).toHaveBeenCalledWith(
        'trading-profit-breakdown',
        expect.objectContaining({ metric: 'gross_sales' }),
        'xlsx'
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId('gross-sales-download-csv')).not.toBeDisabled();
    });

    fireEvent.click(screen.getByTestId('gross-sales-download-csv'));
    await waitFor(() => {
      expect(reportsAPI.exportFile).toHaveBeenLastCalledWith(
        'trading-profit-breakdown',
        expect.objectContaining({ metric: 'gross_sales' }),
        'csv'
      );
    });
  });
});
