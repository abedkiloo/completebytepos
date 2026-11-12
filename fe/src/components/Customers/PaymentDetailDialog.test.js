import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import PaymentDetailDialog from './PaymentDetailDialog';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>
      {children}
    </a>
  ),
}));

jest.mock('../Shared/ReceiptImageLink', () => ({
  __esModule: true,
  default: ({ url, label }) => (
    <a href={url} data-testid="receipt-image-link">
      {label}
    </a>
  ),
}));

jest.mock('../ui/dialog', () => ({
  Dialog: ({ open, children }) => (open ? <div data-testid="dialog">{children}</div> : null),
  DialogContent: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

jest.mock('../ui/badge', () => ({
  Badge: ({ children }) => <span>{children}</span>,
}));

jest.mock('../ui/button', () => ({
  Button: ({ children, onClick, ...rest }) => (
    <button type="button" onClick={onClick} {...rest}>
      {children}
    </button>
  ),
}));

const payment = {
  kind: 'debt_settlement',
  id: 42,
  amount: '1500.00',
  occurred_at: '2026-11-12T10:00:00Z',
  customer_id: 7,
  customer_name: 'Ada',
  customer_phone: '0712345678',
  payment_method: 'mpesa',
  payment_method_label: 'M-PESA',
  mpesa_destination: 'till',
  mpesa_destination_label: 'Till',
  payer_name: 'John',
  payer_phone: '0700111222',
  reference: 'QHX7K2L9M1',
  received_by: 'Cashier A',
  receipt_image_url: '/media/receipts/a.jpg',
  paid_towards_label: 'Customer wallet debt',
  paid_towards: [{ type: 'customer_debt', label: 'Customer wallet debt', amount: '1500.00' }],
  previous_debt: '2000.00',
  new_debt: '500.00',
  notes: 'Paid at shop',
};

describe('PaymentDetailDialog', () => {
  it('shows amount, method with till, payer, reference, and screenshot', () => {
    render(<PaymentDetailDialog payment={payment} open onOpenChange={jest.fn()} />);

    expect(screen.getByTestId('payment-detail-dialog')).toBeInTheDocument();
    expect(screen.getByTestId('payment-detail-amount')).toHaveTextContent(/1,?500/);
    expect(screen.getByText(/M-PESA · Till/i)).toBeInTheDocument();
    expect(screen.getByText(/John · 0700111222/)).toBeInTheDocument();
    expect(screen.getByText('QHX7K2L9M1')).toBeInTheDocument();
    expect(screen.getByTestId('receipt-image-link')).toHaveAttribute(
      'href',
      '/media/receipts/a.jpg'
    );
    expect(screen.getByText(/Paid at shop/)).toBeInTheDocument();
  });

  it('calls onCorrect for debt settlements when allowed', () => {
    const onCorrect = jest.fn();
    render(
      <PaymentDetailDialog
        payment={payment}
        open
        canCorrect
        onCorrect={onCorrect}
        onOpenChange={jest.fn()}
      />
    );

    fireEvent.click(screen.getByTestId('payment-detail-correct'));
    expect(onCorrect).toHaveBeenCalled();
  });

  it('corrected: shows bank destination and paid-towards after receive', () => {
    render(
      <PaymentDetailDialog
        open
        onOpenChange={jest.fn()}
        payment={{
          ...payment,
          mpesa_destination: 'bank',
          mpesa_destination_label: 'Bank',
          paid_towards_label: 'Sale S-1',
          paid_towards: [
            { type: 'sale', sale_id: 1, sale_number: 'S-1', label: 'Sale S-1', amount: '1500.00' },
          ],
        }}
      />
    );
    expect(screen.getByText(/M-PESA · Bank/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Sale S-1/).length).toBeGreaterThan(0);
  });

  it('corrected: invoice payments still open as read-only detail', () => {
    render(
      <PaymentDetailDialog
        open
        onOpenChange={jest.fn()}
        payment={{
          kind: 'invoice_payment',
          id: 8,
          amount: '300.00',
          payment_method_label: 'Cash',
          paid_towards: [
            { type: 'invoice', invoice_id: 2, invoice_number: 'INV-2', label: 'Invoice INV-2' },
          ],
        }}
      />
    );
    expect(screen.getByText(/Invoice payment/i)).toBeInTheDocument();
    expect(screen.getByText(/Invoice INV-2/)).toBeInTheDocument();
    expect(screen.queryByTestId('payment-detail-correct')).not.toBeInTheDocument();
  });
});
