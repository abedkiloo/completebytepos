/**
 * Summary cards on the customer list filter the table.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { customersAPI } from '../../services/api';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}));

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
jest.mock('../ConfirmDialog/ConfirmDialog', () => () => null);
jest.mock('../page', () => {
  const actual = jest.requireActual('../page');
  return {
    ...actual,
    PageShell: ({ children }) => children,
    PageHeader: ({ children }) => children,
    ListPaginationRail: ({ children }) => children,
  };
});

const summary = {
  count: 615,
  with_invoice: 0,
  invoice_outstanding: '0.00',
  with_wallet_debt: 2,
  total_wallet_debt: '14900.00',
  with_wallet_credit: 4,
  total_wallet_credit: '800.00',
};

describe('customer balance cards', () => {
  beforeEach(() => {
    customersAPI.list.mockResolvedValue({
      data: {
        count: 1,
        balance_summary: summary,
        results: [
          {
            id: 9,
            name: 'Debt Shop',
            phone: '0718000009',
            is_active: true,
            total_outstanding: '0',
            wallet_balance: '-14900.00',
          },
        ],
      },
    });
  });

  it('wallet debt cards filter the list and a second tap clears it', async () => {
    const Customers = require('./Customers').default;
    render(<Customers />);
    expect(await screen.findByText('Debt Shop')).toBeInTheDocument();
    expect(screen.getByTestId('customers-balance-wallet')).toHaveTextContent('14,900.00');

    fireEvent.click(screen.getByTestId('customers-balance-wallet'));
    await waitFor(() => {
      expect(customersAPI.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ balance: 'wallet_debt' })
      );
    });
    expect(screen.getByTestId('customers-balance-wallet')).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(screen.getByTestId('customers-balance-wallet-count'));
    await waitFor(() => {
      expect(customersAPI.list).toHaveBeenLastCalledWith(
        expect.not.objectContaining({ balance: expect.anything() })
      );
    });
  });

  it('invoice cards ask for customers with an invoice balance', async () => {
    const Customers = require('./Customers').default;
    render(<Customers />);
    await screen.findByText('Debt Shop');
    fireEvent.click(screen.getByTestId('customers-balance-invoice'));
    await waitFor(() => {
      expect(customersAPI.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ balance: 'invoice' })
      );
    });
    fireEvent.click(screen.getByTestId('customers-balance-all'));
    await waitFor(() => {
      expect(customersAPI.list).toHaveBeenLastCalledWith(
        expect.not.objectContaining({ balance: expect.anything() })
      );
    });
  });

  it('money we hold lists customers with a positive wallet', async () => {
    const Customers = require('./Customers').default;
    render(<Customers />);
    await screen.findByText('Debt Shop');
    expect(screen.getByTestId('customers-balance-credit')).toHaveTextContent('800.00');
    fireEvent.click(screen.getByTestId('customers-balance-credit'));
    await waitFor(() => {
      expect(customersAPI.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ balance: 'wallet_credit' })
      );
    });
    expect(screen.getByTestId('customers-balance-credit-count')).toHaveAttribute(
      'aria-pressed',
      'true'
    );
  });
});
