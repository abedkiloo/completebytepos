import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AuditLogPage, {
  parseAuditChanges,
  summarizeAuditChanges,
} from './AuditLogPage';

jest.mock('../../services/api', () => ({
  auditLogAPI: {
    list: jest.fn(),
    get: jest.fn(),
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

const { auditLogAPI } = require('../../services/api');

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
});

describe('AuditLogPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
      expect(screen.getByText('amina')).toBeInTheDocument();
    });
    expect(screen.getByText(/Price: 800 → 850/)).toBeInTheDocument();
    expect(screen.getByText('Updated')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Open audit detail for Updated/i }));

    await waitFor(() => {
      expect(screen.getByText('Audit trail details')).toBeInTheDocument();
    });
    expect(auditLogAPI.get).toHaveBeenCalledWith(7);
    expect(screen.getByText('What they entered')).toBeInTheDocument();
    expect(screen.getByText('850')).toBeInTheDocument();
    expect(screen.getByText('CEM-50')).toBeInTheDocument();
  });
});
