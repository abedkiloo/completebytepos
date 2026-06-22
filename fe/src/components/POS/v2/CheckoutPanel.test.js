import React from 'react';
import { render, screen } from '@testing-library/react';
import { CheckoutPanel } from './CheckoutPanel';

const baseProps = {
  subtotal: 100,
  discount: 0,
  discountAmount: 0,
  setDiscount: jest.fn(),
  discountType: 'amount',
  setDiscountType: jest.fn(),
  taxPct: 0,
  setTaxPct: jest.fn(),
  taxAmount: 0,
  total: 100,
  change: 0,
  deliveryEnabled: false,
  setDeliveryEnabled: jest.fn(),
  deliveryCost: 0,
  setDeliveryCost: jest.fn(),
  paymentMethod: 'cash',
  setPaymentMethod: jest.fn(),
  receivedAmount: '0',
  setReceivedAmount: jest.fn(),
  paymentReference: '',
  setPaymentReference: jest.fn(),
  submitting: false,
  onPay: jest.fn(),
  itemCount: 1,
  enabledPaymentMethods: [{ id: 'cash', label: 'Cash', requiresAmount: true }],
};

describe('CheckoutPanel', () => {
  it('enables pay for zero received on credit sale', () => {
    render(
      <CheckoutPanel
        {...baseProps}
        allowPartialPayment
        hasRegisteredCustomer
        paymentOnAccount
      />
    );

    expect(screen.getByRole('button', { name: /Complete sale/i })).not.toBeDisabled();
  });

  it('blocks pay for zero received without partial payment', () => {
    render(<CheckoutPanel {...baseProps} />);

    expect(screen.getByRole('button', { name: /Complete sale/i })).toBeDisabled();
  });
});
