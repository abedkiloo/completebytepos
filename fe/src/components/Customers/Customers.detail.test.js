/**
 * Customers list navigates to the dedicated detail screen (no popup).
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { customersAPI } from '../../services/api';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
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

  it('navigates to customer detail when a table row is clicked', async () => {
    const Customers = require('./Customers').default;
    render(<Customers />);

    await screen.findByText('Martha');
    fireEvent.click(screen.getByText('Martha'));
    expect(mockNavigate).toHaveBeenCalledWith('/customers/1');
  });

  it('filters to customers added today and back', async () => {
    const { getTodayDateString } = require('../../utils/debtManagement');
    const Customers = require('./Customers').default;
    render(<Customers />);

    await screen.findByText('Martha');
    expect(customersAPI.list).toHaveBeenLastCalledWith(
      expect.not.objectContaining({ created_on: expect.anything() })
    );
    expect(screen.queryByTestId('customers-added-count')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('customers-added-today'));
    await waitFor(() => {
      expect(customersAPI.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ created_on: getTodayDateString() })
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId('customers-added-count')).toHaveTextContent(
        '1 customer added today'
      );
    });

    fireEvent.click(screen.getByTestId('customers-added-today'));
    await waitFor(() => {
      expect(customersAPI.list).toHaveBeenLastCalledWith(
        expect.not.objectContaining({ created_on: expect.anything() })
      );
    });
  });

  it('shows how many customers were added on a picked day', async () => {
    const Customers = require('./Customers').default;
    render(<Customers />);
    await screen.findByText('Martha');

    customersAPI.list.mockResolvedValue({
      data: {
        count: 3,
        results: [
          { id: 2, name: 'A', is_active: true, total_outstanding: '0', wallet_balance: '0' },
          { id: 3, name: 'B', is_active: true, total_outstanding: '0', wallet_balance: '0' },
          { id: 4, name: 'C', is_active: true, total_outstanding: '0', wallet_balance: '0' },
        ],
      },
    });
    fireEvent.change(screen.getByTestId('customers-added-on'), {
      target: { value: '2026-09-15' },
    });

    await waitFor(() => {
      expect(customersAPI.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ created_on: '2026-09-15' })
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId('customers-added-count')).toHaveTextContent(
        /3 customers added on 15 Sept? 2026/
      );
    });
  });
});
