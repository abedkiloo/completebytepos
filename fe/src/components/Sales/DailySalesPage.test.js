/**
 * Daily Sales Tracker page integration tests:
 * date navigation, summary cards, order classification (paid vs debt), receipt and settlement modals.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

import {
  shiftDate,
  formatDateLabel,
  getTodayDateString,
} from './DailySalesPage';

let mockSearchParams = new URLSearchParams();
const mockSetSearchParams = jest.fn((updater) => {
  if (typeof updater === 'function') {
    mockSearchParams = updater(mockSearchParams);
  } else {
    mockSearchParams = new URLSearchParams(updater);
  }
});

jest.mock('react-router-dom', () => ({
  MemoryRouter: ({ children }) => <>{children}</>,
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  Link: ({ to, children, ...props }) => (
    <a href={typeof to === 'string' ? to : '#'} {...props}>
      {children}
    </a>
  ),
}));

jest.mock('../../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (val) => val,
}));

jest.mock('../../services/api', () => ({
  salesAPI: {
    daily: jest.fn(),
    get: jest.fn(),
    refund: jest.fn(),
  },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({
    permissions: [
      { module: 'sales', action: 'view' },
      { module: 'sales', action: 'daily_sales' },
      { module: 'customers', action: 'update' },
    ],
  }),
  hasPermission: (_perms, mod, act) => {
    if (mod === 'sales' && (act === 'view' || act === 'daily_sales')) return true;
    if (mod === 'customers' && act === 'update') return true;
    return false;
  },
  isManagerOrAdminFromStorage: () => true,
}));

jest.mock('../../utils/dailySalesAccess', () => ({
  canViewDailySalesFromStorage: jest.fn(() => true),
  dailySalesCustomerPath: (id, date) => `/sales/daily/customers/${id}?date=${date}`,
}));

jest.mock('../../utils/saleRefund', () => ({
  userCanRefundSales: () => true,
  saleIsRefundable: () => true,
  handleSaleRefundResponse: () => ({ handled: true }),
}));

jest.mock('../../utils/navBadges', () => ({
  dispatchNavBadgesRefresh: jest.fn(),
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

jest.mock('lucide-react', () => {
  const React = require('react');
  const Icon = (props) => React.createElement('span', { 'data-testid': 'icon', ...props });
  return {
    __esModule: true,
    Calendar: Icon,
    ChevronLeft: Icon,
    ChevronRight: Icon,
    DollarSign: Icon,
    Receipt: Icon,
    RotateCcw: Icon,
    Search: Icon,
    ShoppingCart: Icon,
    TrendingDown: Icon,
    Users: Icon,
    Wallet: Icon,
    CheckCircle2: Icon,
    AlertCircle: Icon,
    ExternalLink: Icon,
    Clock: Icon,
    ArrowLeft: Icon,
  };
});

jest.mock('../ui/button', () => ({
  Button: ({ children, onClick, type = 'button', disabled, title }) => (
    <button type={type} onClick={onClick} disabled={disabled} title={title}>
      {children}
    </button>
  ),
}));

jest.mock('../ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

jest.mock('../ui/badge', () => ({
  Badge: ({ children, className }) => <span className={className}>{children}</span>,
}));

jest.mock('../Shared/SearchableSelect', () => ({
  __esModule: true,
  default: ({ value, onChange, options = [], placeholder }) => (
    <select
      aria-label={placeholder || 'select'}
      value={value ?? ''}
      onChange={(e) => onChange({ target: { value: e.target.value } })}
    >
      {options.map((o) => (
        <option key={String(o.id)} value={o.id}>
          {o.name}
        </option>
      ))}
    </select>
  ),
}));

jest.mock('./SaleDetailDialog', () => ({
  __esModule: true,
  default: ({ open, sale, onOpenChange }) =>
    open && sale ? (
      <div data-testid="sale-detail-dialog">
        <span>Receipt: {sale.sale_number}</span>
        <button type="button" onClick={() => onOpenChange(false)}>
          Close
        </button>
      </div>
    ) : null,
}));

jest.mock('./RefundSaleDialog', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('../Customers/ReceiveWalletPaymentDialog', () => ({
  __esModule: true,
  default: ({ open, customer, onSuccess }) =>
    open && customer ? (
      <div data-testid="receive-wallet-dialog">
        <span>Settle for: {customer.name}</span>
        <button type="button" onClick={() => onSuccess?.()}>
          Mock Confirm Settle
        </button>
      </div>
    ) : null,
}));

jest.mock('../page', () => ({
  __esModule: true,
  PageShell: ({ children }) => <div data-testid="page-shell">{children}</div>,
  PageHeader: ({ title, description, children }) => (
    <header>
      <h1>{title}</h1>
      {description && <p>{description}</p>}
      {children}
    </header>
  ),
  PageLoading: () => <div>Loading…</div>,
  EmptyState: ({ title, description }) => (
    <div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  ),
  SummaryCard: ({ label, value, subtext }) => (
    <div>
      <span>{label}</span>
      <span>{value}</span>
      {subtext && <span>{subtext}</span>}
    </div>
  ),
  FilterBar: ({ children }) => <div>{children}</div>,
  FilterField: ({ label, children }) => (
    <label>
      {label}
      {children}
    </label>
  ),
  DataTable: ({ children }) => <table>{children}</table>,
  DataTableHeader: ({ children }) => (
    <thead>
      <tr>{children}</tr>
    </thead>
  ),
  DataTableHead: ({ children }) => <th>{children}</th>,
  DataTableBody: ({ children }) => <tbody>{children}</tbody>,
  DataTableRow: ({ children }) => <tr>{children}</tr>,
  DataTableCell: ({ children }) => <td>{children}</td>,
  ListPaginationRail: ({ children }) => <div>{children}</div>,
}));

import { salesAPI } from '../../services/api';
import { canViewDailySalesFromStorage } from '../../utils/dailySalesAccess';
import DailySalesPage from './DailySalesPage';

const MOCK_SUMMARY = {
  total_sales: '5000.00',
  orders_count: 3,
  total_paid: '1500.00',
  paid_orders_count: 1,
  total_debt_incurred: '3500.00',
  debt_orders_count: 2,
  partial_orders_count: 1,
  total_debt_collected: '400.00',
  debt_settlement_count: 1,
  total_collected: '1900.00',
  payment_methods: {
    cash: { count: 1, total: '1000.00' },
    mpesa: { count: 1, total: '500.00' },
  },
};

const MOCK_ORDERS = [
  {
    id: 101,
    sale_number: 'SALE-PAID-01',
    occurred_at: '2026-09-12T10:00:00Z',
    customer: null,
    cashier_name: 'alice',
    total: '1000.00',
    amount_paid: '1000.00',
    paid_amount: '1000.00',
    debt_amount: '0.00',
    payment_status: 'paid',
    payment_method: 'cash',
    item_count: 2,
  },
  {
    id: 102,
    sale_number: 'SALE-PARTIAL-02',
    occurred_at: '2026-09-12T10:15:00Z',
    customer: {
      id: 5,
      name: 'Bob Debtor',
      phone: '0711223344',
      customer_code: 'CUST-005',
      wallet_balance: '-2000.00',
    },
    cashier_name: 'alice',
    total: '2500.00',
    amount_paid: '500.00',
    paid_amount: '500.00',
    debt_amount: '2000.00',
    payment_status: 'partial',
    payment_method: 'mpesa',
    item_count: 4,
  },
  {
    id: 103,
    sale_number: 'SALE-DEBT-03',
    occurred_at: '2026-09-12T10:45:00Z',
    customer: {
      id: 6,
      name: 'Charlie Credit',
      phone: '0722334455',
      customer_code: 'CUST-006',
      wallet_balance: '-1500.00',
    },
    cashier_name: 'alice',
    total: '1500.00',
    amount_paid: '0.00',
    paid_amount: '0.00',
    debt_amount: '1500.00',
    payment_status: 'debt',
    payment_method: 'other',
    item_count: 1,
  },
];

describe('DailySales helpers', () => {
  it('shifts date correctly forward and backward', () => {
    expect(shiftDate('2026-09-12', 1)).toBe('2026-09-13');
    expect(shiftDate('2026-09-12', -1)).toBe('2026-09-11');
    expect(shiftDate('2026-03-01', -1)).toBe('2026-02-28');
  });

  it('formats human readable date label', () => {
    const today = getTodayDateString();
    expect(formatDateLabel(today)).toContain('Today');
    const yesterday = shiftDate(today, -1);
    expect(formatDateLabel(yesterday)).toContain('Yesterday');
  });
});

describe('DailySalesPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearchParams = new URLSearchParams('date=2026-09-12');
    canViewDailySalesFromStorage.mockReturnValue(true);
    salesAPI.daily.mockResolvedValue({
      data: {
        date: '2026-09-12',
        summary: MOCK_SUMMARY,
        orders: MOCK_ORDERS,
        pagination: {
          count: 3,
          page: 1,
          page_size: 25,
          total_pages: 1,
        },
      },
    });
    salesAPI.get.mockImplementation((id) =>
      Promise.resolve({
        data: MOCK_ORDERS.find((o) => o.id === id) || { id, sale_number: `SALE-${id}` },
      })
    );
  });

  it('renders daily sales tracker, summary cards, and orders list', async () => {
    render(<DailySalesPage />);

    expect(await screen.findByRole('heading', { name: /Daily Sales Tracker/i })).toBeInTheDocument();
    expect(screen.getByText('Total Sales')).toBeInTheDocument();
    expect(screen.getByText('Paid at Checkout')).toBeInTheDocument();
    expect(screen.getByText('Taken as Debt')).toBeInTheDocument();
    expect(screen.getByText('Prior Debt Collected')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('SALE-PAID-01')).toBeInTheDocument();
      expect(screen.getByText('Bob Debtor')).toBeInTheDocument();
      expect(screen.getByText('Charlie Credit')).toBeInTheDocument();
    });

    expect(screen.getByText('Paid')).toBeInTheDocument();
    expect(screen.getByText('Partial Debt')).toBeInTheDocument();
    expect(screen.getByText('Debt (Unpaid)')).toBeInTheDocument();
  });

  it('navigates to previous day when Previous Day is clicked', async () => {
    render(<DailySalesPage />);
    await screen.findByText('SALE-PAID-01');

    const prevButton = screen.getByTitle('Previous Day');
    fireEvent.click(prevButton);

    await waitFor(() => {
      expect(salesAPI.daily).toHaveBeenCalledWith(
        expect.objectContaining({ date: '2026-09-11' })
      );
    });
  });

  it('filters orders by payment status tab', async () => {
    render(<DailySalesPage />);
    await screen.findByText('SALE-PAID-01');

    fireEvent.click(screen.getByRole('button', { name: /Taken as Debt/i }));

    await waitFor(() => {
      expect(salesAPI.daily).toHaveBeenCalledWith(
        expect.objectContaining({ payment_status: 'debt' })
      );
    });
  });

  it('opens receipt dialog when clicking Receipt button', async () => {
    render(<DailySalesPage />);
    await screen.findByText('SALE-PAID-01');

    const receiptButtons = screen.getAllByRole('button', { name: /Receipt/i });
    fireEvent.click(receiptButtons[0]);

    expect(await screen.findByTestId('sale-detail-dialog')).toHaveTextContent('SALE-PAID-01');
  });

  it('opens settle dialog when clicking Settle on a debtor order', async () => {
    render(<DailySalesPage />);
    await screen.findByText('Bob Debtor');

    const settleButtons = screen.getAllByRole('button', { name: /Settle/i });
    fireEvent.click(settleButtons[0]);

    expect(await screen.findByTestId('receive-wallet-dialog')).toHaveTextContent('Bob Debtor');
  });

  it('links customer name to customer day detail', async () => {
    render(<DailySalesPage />);
    await screen.findByText('Bob Debtor');
    const link = screen.getByRole('link', { name: 'Bob Debtor' });
    expect(link).toHaveAttribute('href', '/sales/daily/customers/5?date=2026-09-12');
    expect(screen.getAllByRole('link', { name: /View day/i }).length).toBeGreaterThan(0);
  });

  it('shows restricted empty state without permission', async () => {
    canViewDailySalesFromStorage.mockReturnValue(false);
    render(<DailySalesPage />);
    expect(await screen.findByText(/Daily Sales is restricted/i)).toBeInTheDocument();
    expect(salesAPI.daily).not.toHaveBeenCalled();
  });

  it('settles debt and refreshes daily report', async () => {
    render(<DailySalesPage />);
    await screen.findByText('Bob Debtor');
    fireEvent.click(screen.getAllByRole('button', { name: /Settle/i })[0]);
    fireEvent.click(screen.getByRole('button', { name: /Mock Confirm Settle/i }));
    await waitFor(() => {
      expect(salesAPI.daily.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('filters by Fully Paid tab', async () => {
    render(<DailySalesPage />);
    await screen.findByText('SALE-PAID-01');
    fireEvent.click(screen.getByRole('button', { name: /Fully Paid/i }));
    await waitFor(() => {
      expect(salesAPI.daily).toHaveBeenCalledWith(
        expect.objectContaining({ payment_status: 'paid' })
      );
    });
  });

  it('jumps to Today from a past date', async () => {
    render(<DailySalesPage />);
    await screen.findByText('SALE-PAID-01');
    fireEvent.click(screen.getByRole('button', { name: /^Today$/i }));
    await waitFor(() => {
      expect(salesAPI.daily).toHaveBeenCalledWith(
        expect.objectContaining({ date: expect.any(String) })
      );
    });
  });

  it('renders empty state when no orders exist on that date', async () => {
    salesAPI.daily.mockResolvedValueOnce({
      data: {
        date: '2026-09-12',
        summary: { ...MOCK_SUMMARY, orders_count: 0, total_sales: '0.00' },
        orders: [],
        pagination: { count: 0, page: 1, page_size: 25, total_pages: 1 },
      },
    });

    render(<DailySalesPage />);
    expect(await screen.findByText(/No orders found/i)).toBeInTheDocument();
  });
});
