import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ProductTrendsPanel from './ProductTrendsPanel';
import { reportsAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  reportsAPI: { productTrends: jest.fn() },
}));

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div data-testid="chart">{children}</div>,
  LineChart: ({ children }) => <div>{children}</div>,
  BarChart: ({ children }) => <div>{children}</div>,
  PieChart: ({ children }) => <div>{children}</div>,
  Pie: () => null,
  Cell: () => null,
  Line: () => null,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  CartesianGrid: () => null,
}));

const samplePayload = {
  product_id: 7,
  months_requested: 12,
  months: [
    {
      month: '2026-05',
      label: 'May 2026',
      quantity_sold: 4,
      revenue: '400.00',
      order_count: 2,
      quantity_received: 10,
    },
    {
      month: '2026-06',
      label: 'Jun 2026',
      quantity_sold: 1,
      revenue: '100.00',
      order_count: 1,
      quantity_received: 0,
    },
  ],
  channels: [{ channel: 'pos', quantity: 5 }],
  summary: {
    quantity_sold: 5,
    revenue: '500.00',
    order_count: 3,
    quantity_received: 10,
    avg_monthly_quantity: 2.5,
    best_month: '2026-05',
    best_month_label: 'May 2026',
  },
};

describe('ProductTrendsPanel', () => {
  beforeEach(() => {
    reportsAPI.productTrends.mockResolvedValue({ data: samplePayload });
  });

  it('loads trends for a product and shows summary', async () => {
    render(<ProductTrendsPanel productId={7} />);
    await waitFor(() =>
      expect(screen.getByTestId('product-trends-summary')).toBeInTheDocument()
    );
    expect(reportsAPI.productTrends).toHaveBeenCalledWith({
      product_id: 7,
      months: 12,
    });
    expect(screen.getByTestId('product-trends-sold-chart')).toBeInTheDocument();
    expect(screen.getByTestId('product-trends-sold-received-chart')).toBeInTheDocument();
    expect(screen.getByText('May 2026')).toBeInTheDocument();
  });

  it('passes variant_id when focused', async () => {
    render(<ProductTrendsPanel productId={7} variantId={99} />);
    await waitFor(() => expect(reportsAPI.productTrends).toHaveBeenCalled());
    expect(reportsAPI.productTrends).toHaveBeenCalledWith({
      product_id: 7,
      months: 12,
      variant_id: 99,
    });
  });

  it('reloads when months change', async () => {
    render(<ProductTrendsPanel productId={7} />);
    await waitFor(() => expect(reportsAPI.productTrends).toHaveBeenCalled());
    fireEvent.change(screen.getByTestId('product-trends-months'), {
      target: { value: '6' },
    });
    await waitFor(() =>
      expect(reportsAPI.productTrends).toHaveBeenLastCalledWith({
        product_id: 7,
        months: 6,
      })
    );
  });

  it('shows error when API fails', async () => {
    reportsAPI.productTrends.mockRejectedValue({
      response: { data: { error: 'Choose a product to see trends.' } },
    });
    render(<ProductTrendsPanel productId={7} />);
    await waitFor(() =>
      expect(screen.getByTestId('product-trends-error')).toHaveTextContent(
        'Choose a product to see trends.'
      )
    );
  });
});
