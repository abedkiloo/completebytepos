import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AccountPaymentBlock } from './AccountPaymentBlock';

describe('AccountPaymentBlock', () => {
  test('shows debt button and preview when checked with customer', () => {
    const onPayFullAmountLater = jest.fn();
    render(
      <AccountPaymentBlock
        visible
        checked
        hasRegisteredCustomer
        total={500}
        amountPaid={0}
        onCheckedChange={jest.fn()}
        onPayFullAmountLater={onPayFullAmountLater}
      />
    );

    expect(screen.getByText(/Allow debt \/ partial payment/i)).toBeInTheDocument();
    expect(screen.getByText(/Debt:/i)).toBeInTheDocument();
    expect(screen.queryByText(/on account/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Record full sale as debt/i }));
    expect(onPayFullAmountLater).toHaveBeenCalled();
  });

  test('shows balance as debt for partial collection', () => {
    render(
      <AccountPaymentBlock
        visible
        checked
        hasRegisteredCustomer
        total={500}
        amountPaid={200}
        onCheckedChange={jest.fn()}
      />
    );
    expect(screen.getByText(/Balance \(debt\):/i)).toBeInTheDocument();
    expect(screen.queryByText(/on account/i)).not.toBeInTheDocument();
  });
});
