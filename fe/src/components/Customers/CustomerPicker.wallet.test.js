import React from 'react';
import { render, screen } from '@testing-library/react';
import { CustomerPicker } from '../POS/v2/CustomerPicker';

const customers = [
  { id: 1, name: 'Alice', phone: '0700111222', wallet_balance: '-80.00' },
  { id: 2, name: 'Bob', phone: '0700333444', wallet_balance: '25.00' },
];

describe('CustomerPicker wallet display', () => {
  it('shows wallet balance on selected customer when enabled', () => {
    render(
      <CustomerPicker
        customers={customers}
        selectedCustomer={customers[0]}
        onSelect={jest.fn()}
        showWalletBalance
      />
    );

    expect(screen.getByText(/owed/i)).toBeInTheDocument();
  });

  it('hides wallet balance when disabled', () => {
    render(
      <CustomerPicker
        customers={customers}
        selectedCustomer={customers[0]}
        onSelect={jest.fn()}
        showWalletBalance={false}
      />
    );

    expect(screen.queryByText(/owed/i)).not.toBeInTheDocument();
  });
});
