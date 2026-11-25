import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ProductPerformanceReportView, {
  normalizeProductSearchResults,
  productOptionLabel,
} from './ProductPerformanceReportView';
import { productsAPI, reportsAPI } from '../../services/api';

const mockSetSearchParams = jest.fn();
let mockSearchParams = new URLSearchParams('report=product-performance');

jest.mock('react-router-dom', () => ({
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
}));

jest.mock('../../services/api', () => ({
  productsAPI: {
    list: jest.fn(),
    get: jest.fn(),
  },
  reportsAPI: {
    productTrends: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('../Products/ProductTrendsPanel', () => ({
  __esModule: true,
  default: ({ productId, compareProductIds }) => (
    <div data-testid="product-trends-panel">
      trends-for-{productId}
      <span data-testid="product-trends-compare-prop">
        {(compareProductIds || []).join(',')}
      </span>
    </div>
  ),
}));

jest.mock('../page', () => ({
  EmptyState: ({ title }) => <div>{title}</div>,
  FilterBar: ({ children }) => <div>{children}</div>,
  FilterField: ({ children, label }) => (
    <label>
      {label}
      {children}
    </label>
  ),
  PageLoading: () => <div>loading</div>,
}));

jest.mock('../ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

jest.mock('../ui/button', () => ({
  Button: ({ children, ...props }) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
}));

jest.mock('lucide-react', () => ({
  PackageSearch: () => <span>icon</span>,
  X: () => <span>x</span>,
}));

jest.mock('../ui/badge', () => ({
  Badge: ({ children, ...props }) => <span {...props}>{children}</span>,
}));

describe('ProductPerformanceReportView helpers (unit)', () => {
  it('normalizes list payloads and labels products', () => {
    expect(normalizeProductSearchResults(null)).toEqual([]);
    expect(normalizeProductSearchResults([{ id: 1 }])).toEqual([{ id: 1 }]);
    expect(normalizeProductSearchResults({ results: [{ id: 2 }] })).toEqual([{ id: 2 }]);
    expect(productOptionLabel({ name: 'Cement', sku: 'C50' })).toBe('Cement · C50');
    expect(productOptionLabel({ id: 9 })).toBe('Product #9');
  });

  it('stress: keeps only the search page size from a large payload', () => {
    const rows = Array.from({ length: 500 }, (_, i) => ({
      id: i + 1,
      name: `SKU-${i}`,
      sku: `S-${i}`,
    }));
    const normalized = normalizeProductSearchResults({ results: rows });
    expect(normalized).toHaveLength(500);
    expect(productOptionLabel(normalized[499])).toContain('SKU-499');
  });
});

describe('ProductPerformanceReportView', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockSearchParams = new URLSearchParams('report=product-performance');
    productsAPI.list.mockResolvedValue({
      data: {
        results: [
          { id: 7, name: 'Cement 50kg', sku: 'CEM-50' },
          { id: 8, name: 'Hinge', sku: 'H1' },
        ],
      },
    });
    productsAPI.get.mockResolvedValue({
      data: { id: 7, name: 'Cement 50kg', sku: 'CEM-50', variants: [] },
    });
    reportsAPI.productTrends.mockResolvedValue({ data: { periods: [] } });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('corrected: search picks a product and shows performance charts', async () => {
    render(<ProductPerformanceReportView />);
    expect(screen.getByText('Pick a product')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('product-performance-search'), {
      target: { value: 'Cement' },
    });
    await act(async () => {
      jest.advanceTimersByTime(300);
    });

    await waitFor(() => {
      expect(productsAPI.list).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'Cement', page_size: 12 })
      );
    });
    expect(screen.getByTestId('product-performance-pick-7')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('product-performance-pick-7'));

    await waitFor(() => {
      expect(screen.getByTestId('product-trends-panel')).toHaveTextContent('trends-for-7');
    });
    expect(screen.getByTestId('product-performance-selected-name')).toHaveTextContent(
      'Cement 50kg'
    );
    expect(mockSetSearchParams).toHaveBeenCalled();
    const nextParams = mockSetSearchParams.mock.calls.at(-1)[0];
    expect(nextParams.get('product_id')).toBe('7');
    expect(nextParams.get('report')).toBe('product-performance');
  });

  it('integration: loads product from URL product_id', async () => {
    mockSearchParams = new URLSearchParams(
      'report=product-performance&product_id=7'
    );
    await act(async () => {
      render(<ProductPerformanceReportView />);
    });
    await waitFor(() => {
      expect(productsAPI.get).toHaveBeenCalledWith(7);
    });
    await waitFor(() => {
      expect(screen.getByTestId('product-trends-panel')).toBeInTheDocument();
    });
    expect(screen.getByTestId('product-performance-selected-name')).toHaveTextContent(
      'Cement 50kg'
    );
  });

  it('corrected: adds a peer to compare and passes compare_ids', async () => {
    mockSearchParams = new URLSearchParams(
      'report=product-performance&product_id=7'
    );
    productsAPI.get.mockImplementation((id) => {
      if (Number(id) === 7) {
        return Promise.resolve({
          data: { id: 7, name: 'Cement 50kg', sku: 'CEM-50', variants: [] },
        });
      }
      if (Number(id) === 8) {
        return Promise.resolve({
          data: { id: 8, name: 'Hinge', sku: 'H1', variants: [] },
        });
      }
      return Promise.reject(new Error('missing'));
    });

    await act(async () => {
      render(<ProductPerformanceReportView />);
    });
    await waitFor(() => {
      expect(screen.getByTestId('product-trends-panel')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('product-performance-add-compare'));
    fireEvent.change(screen.getByTestId('product-performance-search'), {
      target: { value: 'Hinge' },
    });
    await act(async () => {
      jest.advanceTimersByTime(300);
    });
    await waitFor(() => {
      expect(screen.getByTestId('product-performance-pick-8')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('product-performance-pick-8'));

    await waitFor(() => {
      expect(screen.getByTestId('product-performance-compare-chip-8')).toBeInTheDocument();
    });
    expect(screen.getByTestId('product-trends-compare-prop')).toHaveTextContent('8');
    const nextParams = mockSetSearchParams.mock.calls.at(-1)[0];
    expect(nextParams.get('compare_ids')).toBe('8');
  });

  it('integration: hydrates compare_ids from URL', async () => {
    mockSearchParams = new URLSearchParams(
      'report=product-performance&product_id=7&compare_ids=8'
    );
    productsAPI.get.mockImplementation((id) => {
      if (Number(id) === 7) {
        return Promise.resolve({
          data: { id: 7, name: 'Cement 50kg', sku: 'CEM-50', variants: [] },
        });
      }
      return Promise.resolve({
        data: { id: 8, name: 'Hinge', sku: 'H1', variants: [] },
      });
    });
    await act(async () => {
      render(<ProductPerformanceReportView />);
    });
    await waitFor(() => {
      expect(screen.getByTestId('product-performance-compare-chip-8')).toBeInTheDocument();
    });
    expect(screen.getByTestId('product-trends-compare-prop')).toHaveTextContent('8');
  });
});


