import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AuditLogPage, {
  extractFinanceFields,
  parseAuditChanges,
  summarizeAuditChanges,
} from './AuditLogPage';

jest.mock('../../services/api', () => ({
  auditLogAPI: {
    list: jest.fn(),
    get: jest.fn(),
    facets: jest.fn(),
  },
  usersAPI: {
    list: jest.fn(),
  },
}));

jest.mock('../../utils/roleAccess', () => ({
  userMayEditFinancialFieldsFromStorage: () => true,
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('react-router-dom', () => ({
  Navigate: () => <div>redirect</div>,
}));

jest.mock('lucide-react', () => ({
  ScrollText: () => <span>scroll</span>,
  Search: () => <span>search</span>,
  Loader2: () => <span>loading</span>,
}));

jest.mock('../page', () => ({
  PageShell: ({ children }) => <div data-testid="shell">{children}</div>,
  PageHeader: ({ title, description }) => (
    <div>
      <h1>{title}</h1>
      <p>{description}</p>
    </div>
  ),
  PageLoading: ({ label }) => <div>{label}</div>,
}));

jest.mock('../page/ListSortBar', () => ({
  ListSortBar: () => <div data-testid="sort-bar" />,
}));

jest.mock('../ui/card', () => ({
  Card: ({ children }) => <div data-testid="card">{children}</div>,
  CardContent: ({ children }) => <div>{children}</div>,
}));

jest.mock('../ui/input', () => ({
  Input: (props) => <input aria-label={props.placeholder || 'input'} {...props} />,
}));

jest.mock('../ui/button', () => ({
  Button: ({ children, ...props }) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
}));

jest.mock('../ui/badge', () => ({
  Badge: ({ children }) => <span data-testid="badge">{children}</span>,
}));

jest.mock('../ui/dialog', () => {
  const React = require('react');
  return {
    Dialog: ({ open, children }) =>
      open ? React.createElement('div', { 'data-testid': 'audit-dialog' }, children) : null,
    DialogContent: ({ children }) => React.createElement('div', null, children),
    DialogHeader: ({ children }) => React.createElement('div', null, children),
    DialogTitle: ({ children }) => React.createElement('h2', null, children),
    DialogDescription: ({ children }) => React.createElement('p', null, children),
  };
});

jest.mock('../../hooks/useListOrdering', () => ({
  useListOrdering: () => ({ ordering: '-created_at', setOrdering: jest.fn() }),
}));

jest.mock('../../utils/listOrdering', () => ({
  withListOrdering: (params) => params,
}));

jest.mock('../../utils/formatters', () => ({
  formatDateTime: (v) => `dt:${v}`,
}));

jest.mock('../../lib/cn', () => ({
  cn: (...args) => args.filter(Boolean).join(' '),
}));

const { auditLogAPI, usersAPI } = require('../../services/api');

describe('audit change helpers', () => {
  it('summarizes field diffs and created payloads', () => {
    expect(
      summarizeAuditChanges({
        price: { from: '10', to: '20' },
        name: { from: 'A', to: 'B' },
      })
    ).toContain('Price: 10 → 20');

    expect(
      summarizeAuditChanges({
        __created__: { total: '100.00', payment_method: 'cash' },
      })
    ).toContain('Total: 100.00');

    expect(parseAuditChanges(null).rows).toEqual([]);
  });

  it('summarizes debt/sale money events with amount method and stage', () => {
    expect(
      summarizeAuditChanges({
        lifecycle: 'money_posted',
        amount: '460.00',
        payment_method: 'mpesa',
        reference: 'QHX',
        customer_name: 'Kogi',
        via: 'approval',
        proposed_values: { amount: '460.00' },
        reason: 'Debt collection of 460.00 via M-PESA',
      })
    ).toMatch(/Money posted.*460.*MPESA.*QHX.*Kogi/i);

    expect(
      summarizeAuditChanges({
        lifecycle: 'submitted',
        amount: '460.00',
        payment_method: 'mpesa',
        reason: 'Debt collection of 460.00 via M-PESA',
        original_values: {},
        proposed_values: { amount: '460' },
      })
    ).toMatch(/Submitted.*460.*MPESA/i);

    expect(
      extractFinanceFields({
        amount: '100',
        payment_method: 'cash',
        lifecycle: 'money_posted',
      })
    ).toEqual(
      expect.objectContaining({
        amount: '100',
        method: 'cash',
        lifecycle: 'money_posted',
      })
    );
  });
});

describe('AuditLogPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    usersAPI.list.mockResolvedValue({
      data: { results: [{ id: 4, username: 'amina' }, { id: 9, username: 'john' }] },
    });
    auditLogAPI.facets.mockResolvedValue({
      data: { modules: ['products', 'inventory', 'payroll'], actions: ['create', 'stock_adjust'] },
    });
    auditLogAPI.list.mockResolvedValue({
      data: {
        results: [
          {
            id: 7,
            created_at: '2026-10-05T10:00:00Z',
            username_snapshot: 'amina',
            action: 'update',
            module: 'products',
            object_repr: 'Cement 50kg',
            object_type: 'products.Product',
            object_id: '3',
            changes: { price: { from: '800', to: '850' }, cost: { from: '600', to: '610' } },
            path: '/api/products/3/',
            method: 'PATCH',
            ip_address: '127.0.0.1',
          },
        ],
      },
    });
    auditLogAPI.get.mockResolvedValue({
      data: {
        id: 7,
        created_at: '2026-10-05T10:00:00Z',
        username_snapshot: 'amina',
        action: 'update',
        module: 'products',
        object_repr: 'Cement 50kg',
        object_type: 'products.Product',
        object_id: '3',
        changes: {
          price: { from: '800', to: '850' },
          cost: { from: '600', to: '610' },
          sku: { from: 'CEM', to: 'CEM-50' },
        },
        path: '/api/products/3/',
        method: 'PATCH',
        ip_address: '127.0.0.1',
      },
    });
  });

  it('lists values and opens a detail dialog for a row', async () => {
    render(<AuditLogPage />);

    await waitFor(() => {
      expect(screen.getByText(/Price: 800 → 850/)).toBeInTheDocument();
    });
    expect(screen.getAllByText('amina').length).toBeGreaterThan(0);
    expect(screen.getByText('Updated')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Open audit detail for Updated/i }));

    await waitFor(() => {
      expect(screen.getByText('Audit trail details')).toBeInTheDocument();
    });
    expect(auditLogAPI.get).toHaveBeenCalledWith(7);
    expect(screen.getByText('All recorded values')).toBeInTheDocument();
    expect(screen.getByText('850')).toBeInTheDocument();
    expect(screen.getByText('CEM-50')).toBeInTheDocument();
  });

  it('sends day, time, and user filters to the audit API', async () => {
    render(<AuditLogPage />);

    await waitFor(() => {
      expect(auditLogAPI.list).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByLabelText('From date'), {
      target: { value: '2026-10-01' },
    });
    fireEvent.change(screen.getByLabelText('From time'), {
      target: { value: '08:00' },
    });
    fireEvent.change(screen.getByLabelText('To date'), {
      target: { value: '2026-10-05' },
    });
    fireEvent.change(screen.getByLabelText('To time'), {
      target: { value: '18:30' },
    });
    await waitFor(() => {
      expect(usersAPI.list).toHaveBeenCalled();
    });
    fireEvent.change(screen.getByLabelText('Filter by user'), {
      target: { value: '4' },
    });
    fireEvent.change(screen.getByLabelText('Filter by module'), {
      target: { value: 'inventory' },
    });

    await waitFor(() => {
      const calls = auditLogAPI.list.mock.calls.map((c) => c[0] || {});
      const matched = calls.find(
        (p) =>
          p.date_from === '2026-10-01' &&
          p.date_to === '2026-10-05' &&
          p.time_from === '08:00' &&
          p.time_to === '18:30' &&
          String(p.user) === '4' &&
          p.module === 'inventory'
      );
      expect(matched).toBeTruthy();
    });
  });
});
