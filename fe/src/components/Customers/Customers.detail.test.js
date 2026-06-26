/**
 * Smoke + row-click wiring: full drill-down flow is covered in CustomerDetailDialog.test.js
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { customersAPI } from '../../services/api';

jest.mock('../../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (value) => value,
}));

jest.mock('../../services/api', () => ({
  customersAPI: {
    list: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
  salesAPI: { list: jest.fn() },
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({ settings: {} }),
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: () => ({ settings: {} }),
}));

jest.mock('./ReceiveWalletPaymentDialog', () => () => null);
jest.mock('./CustomerDetailDialog', () => ({
  __esModule: true,
  default: ({ customer, open }) =>
    open && customer ? <div data-testid="customer-detail">{customer.name}</div> : null,
}));
jest.mock('../ConfirmDialog/ConfirmDialog', () => () => null);
jest.mock('../page', () => ({
  PageShell: ({ children }) => children,
  PageHeader: ({ children }) => children,
  ListPaginationRail: ({ children }) => children,
}));

describe('Customers module', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    customersAPI.list.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 1,
            name: 'Martha',
            email: 'm@example.com',
            is_active: true,
            total_outstanding: '0',
            wallet_balance: '0',
          },
        ],
      },
    });
  });

  it('parses and exports the Customers component', () => {
    const Customers = require('./Customers').default;
    expect(typeof Customers).toBe('function');
  });

  it('opens CustomerDetailDialog when a table row is clicked', async () => {
    const Customers = require('./Customers').default;
    render(<Customers />);

    await waitFor(() => expect(screen.getByText('Martha')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Martha'));
    expect(await screen.findByTestId('customer-detail')).toHaveTextContent('Martha');
  });
});
