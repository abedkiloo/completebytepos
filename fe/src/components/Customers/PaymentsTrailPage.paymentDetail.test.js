/**
 * Integration: payments trail row click opens payment / sale detail.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, onClick, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} onClick={onClick} {...rest}>
      {children}
    </a>
  ),
}));

jest.mock('../../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (value) => value,
}));

jest.mock('../../services/api', () => ({
  customersAPI: {
    paymentsTrail: jest.fn(),
    paymentsTrailSummary: jest.fn(),
    paymentsTrailExport: jest.fn(),
    walletSettlementDetail: jest.fn(),
  },
  salesAPI: {
    get: jest.fn(),
  },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: () => ({
    permissions: [
      { module: 'debt_management', action: 'payments_trail', name: 'debt_management.payments_trail' },
    ],
  }),
  hasPermission: () => true,
}));

jest.mock('../../utils/moduleFeatures', () => ({
  isModuleFeatureEnabled: () => true,
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

jest.mock('lucide-react', () => {
  const React = require('react');
  const Icon = (props) => React.createElement('span', { 'data-testid': 'icon', ...props });
  return {
    __esModule: true,
    Banknote: Icon,
    Calculator: Icon,
    FileSpreadsheet: Icon,
    Search: Icon,
  };
});

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

jest.mock('../Shared/ReceiptImageLink', () => ({
  __esModule: true,
  default: ({ label }) => <span>{label}</span>,
}));

jest.mock('./PaymentDetailDialog', () => ({
  __esModule: true,
  default: ({ open, payment, loading }) =>
    open ? (
      <div data-testid="payment-detail-dialog">
        {loading ? 'Loading…' : null}
        {payment ? <span data-testid="opened-payment-id">{payment.id}</span> : null}
        {payment?.payer_name ? <span>{payment.payer_name}</span> : null}
      </div>
    ) : null,
}));

jest.mock('../Sales/SaleDetailDialog', () => ({
  __esModule: true,
  default: ({ open, sale }) =>
    open && sale ? (
      <div data-testid="sale-detail-dialog">Sale {sale.id}</div>
    ) : null,
}));

jest.mock('../ui/button', () => ({
  Button: ({ children, onClick, disabled }) => (
    <button type="button" onClick={onClick} disabled={disabled}>
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

jest.mock('../page', () => ({
  __esModule: true,
  PageShell: ({ children }) => <div>{children}</div>,
  PageHeader: ({ title, children }) => (
    <header>
      <h1>{title}</h1>
      {children}
    </header>
  ),
  PageLoading: () => <div>Loading…</div>,
  EmptyState: ({ title }) => <div>{title}</div>,
  FilterBar: ({ children }) => <div>{children}</div>,
  FilterField: ({ label, children }) => (
    <label>
      {label}
      {children}
    </label>
  ),
  SummaryCard: ({ label, value }) => (
    <div>
      {label}:{value}
    </div>
  ),
  DataTable: ({ children }) => <table>{children}</table>,
  DataTableHeader: ({ children }) => (
    <thead>
      <tr>{children}</tr>
    </thead>
  ),
  DataTableHead: ({ children }) => <th>{children}</th>,
  DataTableBody: ({ children }) => <tbody>{children}</tbody>,
  DataTableRow: ({ children, onClick, ...rest }) => (
    <tr onClick={onClick} {...rest}>
      {children}
    </tr>
  ),
  DataTableCell: ({ children, onClick }) => <td onClick={onClick}>{children}</td>,
  ListPaginationRail: ({ children }) => <div>{children}</div>,
}));

import { customersAPI, salesAPI } from '../../services/api';
import PaymentsTrailPage from './PaymentsTrailPage';

describe('PaymentsTrailPage payment detail integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    customersAPI.paymentsTrail.mockResolvedValue({
      data: {
        count: 2,
        results: [
          {
            kind: 'debt_settlement',
            id: 11,
            amount: '80.00',
            occurred_at: '2026-11-12T08:00:00Z',
            customer_id: 3,
            customer_name: 'Ada',
            payment_method: 'mpesa',
            payment_method_label: 'M-PESA',
            mpesa_destination: 'till',
            payer_name: 'Mary',
            reference: 'QHX1111111',
            receipt_image_url: '/media/a.jpg',
            paid_towards_label: 'Customer debt',
            paid_towards: [],
            received_by: 'Cashier',
          },
          {
            kind: 'sale_payment',
            id: 99,
            amount: '200.00',
            occurred_at: '2026-11-12T09:00:00Z',
            customer_name: 'Walk-in',
            payment_method: 'cash',
            paid_towards_label: 'Sale S-99',
            paid_towards: [],
          },
        ],
      },
    });
    customersAPI.walletSettlementDetail.mockResolvedValue({
      data: {
        kind: 'debt_settlement',
        id: 11,
        amount: '80.00',
        payer_name: 'Mary Refreshed',
        mpesa_destination: 'till',
      },
    });
    salesAPI.get.mockResolvedValue({
      data: { id: 99, sale_number: 'S-99', total: '200.00', amount_paid: '200.00' },
    });
  });

  it('opens payment detail for debt settlement rows and refreshes from API', async () => {
    render(<PaymentsTrailPage />);
    await waitFor(() =>
      expect(screen.getByTestId('payment-trail-row-debt_settlement-11')).toBeInTheDocument()
    );

    fireEvent.click(screen.getByTestId('payment-trail-row-debt_settlement-11'));
    await waitFor(() =>
      expect(customersAPI.walletSettlementDetail).toHaveBeenCalledWith(11)
    );
    await waitFor(() => {
      expect(screen.getByTestId('payment-detail-dialog')).toBeInTheDocument();
      expect(screen.getByTestId('opened-payment-id')).toHaveTextContent('11');
      expect(screen.getByText('Mary Refreshed')).toBeInTheDocument();
    });
  });

  it('opens sale detail for sale tender rows', async () => {
    render(<PaymentsTrailPage />);
    await waitFor(() =>
      expect(screen.getByTestId('payment-trail-row-sale_payment-99')).toBeInTheDocument()
    );

    fireEvent.click(screen.getByTestId('payment-trail-row-sale_payment-99'));
    await waitFor(() => expect(salesAPI.get).toHaveBeenCalledWith(99));
    await waitFor(() =>
      expect(screen.getByTestId('sale-detail-dialog')).toHaveTextContent('Sale 99')
    );
  });
});
