import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { CheckoutPanel } from './CheckoutPanel';

jest.mock('../../../utils/toast', () => ({
  toast: { info: jest.fn(), warning: jest.fn(), error: jest.fn(), success: jest.fn() },
}));

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
      enabledPaymentMethods={['cash', 'mpesa']}
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

  it('records payment before sending a sale for approval', () => {
    const onPay = jest.fn();
    render(
      <CheckoutPanel
        {...baseProps}
        receivedAmount="0"
        sendForApproval
        onPay={onPay}
      />
    );

    expect(screen.getByLabelText(/Amount received/i)).toBeInTheDocument();
    const send = screen.getByRole('button', { name: /Send for approval/i });
    expect(send).toBeDisabled();
  });

  it('lets the cashier type an M-Pesa code and shows coming soon for prompt', () => {
    const onPay = jest.fn();
    render(<MpesaHarness onPay={onPay} customerPhone="0712345678" />);

    expect(screen.getByTestId('mpesa-capture-prompt')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Complete sale/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/M-Pesa code/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Safaricom number/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('mpesa-capture-prompt'));
    expect(screen.queryByText('mock-stk-paid')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/M-Pesa code/i), {
      target: { value: ' qhx 7k2 l9m1 ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Complete sale/i }));
    expect(onPay).toHaveBeenCalledWith({ paymentReference: 'QHX7K2L9M1' });
  });

  it('requires an M-Pesa code before completing the sale', () => {
    const onPay = jest.fn();
    render(<MpesaHarness onPay={onPay} />);

    fireEvent.click(screen.getByRole('button', { name: /Complete sale/i }));
    expect(onPay).not.toHaveBeenCalled();
    expect(screen.queryByText('mock-stk-paid')).not.toBeInTheDocument();
    expect(screen.getByText(/Enter the M-Pesa code from the SMS/i)).toBeInTheDocument();
  });
});
