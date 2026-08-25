import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SaleCommitConfirm } from './SaleCommitConfirm';

const base = {
  total: 500,
  received: 500,
  change: 0,
  balance: 0,
  paymentMethod: 'cash',
  itemCount: 2,
  customerName: 'Ada',
  paymentReference: '',
};

describe('SaleCommitConfirm', () => {
  test('shows full-payment summary and confirms', () => {
    const onConfirm = jest.fn();
    render(
      <SaleCommitConfirm
        open
        onOpenChange={jest.fn()}
        summary={{ ...base, kind: 'full' }}
        submitting={false}
        onConfirm={onConfirm}
      />
    );

    expect(screen.getByText('Confirm sale?')).toBeInTheDocument();
    expect(screen.getByText('Ada')).toBeInTheDocument();
    expect(screen.getByText('Cash')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Confirm & complete sale/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  test('shows change for overpayment and payment reference', () => {
    render(
      <SaleCommitConfirm
        open
        onOpenChange={jest.fn()}
        summary={{
          ...base,
          kind: 'full',
          received: 600,
          change: 100,
          paymentReference: 'MPESA-1',
          itemCount: 0,
          customerName: null,
        }}
        onConfirm={jest.fn()}
      />
    );

    expect(screen.getByText('Change')).toBeInTheDocument();
    expect(screen.getByText('MPESA-1')).toBeInTheDocument();
    expect(screen.queryByText('Items')).not.toBeInTheDocument();
    expect(screen.queryByText('Customer')).not.toBeInTheDocument();
  });

  test('shows pay-later wording', () => {
    render(
      <SaleCommitConfirm
        open
        onOpenChange={jest.fn()}
        summary={{
          ...base,
          kind: 'pay_later',
          total: 200,
          received: 0,
          balance: 200,
          customerName: 'Bob',
        }}
        onConfirm={jest.fn()}
      />
    );

    expect(screen.getByText(/Confirm pay-later sale/i)).toBeInTheDocument();
    expect(screen.getByText(/Amount due \(pay later\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Collected now/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Confirm — pay later/i })).toBeInTheDocument();
  });

  test('shows partial debt wording and cancel closes', () => {
    const onOpenChange = jest.fn();
    render(
      <SaleCommitConfirm
        open
        onOpenChange={onOpenChange}
        summary={{
          ...base,
          kind: 'partial',
          total: 200,
          received: 50,
          balance: 150,
        }}
        onConfirm={jest.fn()}
      />
    );

    expect(screen.getByText(/Confirm partial payment/i)).toBeInTheDocument();
    expect(screen.getByText(/Balance \(debt\)/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test('defaults kind to full and shows Saving while submitting', () => {
    render(
      <SaleCommitConfirm
        open
        onOpenChange={jest.fn()}
        summary={{ ...base, kind: undefined }}
        submitting
        onConfirm={jest.fn()}
      />
    );

    expect(screen.getByText('Confirm sale?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Saving/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled();
  });

  test('renders nothing without summary', () => {
    const { container } = render(
      <SaleCommitConfirm open onOpenChange={jest.fn()} summary={null} onConfirm={jest.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
