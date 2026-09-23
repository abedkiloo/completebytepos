import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { CheckoutPanel } from './CheckoutPanel';

jest.mock('../../Payments/StkWaitDialog', () => ({
  __esModule: true,
  default: ({ open, onPaid }) =>
    open ? (
      <button
        type="button"
        onClick={() => onPaid({ mpesa_receipt: 'QHX7K2L9M1' })}
      >
        mock-stk-paid
      </button>
    ) : null,
}));

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

function MpesaHarness({ onPay, receivedAmount = '100', customerPhone = '' }) {
  const [paymentMethod, setPaymentMethod] = useState('mpesa');
  const [paymentReference, setPaymentReference] = useState('');
  const [received, setReceived] = useState(receivedAmount);
  return (
    <CheckoutPanel
      {...baseProps}
      paymentMethod={paymentMethod}
      setPaymentMethod={setPaymentMethod}
      receivedAmount={received}
      setReceivedAmount={setReceived}
      paymentReference={paymentReference}
      setPaymentReference={setPaymentReference}
      onPay={onPay}
      enabledPaymentMethods={['cash', 'mpesa', 'card']}
      customerPhone={customerPhone}
    />
  );
}

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

  it('lets the cashier prompt M-Pesa or type a code', () => {
    const onPay = jest.fn();
    render(<MpesaHarness onPay={onPay} customerPhone="0712345678" />);

    expect(screen.getByTestId('mpesa-capture-prompt')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Send M-Pesa prompt/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Safaricom number/i)).toHaveValue('0712345678');

    fireEvent.click(screen.getByRole('button', { name: /Send M-Pesa prompt/i }));
    expect(onPay).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('mock-stk-paid'));
    expect(onPay).toHaveBeenCalledWith({ paymentReference: 'QHX7K2L9M1' });

    onPay.mockClear();
    fireEvent.click(screen.getByTestId('mpesa-capture-code'));
    fireEvent.change(screen.getByLabelText(/M-Pesa code/i), {
      target: { value: ' qhx 7k2 l9m1 ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Complete sale/i }));
    expect(onPay).toHaveBeenCalledWith({ paymentReference: 'QHX7K2L9M1' });
  });

  it('asks for a Safaricom number before sending a prompt', () => {
    const onPay = jest.fn();
    render(<MpesaHarness onPay={onPay} />);

    fireEvent.click(screen.getByRole('button', { name: /Send M-Pesa prompt/i }));
    expect(onPay).not.toHaveBeenCalled();
    expect(screen.queryByText('mock-stk-paid')).not.toBeInTheDocument();
    expect(screen.getByText(/Enter a Kenyan mobile/i)).toBeInTheDocument();
  });
});
