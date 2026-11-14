/**
 * Unit / integration / module / stress / corrected / security:
 * Payments trail Today and Last 30 days date presets.
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

const mockGetStoredAuth = jest.fn();
const mockHasPermission = jest.fn();

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: (...args) => mockGetStoredAuth(...args),
  hasPermission: (...args) => mockHasPermission(...args),
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
  default: () => null,
}));

jest.mock('../Sales/SaleDetailDialog', () => ({
  __esModule: true,
  default: () => null,
}));

import { customersAPI } from '../../services/api';
import {
  getTodayDateString,
  paymentsTrailLast30DaysRange,
  paymentsTrailTodayRange,
} from '../../utils/debtManagement';
import PaymentsTrailPage from './PaymentsTrailPage';

function grantTrailAccess() {
  mockGetStoredAuth.mockReturnValue({
    permissions: [
      {
        module: 'debt_management',
        action: 'payments_trail',
        name: 'debt_management.payments_trail',
      },
    ],
  });
  mockHasPermission.mockReturnValue(true);
}

function denyTrailAccess() {
  mockGetStoredAuth.mockReturnValue({ permissions: [] });
  mockHasPermission.mockReturnValue(false);
}

describe('PaymentsTrailPage today filter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    grantTrailAccess();
    customersAPI.paymentsTrail.mockResolvedValue({
      data: { count: 0, results: [] },
    });
    customersAPI.paymentsTrailSummary.mockResolvedValue({
      data: { count: 0, total: '0.00' },
    });
  });

  it('unit: shows Today and Last 30 days quick filters', async () => {
    render(<PaymentsTrailPage />);
    await waitFor(() => expect(customersAPI.paymentsTrail).toHaveBeenCalled());
    expect(screen.getByTestId('payments-trail-today')).toHaveTextContent('Today');
    expect(screen.getByTestId('payments-trail-last-30')).toHaveTextContent('Last 30 days');
  });

  it('integration: Today sends date_from and date_to as today', async () => {
    render(<PaymentsTrailPage />);
    await waitFor(() => expect(customersAPI.paymentsTrail).toHaveBeenCalled());
    customersAPI.paymentsTrail.mockClear();

    fireEvent.click(screen.getByTestId('payments-trail-today'));

    const today = getTodayDateString();
    await waitFor(() => {
      expect(customersAPI.paymentsTrail).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: today,
          date_to: today,
        })
      );
    });
    expect(screen.getByTestId('payments-trail-today')).toHaveAttribute('aria-pressed', 'true');
  });

  it('module: Last 30 days restores the default window', async () => {
    render(<PaymentsTrailPage />);
    await waitFor(() => expect(customersAPI.paymentsTrail).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId('payments-trail-today'));
    await waitFor(() =>
      expect(screen.getByTestId('payments-trail-today')).toHaveAttribute('aria-pressed', 'true')
    );
    customersAPI.paymentsTrail.mockClear();

    fireEvent.click(screen.getByTestId('payments-trail-last-30'));
    const expected = paymentsTrailLast30DaysRange();
    await waitFor(() => {
      expect(customersAPI.paymentsTrail).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: expected.dateFrom,
          date_to: expected.dateTo,
        })
      );
    });
    expect(screen.getByTestId('payments-trail-today')).toHaveAttribute('aria-pressed', 'false');
  });

  it('corrected functionality: Today then summary uses the same today bounds', async () => {
    render(<PaymentsTrailPage />);
    await waitFor(() => expect(customersAPI.paymentsTrail).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId('payments-trail-today'));
    const today = paymentsTrailTodayRange();
    await waitFor(() =>
      expect(customersAPI.paymentsTrail).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: today.dateFrom,
          date_to: today.dateTo,
        })
      )
    );

    fireEvent.click(screen.getByRole('button', { name: /show total/i }));
    await waitFor(() => {
      expect(customersAPI.paymentsTrailSummary).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: today.dateFrom,
          date_to: today.dateTo,
        })
      );
    });
  });

  it('stress: rapid Today / Last 30 clicks still request valid date pairs', async () => {
    render(<PaymentsTrailPage />);
    await waitFor(() => expect(customersAPI.paymentsTrail).toHaveBeenCalled());
    customersAPI.paymentsTrail.mockClear();

    const todayBtn = screen.getByTestId('payments-trail-today');
    const last30Btn = screen.getByTestId('payments-trail-last-30');
    for (let i = 0; i < 12; i += 1) {
      fireEvent.click(i % 2 === 0 ? todayBtn : last30Btn);
    }

    await waitFor(() => expect(customersAPI.paymentsTrail.mock.calls.length).toBeGreaterThan(0));
    customersAPI.paymentsTrail.mock.calls.forEach(([params]) => {
      expect(params.date_from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(params.date_to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(params.date_from <= params.date_to).toBe(true);
    });
  });

  it('security: without payments_trail permission, Today filter is not shown and API is not called', async () => {
    denyTrailAccess();
    render(<PaymentsTrailPage />);
    await waitFor(() =>
      expect(screen.getByText(/Payments trail is restricted/i)).toBeInTheDocument()
    );
    expect(screen.queryByTestId('payments-trail-today')).not.toBeInTheDocument();
    expect(customersAPI.paymentsTrail).not.toHaveBeenCalled();
  });
});
