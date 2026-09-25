import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import StockValuationReportView from './StockValuationReportView';
import { reportsAPI } from '../../services/api';
import { useModuleSettings } from '../../hooks/useModuleSettings';

jest.mock('../../services/api', () => ({
  reportsAPI: {
    stockValuation: jest.fn(),
    exportFile: jest.fn(),
  },
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: () => ({ settings: { store_name: 'Omuwenga Suppliers' } }),
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: jest.fn(),
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('../page', () => ({
  PageLoading: () => <div>Loading…</div>,
  EmptyState: ({ title }) => <div>{title}</div>,
}));

const payload = {
  owner: 'Omuwenga Suppliers',
  tagline: 'Think Furniture, Think Omuwenga',
  contact: 'Tel: 0718515142',
  note: 'On-hand stock as of this moment.',
  summary: {
    line_count: 1,
    units_on_hand: 3,
    cost_value: 12000,
    retail_value: 24000,
    zero_stock_skus: 0,
  },
  lines: [
    {
      sku: 'TBL-1',
      product: 'Coffee table',
      variant: '',
      quantity: 3,
      unit_cost: 4000,
      cost_value: 12000,
      unit_price: 8000,
      retail_value: 24000,
    },
  ],
};

describe('StockValuationReportView', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useModuleSettings.mockReturnValue({ settings: { show_cost_and_profit: true } });
    reportsAPI.stockValuation.mockResolvedValue({ data: payload });
    reportsAPI.exportFile.mockResolvedValue('stock.pdf');
  });

  it('shows the store name, stock list, and totals', async () => {
    render(<StockValuationReportView />);
    expect(await screen.findByText('Coffee table')).toBeInTheDocument();
    expect(screen.getAllByText('Omuwenga Suppliers').length).toBeGreaterThan(0);
    expect(screen.getByText('TBL-1')).toBeInTheDocument();
    expect(screen.getAllByText(/Cost value/i).length).toBeGreaterThan(0);
    expect(reportsAPI.stockValuation).toHaveBeenCalledWith({ include_zero: undefined });
  });

  it('hides cost columns when the store toggle is off', async () => {
    useModuleSettings.mockReturnValue({ settings: { show_cost_and_profit: false } });
    render(<StockValuationReportView />);
    expect(await screen.findByText('Coffee table')).toBeInTheDocument();
    expect(screen.queryAllByText(/Cost value/i).length).toBe(0);
    expect(screen.getAllByText(/Retail value/i).length).toBeGreaterThan(0);
  });

  it('reloads with zero-stock SKUs when the checkbox is on', async () => {
    render(<StockValuationReportView />);
    await screen.findByText('Coffee table');
    fireEvent.click(screen.getByLabelText(/Include zero stock/i));
    await waitFor(() => {
      expect(reportsAPI.stockValuation).toHaveBeenCalledWith({ include_zero: '1' });
    });
  });

  it('downloads a branded PDF', async () => {
    render(<StockValuationReportView />);
    await screen.findByText('Coffee table');
    fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }));
    await waitFor(() => {
      expect(reportsAPI.exportFile).toHaveBeenCalledWith('stock-valuation', {}, 'pdf');
    });
  });

  it('shows an empty state when load fails', async () => {
    reportsAPI.stockValuation.mockRejectedValue(new Error('down'));
    render(<StockValuationReportView />);
    expect(await screen.findByText('Could not load stock')).toBeInTheDocument();
  });

  it('shows an empty stock message when there are no lines', async () => {
    reportsAPI.stockValuation.mockResolvedValue({
      data: {
        ...payload,
        contact: '',
        note: '',
        summary: { ...payload.summary, line_count: 0, units_on_hand: 0 },
        lines: [],
      },
    });
    render(<StockValuationReportView />);
    expect(await screen.findByText('Nothing in stock')).toBeInTheDocument();
  });
});
