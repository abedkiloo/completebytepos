/**
 * Debt Management page integration: summary cards, debtor list, history + pay actions.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

const moduleSettingsState = {
  settings: {
    show_wallet_balance: true,
    enable_wallet_payment: true,
  },
  loading: false,
};

// react-router-dom v7 named exports (MemoryRouter) are undefined under CRA Jest ESM interop.
jest.mock('react-router-dom', () => ({
  MemoryRouter: ({ children }) => <>{children}</>,
  Link: ({ to, children, ...props }) => (
    <a href={typeof to === 'string' ? to : '#'} {...props}>
      {children}
    </a>
  ),
}));

jest.mock('../../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (value) => value,
}));

jest.mock('../../services/api', () => ({
  customersAPI: {
    debtSummary: jest.fn(),
    debtors: jest.fn(),
    walletTransactions: jest.fn(),
    receiveWalletPayment: jest.fn(),
  },
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => moduleSettingsState,
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({
    permissions: [
      { module: 'customers', action: 'view', name: 'customers.view' },
      { module: 'customers', action: 'update', name: 'customers.update' },
    ],
  }),
  hasPermission: (_perms, module, action) =>
    module === 'customers' && (action === 'view' || action === 'update'),
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
    Wallet: Icon,
    Users: Icon,
    TrendingDown: Icon,
    Banknote: Icon,
    History: Icon,
    Search: Icon,
    ExternalLink: Icon,
    Inbox: Icon,
    Loader2: Icon,
  };
});

jest.mock('../ui/button', () => ({
  Button: ({ children, onClick, type = 'button', disabled }) => (
    <button type={type} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

jest.mock('../ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

jest.mock('../ui/badge', () => ({
  Badge: ({ children }) => <span>{children}</span>,
}));

jest.mock('./ReceiveWalletPaymentDialog', () => ({
  __esModule: true,
  default: ({ open, customer, onSuccess }) =>
    open && customer ? (
      <div data-testid="receive-wallet-dialog">
        <span>{customer.name}</span>
        <button type="button" onClick={() => onSuccess?.({ id: customer.id, wallet_balance: '0' })}>
          Mock settle
        </button>
      </div>
    ) : null,
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

jest.mock('../ui/dialog', () => ({
  Dialog: ({ open, children }) => (open ? <div data-testid="history-dialog">{children}</div> : null),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

jest.mock('../page', () => ({
  __esModule: true,
  PageShell: ({ children }) => <div data-testid="page-shell">{children}</div>,
  PageHeader: ({ title, description }) => (
    <header>
      <h1>{title}</h1>
      {description ? <p>{description}</p> : null}
    </header>
  ),
  PageLoading: () => <div>Loading…</div>,
  EmptyState: ({ title }) => <div>{title}</div>,
  SummaryCard: ({ label, value }) => (
    <div>
      <span>{label}</span>
      <span>{value}</span>
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

import { MemoryRouter } from 'react-router-dom';
import { customersAPI } from '../../services/api';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import DebtManagementPage from './DebtManagementPage';

const SUMMARY = {
  customers_with_debt: 1,
  total_debt: '250.00',
  average_debt: '250.00',
  collected_today: '40.00',
  aging: {
    '0_7': { count: 0, amount: '0.00' },
    '8_30': { count: 1, amount: '250.00' },
    '31_60': { count: 0, amount: '0.00' },
    '60_plus': { count: 0, amount: '0.00' },
  },
};

const DEBTOR = {
  id: 9,
  name: 'Alice Debtor',
  phone: '0700111222',
  customer_code: 'C-9',
  wallet_balance: '-250.00',
  debt_amount: '250.00',
  debt_age_days: 12,
  aging_bucket: '8_30',
  last_sale_at: null,
  last_payment_at: null,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <DebtManagementPage />
    </MemoryRouter>
  );
}

describe('DebtManagementPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    moduleSettingsState.settings = {
      show_wallet_balance: true,
      enable_wallet_payment: true,
    };
    moduleSettingsState.loading = false;
    customersAPI.debtSummary.mockResolvedValue({ data: SUMMARY });
    customersAPI.debtors.mockResolvedValue({
      data: { count: 1, results: [DEBTOR] },
    });
    customersAPI.walletTransactions.mockResolvedValue({
      data: [
        {
          id: 1,
          source_type: 'debt',
          transaction_type: 'debit',
          amount: '250.00',
          created_at: '2026-09-01T10:00:00Z',
          sale_number: 'SALE-1',
          notes: 'Pay later',
        },
      ],
    });
  });

  it('renders dashboard summary and debtor row', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: /Debt Management/i })).toBeInTheDocument();
    expect(screen.getByText(/Customers with debt/i)).toBeInTheDocument();
    expect(screen.getByText(/Total debt outstanding/i)).toBeInTheDocument();
    expect(screen.getByText(/Collected today/i)).toBeInTheDocument();
    expect(screen.getAllByText(/8–30 days/i).length).toBeGreaterThanOrEqual(1);

    await waitFor(() => {
      expect(screen.getByText('Alice Debtor')).toBeInTheDocument();
    });
    expect(screen.getByText(/0700111222/)).toBeInTheDocument();
    expect(customersAPI.debtSummary).toHaveBeenCalled();
    expect(customersAPI.debtors).toHaveBeenCalled();
  });

  it('opens receive payment dialog from row action', async () => {
    renderPage();
    await screen.findByText('Alice Debtor');

    fireEvent.click(screen.getByRole('button', { name: /Receive payment/i }));
    expect(screen.getByTestId('receive-wallet-dialog')).toHaveTextContent('Alice Debtor');
  });

  it('refreshes summary, debtors, and nav badge after settle', async () => {
    renderPage();
    await screen.findByText('Alice Debtor');

    fireEvent.click(screen.getByRole('button', { name: /Receive payment/i }));
    fireEvent.click(screen.getByRole('button', { name: /Mock settle/i }));

    await waitFor(() => {
      expect(customersAPI.debtSummary.mock.calls.length).toBeGreaterThanOrEqual(2);
      expect(customersAPI.debtors.mock.calls.length).toBeGreaterThanOrEqual(2);
      expect(dispatchNavBadgesRefresh).toHaveBeenCalled();
    });
  });

  it('loads wallet history when History is clicked', async () => {
    renderPage();
    await screen.findByText('Alice Debtor');

    fireEvent.click(screen.getByRole('button', { name: /History/i }));

    expect(await screen.findByTestId('history-dialog')).toBeInTheDocument();
    await waitFor(() => {
      expect(customersAPI.walletTransactions).toHaveBeenCalledWith(9, { limit: 40 });
    });
    expect(screen.getByText(/Debt added/i)).toBeInTheDocument();
    expect(screen.getByText(/SALE-1/)).toBeInTheDocument();
  });

  it('shows empty state when wallet balance feature is off', () => {
    moduleSettingsState.settings = {
      show_wallet_balance: false,
      enable_wallet_payment: true,
    };
    renderPage();
    expect(screen.getByText(/Wallet debt is hidden/i)).toBeInTheDocument();
    expect(customersAPI.debtors).not.toHaveBeenCalled();
  });

  it('shows no-debtors empty state when list is empty', async () => {
    customersAPI.debtors.mockResolvedValue({ data: { count: 0, results: [] } });
    renderPage();
    expect(await screen.findByText(/No customers with debt/i)).toBeInTheDocument();
  });
});

describe('DebtManagementPage helpers', () => {
  const {
    emptyDebtSummary,
    walletTxnLabel,
    AGING_BUCKET_LABELS,
  } = require('../../utils/debtManagement');

  it('has aging labels used by the dashboard', () => {
    expect(Object.keys(AGING_BUCKET_LABELS)).toEqual(['0_7', '8_30', '31_60', '60_plus']);
  });

  it('starts from an empty summary shape', () => {
    expect(emptyDebtSummary().customers_with_debt).toBe(0);
  });

  it('labels settlement transactions', () => {
    expect(walletTxnLabel('debt_settlement')).toContain('Payment');
  });
});
