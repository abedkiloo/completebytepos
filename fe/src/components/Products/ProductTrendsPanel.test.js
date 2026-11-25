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
  grain: 'month',
  span_requested: 12,
  months_requested: 12,
  periods: [
    {
      period: '2026-05',
      month: '2026-05',
      label: 'May 2026',
      quantity_sold: 4,
      revenue: '400.00',
      order_count: 2,
      quantity_received: 10,
    },
    {
      period: '2026-06',
      month: '2026-06',
      label: 'Jun 2026',
      quantity_sold: 1,
      revenue: '100.00',
      order_count: 1,
      quantity_received: 0,
    },
  ],
  months: [
    {
      period: '2026-05',
      month: '2026-05',
      label: 'May 2026',
      quantity_sold: 4,
      revenue: '400.00',
      order_count: 2,
      quantity_received: 10,
    },
    {
      period: '2026-06',
      month: '2026-06',
      label: 'Jun 2026',
      quantity_sold: 1,
      revenue: '100.00',
      order_count: 1,
      quantity_received: 0,
    },
  ],
  channels: [{ channel: 'pos', quantity: 5 }],
  variants: [
    {
      variant_id: 101,
      label: 'BLACK',
      sku: 'SKU-B',
      chart_key: 'v_101',
      quantity_sold: 4,
      revenue: '400.00',
      order_count: 2,
      quantity_received: 5,
    },
    {
      variant_id: 102,
      label: 'GOLD',
      sku: 'SKU-G',
      chart_key: 'v_102',
      quantity_sold: 1,
      revenue: '100.00',
      order_count: 1,
      quantity_received: 0,
    },
  ],
  variant_keys: [
    { variant_id: 101, label: 'BLACK', key: 'v_101' },
    { variant_id: 102, label: 'GOLD', key: 'v_102' },
  ],
  variant_series: [
    { period: '2026-05', label: 'May 2026', v_101: 3, v_102: 1 },
    { period: '2026-06', label: 'Jun 2026', v_101: 1, v_102: 0 },
  ],
  summary: {
    quantity_sold: 5,
    revenue: '500.00',
    order_count: 3,
    quantity_received: 10,
    avg_period_quantity: 2.5,
    avg_monthly_quantity: 2.5,
    best_period: '2026-05',
    best_period_label: 'May 2026',
    best_month: '2026-05',
    best_month_label: 'May 2026',
  },
};

describe('ProductTrendsPanel', () => {
  beforeEach(() => {
    reportsAPI.productTrends.mockResolvedValue({ data: samplePayload });
  });

  it('loads trends for any product and shows summary', async () => {
    render(<ProductTrendsPanel productId={7} />);
    await waitFor(() =>
      expect(screen.getByTestId('product-trends-summary')).toBeInTheDocument()
    );
    expect(reportsAPI.productTrends).toHaveBeenCalledWith({
      product_id: 7,
      grain: 'month',
      months: 12,
      include_variants: '1',
    });
    expect(screen.getByTestId('product-trends-sold-chart')).toBeInTheDocument();
    expect(screen.getByTestId('product-trends-sold-received-chart')).toBeInTheDocument();
    expect(screen.getByTestId('product-trends-variant-compare-chart')).toBeInTheDocument();
    expect(screen.getByText('May 2026')).toBeInTheDocument();
  });

  it('passes variant_id when focused and skips compare payload', async () => {
    render(<ProductTrendsPanel productId={7} variantId={99} />);
    await waitFor(() => expect(reportsAPI.productTrends).toHaveBeenCalled());
    expect(reportsAPI.productTrends).toHaveBeenCalledWith({
      product_id: 7,
      grain: 'month',
      months: 12,
      variant_id: 99,
      include_variants: '0',
    });
  });

  it('reloads when months span changes', async () => {
    render(<ProductTrendsPanel productId={7} />);
    await waitFor(() => expect(reportsAPI.productTrends).toHaveBeenCalled());
    fireEvent.change(screen.getByTestId('product-trends-span'), {
      target: { value: '6' },
    });
    await waitFor(() =>
      expect(reportsAPI.productTrends).toHaveBeenLastCalledWith({
        product_id: 7,
        grain: 'month',
        months: 6,
        include_variants: '1',
      })
    );
  });

  it('switches to quarter grain', async () => {
    reportsAPI.productTrends.mockResolvedValue({
      data: {
        ...samplePayload,
        grain: 'quarter',
        span_requested: 4,
        quarters_requested: 4,
        months: [],
        periods: [
          {
            period: '2026-Q2',
            label: 'Q2 2026',
            quantity_sold: 5,
            revenue: '500.00',
            order_count: 3,
            quantity_received: 10,
          },
        ],
        variants: [],
        variant_keys: [],
        variant_series: [],
        summary: {
          ...samplePayload.summary,
          best_period_label: 'Q2 2026',
        },
      },
    });
    render(<ProductTrendsPanel productId={7} />);
    await waitFor(() => expect(reportsAPI.productTrends).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId('product-trends-grain-quarter'));
    await waitFor(() =>
      expect(reportsAPI.productTrends).toHaveBeenLastCalledWith({
        product_id: 7,
        grain: 'quarter',
        quarters: 4,
        include_variants: '1',
      })
    );
  });

  it('lets staff pick a variant from the scope control', async () => {
    const onVariantChange = jest.fn();
    render(
      <ProductTrendsPanel
        productId={7}
        variants={[
          { id: 101, color_name: 'BLACK', sku: 'SKU-B' },
          { id: 102, color_name: 'GOLD', sku: 'SKU-G' },
        ]}
        onVariantChange={onVariantChange}
      />
    );
    await waitFor(() => expect(screen.getByTestId('product-trends-variant-scope')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('product-trends-variant-scope'), {
      target: { value: '102' },
    });
    expect(onVariantChange).toHaveBeenCalledWith('102');
    await waitFor(() =>
      expect(reportsAPI.productTrends).toHaveBeenLastCalledWith(
        expect.objectContaining({ variant_id: '102', include_variants: '0' })
      )
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
