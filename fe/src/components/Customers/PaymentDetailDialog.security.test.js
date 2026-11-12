import React from 'react';
import { render, screen } from '@testing-library/react';
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

const settlement = {
  kind: 'debt_settlement',
  id: 42,
  amount: '1500.00',
  occurred_at: '2026-11-12T10:00:00Z',
  customer_id: 7,
  customer_name: 'Ada',
  payment_method: 'mpesa',
  payment_method_label: 'M-PESA',
  mpesa_destination: 'till',
  mpesa_destination_label: 'Till',
  payer_name: 'Mary',
  payer_phone: '0700111222',
  reference: 'QHXSECRET01',
  receipt_image_url: '/media/secret.jpg',
  received_by: 'Cashier',
};

describe('PaymentDetailDialog security', () => {
  it('hides correct action unless canCorrect is explicitly granted', () => {
    render(
      <PaymentDetailDialog payment={settlement} open onOpenChange={jest.fn()} />
    );
    expect(screen.queryByTestId('payment-detail-correct')).not.toBeInTheDocument();
  });

  it('does not invent a correct button for invoice / sale tenders', () => {
    render(
      <PaymentDetailDialog
        open
        canCorrect
        onCorrect={jest.fn()}
        onOpenChange={jest.fn()}
        payment={{
          kind: 'sale_payment',
          id: 9,
          amount: '20.00',
          payment_method_label: 'Cash',
        }}
      />
    );
    expect(screen.queryByTestId('payment-detail-correct')).not.toBeInTheDocument();
  });

  it('renders nothing when closed or without payment (no accidental data paint)', () => {
    const { container: closed } = render(
      <PaymentDetailDialog payment={settlement} open={false} onOpenChange={jest.fn()} />
    );
    expect(closed.querySelector('[data-testid="dialog"]')).toBeNull();

    const { container: empty } = render(
      <PaymentDetailDialog payment={null} open onOpenChange={jest.fn()} />
    );
    expect(empty.querySelector('[data-testid="dialog"]')).toBeNull();
  });

  it('stress: repeated open without canCorrect never exposes correct control', () => {
    for (let i = 0; i < 40; i += 1) {
      const { unmount } = render(
        <PaymentDetailDialog
          payment={{ ...settlement, id: i + 1 }}
          open
          onOpenChange={jest.fn()}
        />
      );
      expect(screen.queryByTestId('payment-detail-correct')).not.toBeInTheDocument();
      unmount();
    }
  });
});
