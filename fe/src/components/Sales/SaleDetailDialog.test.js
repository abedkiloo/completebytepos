import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SaleDetailDialog from './SaleDetailDialog';

const sale = {
  id: 1,
  sale_number: 'S-100',
  status: 'completed',
  refund_status: 'partial',
  created_at: '2026-06-24T10:00:00Z',
  customer_name: 'Martha',
  cashier_name: 'cashier1',
  subtotal: '1000',
  tax_amount: '0',
  discount_amount: '0',
  total: '1000',
  payment_method: 'cash',
  amount_paid: '600',
  change: '0',
  amount_refunded: '200',
  refundable_remaining: '400',
  items: [
    {
      id: 10,
      product_id: 2,
      variant_id: 5,
      product_name: 'Zipper',
      quantity: 2,
      quantity_refunded: 1,
      unit_price: '500',
      subtotal: '1000',
      size_name: 'Large',
      color_name: 'White',
    },
    {
      id: 11,
      product_id: 2,
      variant_id: 5,
      product_name: 'Zipper',
      quantity: 1,
      unit_price: '100',
      subtotal: '100',
      size_name: 'Large',
      color_name: 'White',
    },
  ],
};

describe('SaleDetailDialog', () => {
  it('shows payment status, balance due, and variant labels', () => {
    render(
      <SaleDetailDialog sale={sale} open onOpenChange={() => {}} showCustomerName />
    );

    expect(screen.getByText(/Sale — S-100/)).toBeInTheDocument();
    expect(screen.getByText('Partial refund')).toBeInTheDocument();
    expect(screen.getByText('Martha')).toBeInTheDocument();
    expect(screen.getAllByText('Large / White').length).toBeGreaterThan(0);
    expect(screen.getByText(/1 of 2 refunded/)).toBeInTheDocument();
    expect(screen.getByText('Partial payment')).toBeInTheDocument();
    expect(screen.getByText(/Balance due/)).toBeInTheDocument();
    expect(screen.getByText(/Amount refunded/)).toBeInTheDocument();
    expect(screen.getByText(/Refundable remaining/)).toBeInTheDocument();
  });

  it('flags duplicate lines and hides customer name when requested', () => {
    render(
      <SaleDetailDialog sale={sale} open onOpenChange={() => {}} showCustomerName={false} />
    );

    expect(screen.queryByText('Martha')).not.toBeInTheDocument();
    expect(screen.getByText('Duplicate lines')).toBeInTheDocument();
  });

  it('shows void/refund only when permitted and sale is refundable', () => {
    const onRefund = jest.fn();
    render(
      <SaleDetailDialog
        sale={sale}
        open
        onOpenChange={() => {}}
        canRefund
        onRefund={onRefund}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Void \/ Refund/i }));
    expect(onRefund).toHaveBeenCalledWith(sale);
  });

  it('hides void/refund for fully refunded sales', () => {
    render(
      <SaleDetailDialog
        sale={{
          ...sale,
          refund_status: 'refunded',
          refundable_remaining: '0',
        }}
        open
        onOpenChange={() => {}}
        canRefund
        onRefund={jest.fn()}
      />
    );

    expect(screen.queryByRole('button', { name: /Void \/ Refund/i })).not.toBeInTheDocument();
  });
});
