/**
 * Stress / corrected-functionality: many payment shapes still render safely.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import PaymentDetailDialog from './PaymentDetailDialog';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to }) => <a href={typeof to === 'string' ? to : '#'}>{children}</a>,
}));

jest.mock('../Shared/ReceiptImageLink', () => ({
  __esModule: true,
  default: ({ label }) => <span data-testid="receipt">{label}</span>,
}));

jest.mock('../ui/dialog', () => ({
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
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

function basePayment(overrides = {}) {
  return {
    kind: 'debt_settlement',
    id: 1,
    amount: '10.00',
    payment_method: 'cash',
    payment_method_label: 'Cash',
    ...overrides,
  };
}

describe('PaymentDetailDialog stress + corrected cases', () => {
  it('renders 100 varied payments without crashing', () => {
    for (let i = 0; i < 100; i += 1) {
      const { unmount } = render(
        <PaymentDetailDialog
          open
          onOpenChange={jest.fn()}
          payment={basePayment({
            id: i + 1,
            amount: String(i + 0.5),
            payment_method: i % 2 === 0 ? 'mpesa' : 'cash',
            payment_method_label: i % 2 === 0 ? 'M-PESA' : 'Cash',
            mpesa_destination: i % 2 === 0 ? (i % 4 === 0 ? 'till' : 'bank') : '',
            payer_name: i % 3 === 0 ? `Payer ${i}` : '',
            receipt_image_url: i % 5 === 0 ? `/media/r${i}.jpg` : '',
            notes: i % 7 === 0 ? 'note' : '',
            paid_towards: i % 2 === 0
              ? [{ type: 'sale', label: `Sale ${i}`, amount: '1.00', sale_id: i }]
              : [],
          })}
        />
      );
      expect(screen.getByTestId('payment-detail-dialog')).toBeInTheDocument();
      unmount();
    }
  });

  it('does not invent a cash label when method is on_account / unpaid-like', () => {
    render(
      <PaymentDetailDialog
        open
        onOpenChange={jest.fn()}
        payment={basePayment({
          payment_method: 'on_account',
          payment_method_label: 'Debt',
          amount: '0.00',
        })}
      />
    );
    expect(screen.getByText(/^Debt$/i)).toBeInTheDocument();
    expect(screen.queryByText(/on account/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Cash$/)).not.toBeInTheDocument();
  });

  it('shows loading state without payment payload', () => {
    render(
      <PaymentDetailDialog open loading payment={null} onOpenChange={jest.fn()} />
    );
    expect(screen.getByText(/Loading payment/i)).toBeInTheDocument();
  });
});
