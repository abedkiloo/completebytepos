import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { installLocalStorageMock } from '../../test-utils';

const mockNavigate = jest.fn();
const mockSearchParams = { current: new URLSearchParams() };
const mockMakerCheckerReasonCopy = jest.fn(() => ({
  label: 'Why now?',
  placeholder: 'Explain',
  summary: 'May require approval',
}));
const mockIsMakerCheckerEnabled = jest.fn(() => true);
const mockGetCurrentUserId = jest.fn(() => 5);
const mockIsManagerOrAdmin = jest.fn(() => false);

jest.mock('react-router-dom', () => ({
  MemoryRouter: ({ children }) => <>{children}</>,
  useNavigate: () => mockNavigate,
  useSearchParams: () => [mockSearchParams.current, jest.fn()],
  Link: ({ to, children, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: () => ({
    settings: {
      maker_checker_enabled: true,
      backfill_maker_checker_enabled: true,
      backfill_max_days: 30,
    },
  }),
}));

jest.mock('../../utils/roleAccess', () => ({
  isManagerOrAdminFromStorage: () => mockIsManagerOrAdmin(),
}));

jest.mock('../../utils/makerChecker', () => ({
  isMakerCheckerEnabled: () => mockIsMakerCheckerEnabled(),
  getCurrentUserId: () => mockGetCurrentUserId(),
  pendingApprovalToastMessage: jest.fn(() => 'Queued for approval'),
  makerCheckerReasonCopy: (...args) => mockMakerCheckerReasonCopy(...args),
}));

jest.mock('../../services/api', () => ({
  customersAPI: {
    list: jest.fn(() => Promise.resolve({ data: { results: [] } })),
  },
  usersAPI: {
    list: jest.fn(() =>
      Promise.resolve({
        data: {
          results: [{ id: 8, first_name: 'Alex', last_name: 'Staff', username: 'alex' }],
        },
      })
    ),
  },
  productsAPI: {
    list: jest.fn(() => Promise.resolve({ data: { results: [] } })),
    get: jest.fn(() => Promise.resolve({ data: { id: 1, name: 'Pen', sku: 'PEN-1' } })),
  },
  variantsAPI: {
    getByProduct: jest.fn(() => Promise.resolve({ data: [] })),
  },
  salesAPI: {
    backfill: jest.fn(),
    backfillPreflight: jest.fn(() => Promise.resolve({ data: { warnings: [] } })),
    backfillImportTemplate: jest.fn(),
    backfillImportCsv: jest.fn(),
  },
  pendingChangesAPI: {
    mySubmissions: jest.fn(() => Promise.resolve({ data: [] })),
    get: jest.fn(),
  },
}));

jest.mock('../page', () => ({
  PageShell: ({ children }) => <div>{children}</div>,
  PageHeader: ({ title }) => <h1>{title}</h1>,
}));
jest.mock('../ui/tabs', () => ({
  Tabs: ({ children }) => <div>{children}</div>,
  TabsList: ({ children }) => <div>{children}</div>,
  TabsTrigger: ({ children }) => <button type="button">{children}</button>,
  TabsContent: ({ children }) => <div>{children}</div>,
}));
jest.mock('../POS/VariantSelector', () => () => null);
jest.mock('../Approvals/ChangeReasonField', () => ({ label, value, onChange }) => (
  <label>
    {label}
    <input aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} />
  </label>
));
jest.mock('../Shared/SearchableSelect', () => ({ value, onChange, placeholder, options = [] }) => (
  <select
    aria-label={placeholder || 'select'}
    value={value}
    onChange={(e) => onChange({ target: { value: e.target.value } })}
  >
    {options.map((opt) => (
      <option key={opt.value} value={opt.value}>
        {opt.label}
      </option>
    ))}
  </select>
));

const RecordPastSale = require('./RecordPastSale').default;
const {
  pendingChangesAPI,
  salesAPI,
  productsAPI,
  customersAPI,
  usersAPI,
} = require('../../services/api');

function renderPage(route = '/sales/record-past') {
  const query = route.includes('?') ? route.split('?')[1] : '';
  mockSearchParams.current = new URLSearchParams(query);
  return render(<RecordPastSale />);
}

describe('RecordPastSale resubmit and served-by', () => {
  beforeEach(() => {
    installLocalStorageMock();
    jest.clearAllMocks();
    mockIsManagerOrAdmin.mockReturnValue(false);
    mockGetCurrentUserId.mockReturnValue(5);
    mockIsMakerCheckerEnabled.mockReturnValue(true);
    mockMakerCheckerReasonCopy.mockReturnValue({
      label: 'Why now?',
      placeholder: 'Explain',
      summary: 'May require approval',
    });
    customersAPI.list.mockResolvedValue({ data: { results: [] } });
    usersAPI.list.mockResolvedValue({ data: { results: [] } });
    productsAPI.list.mockResolvedValue({ data: { results: [] } });
    productsAPI.get.mockResolvedValue({ data: { id: 1, name: 'Pen', sku: 'PEN-1' } });
    pendingChangesAPI.mySubmissions.mockResolvedValue({ data: [] });
  });

  it('shows read-only served-by text for sales staff', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/You — recorded as the person who made this sale/i)).toBeInTheDocument();
    });
    expect(screen.queryByLabelText(/Who made the sale/i)).not.toBeInTheDocument();
  });

  it('shows served-by dropdown for managers', async () => {
    mockIsManagerOrAdmin.mockReturnValue(true);
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/Who made the sale/i)).toBeInTheDocument();
    });
  });

  it('lists rejected submissions with fix action', async () => {
    pendingChangesAPI.mySubmissions.mockResolvedValue({
      data: [
        {
          id: 42,
          entity_repr: 'Past sale 2026-06-20',
          rejection_reason: 'Wrong date',
        },
      ],
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Past sales sent back for correction/i)).toBeInTheDocument();
      expect(screen.getByText('Wrong date')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Fix & resubmit/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/sales/record-past?resubmit=42');
  });

  it('prefills form from rejected submission and submits resubmit_of', async () => {
    pendingChangesAPI.get.mockResolvedValue({
      data: {
        id: 42,
        status: 'rejected',
        action_type: 'sale_backfill',
        rejection_reason: 'Fix payment',
        apply_payload: {
          occurred_at: '2026-06-20T10:00:00.000Z',
          backfill_reason: 'Offline sale during outage',
          sale_type: 'pos',
          payment_method: 'cash',
          amount_paid: '50',
          items: [{ product_id: 1, quantity: 1, unit_price: '50' }],
        },
      },
    });
    salesAPI.backfill.mockResolvedValue({
      status: 202,
      data: { pending_change: { id: 42 } },
    });

    renderPage('/sales/record-past?resubmit=42');

    await waitFor(() => {
      expect(screen.getByText('Fix payment')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Offline sale during outage')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Submit for approval/i }));

    await waitFor(() => {
      expect(salesAPI.backfill).toHaveBeenCalled();
    });

    const [payload] = salesAPI.backfill.mock.calls[0];
    expect(payload.resubmit_of).toBe(42);
    expect(payload.served_by_id).toBe(5);
    expect(payload.items).toEqual([
      expect.objectContaining({ product_id: 1, quantity: 1, unit_price: 50 }),
    ]);
    expect(mockNavigate).toHaveBeenCalledWith('/sales/record-past');
  });

  it('loads product line labels when resubmit payload has items', async () => {
    pendingChangesAPI.get.mockResolvedValue({
      data: {
        id: 7,
        status: 'rejected',
        action_type: 'sale_backfill',
        rejection_reason: 'Check items',
        apply_payload: {
          occurred_at: '2026-06-20T10:00:00.000Z',
          backfill_reason: 'Offline sale during outage',
          items: [{ product_id: 1, quantity: 2, unit_price: '10' }],
        },
      },
    });

    renderPage('/sales/record-past?resubmit=7');

    await waitFor(() => {
      expect(productsAPI.get).toHaveBeenCalledWith(1);
      expect(screen.getByText(/Pen \(PEN-1\)/)).toBeInTheDocument();
    });
  });
});
