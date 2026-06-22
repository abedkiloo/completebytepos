import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { PartialPaymentConfirm } from './PaymentConfirmDialogs';

describe('PartialPaymentConfirm', () => {
  test('shows full pay-later copy when nothing collected', () => {
    render(
      <PartialPaymentConfirm
        open
        onOpenChange={jest.fn()}
        pending={{ total: 500, received: 0, balance: 500 }}
        customer={{ name: 'Alice' }}
        submitting={false}
        onConfirm={jest.fn()}
      />
    );

    expect(screen.getByText(/Record full amount as pay later/i)).toBeInTheDocument();
    expect(screen.getByText(/No payment is collected now/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Record sale — pay later/i })).toBeInTheDocument();
  });

  test('shows partial balance copy when some amount received', () => {
    render(
      <PartialPaymentConfirm
        open
        onOpenChange={jest.fn()}
        pending={{ total: 500, received: 200, balance: 300 }}
        customer={{ name: 'Alice' }}
        submitting={false}
        onConfirm={jest.fn()}
      />
    );

    expect(screen.getByText(/Record balance as debt/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Record sale & debt/i })).toBeInTheDocument();
  });

  test('calls onConfirm when confirmed', () => {
    const onConfirm = jest.fn();
    render(
      <PartialPaymentConfirm
        open
        onOpenChange={jest.fn()}
        pending={{ total: 100, received: 0, balance: 100 }}
        customer={{ name: 'Bob' }}
        submitting={false}
        onConfirm={onConfirm}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Record sale — pay later/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
