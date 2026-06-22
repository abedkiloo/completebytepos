import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

jest.mock('../../services/api', () => ({}));

import { AccountPaymentBlock } from './AccountPaymentBlock';

describe('AccountPaymentBlock', () => {
  test('renders nothing when not visible', () => {
    const { container } = render(<AccountPaymentBlock visible={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  test('shows pay later button and preview when checked with customer', () => {
    const onPayFullAmountLater = jest.fn();
    render(
      <AccountPaymentBlock
        visible
        checked
        hasRegisteredCustomer
        total={500}
        amountPaid="0"
        onCheckedChange={jest.fn()}
        onPayFullAmountLater={onPayFullAmountLater}
      />
    );

    expect(screen.getByText(/Payment on customer account/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Pay full amount later/i })).toBeInTheDocument();
    expect(screen.getByText(/Pay later:/i)).toBeInTheDocument();
    expect(screen.getByText(/500/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Pay full amount later/i }));
    expect(onPayFullAmountLater).toHaveBeenCalledTimes(1);
  });

  test('shows partial balance preview when some amount received', () => {
    render(
      <AccountPaymentBlock
        visible
        checked
        hasRegisteredCustomer
        total={500}
        amountPaid="200"
        onCheckedChange={jest.fn()}
        onPayFullAmountLater={jest.fn()}
      />
    );

    expect(screen.getByText(/Balance on account:/i)).toBeInTheDocument();
    expect(screen.getByText(/300/)).toBeInTheDocument();
  });

  test('checkbox calls onCheckedChange', () => {
    const onCheckedChange = jest.fn();
    render(
      <AccountPaymentBlock
        visible
        checked={false}
        hasRegisteredCustomer
        total={100}
        amountPaid=""
        onCheckedChange={onCheckedChange}
        onPayFullAmountLater={jest.fn()}
      />
    );

    fireEvent.click(screen.getByRole('checkbox'));
    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });
});
