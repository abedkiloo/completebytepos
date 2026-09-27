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
  generated_at: '2026-09-27T10:00:00Z',
  as_of: '2026-09-27T10:00:00Z',
  summary: {
    item_count: 1,
    units_on_hand: 3,
    inventory_value: 12000,
    selling_value: 24000,
    zero_stock_skus: 0,
  },
  items: [
    {
      sku: 'TBL-1',
      item: 'Coffee table',
      category: 'Sofas',
      variant: '',
      quantity: 3,
      unit_cost: 4000,
      inventory_value: 12000,
      selling_price: 8000,
      selling_value: 24000,
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
    expect(screen.getByText('SKUs in stock')).toBeInTheDocument();
    expect(screen.getAllByText(/Inventory value/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Lines on hand/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/quantity ×/i)).not.toBeInTheDocument();
    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(reportsAPI.stockValuation).toHaveBeenCalledWith({ include_zero: undefined });
  });

  it('hides cost columns when the store toggle is off', async () => {
    useModuleSettings.mockReturnValue({ settings: { show_cost_and_profit: false } });
    render(<StockValuationReportView />);
    expect(await screen.findByText('Coffee table')).toBeInTheDocument();
    expect(screen.queryAllByText(/Inventory value/i).length).toBe(0);
    expect(screen.getAllByText(/Selling value/i).length).toBeGreaterThan(0);
  });

  it('reloads with zero-stock SKUs when the checkbox is on', async () => {
    render(<StockValuationReportView />);
    await screen.findByText('Coffee table');
    fireEvent.click(screen.getByLabelText(/Show zero quantity/i));
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

  it('shows an empty stock message when there are no items', async () => {
    reportsAPI.stockValuation.mockResolvedValue({
      data: {
        ...payload,
        contact: '',
        summary: { ...payload.summary, item_count: 0, units_on_hand: 0 },
        items: [],
      },
    });
    render(<StockValuationReportView />);
    expect(await screen.findByText('Nothing in stock')).toBeInTheDocument();
  });

  it('still renders a legacy lines payload', async () => {
    reportsAPI.stockValuation.mockResolvedValue({
      data: {
        owner: 'Omuwenga Suppliers',
        generated_at: '2026-09-27T10:00:00Z',
        summary: {
          line_count: 1,
          units_on_hand: 2,
          cost_value: 10,
          retail_value: 20,
        },
        lines: [
          {
            sku: 'OLD-1',
            product: 'Old chair',
            quantity: 2,
            unit_cost: 5,
            cost_value: 10,
            unit_price: 10,
            retail_value: 20,
          },
        ],
      },
    });
    render(<StockValuationReportView />);
    expect(await screen.findByText('Old chair')).toBeInTheDocument();
    expect(screen.getByText('OLD-1')).toBeInTheDocument();
    expect(screen.getByText('Total')).toBeInTheDocument();
  });
});
