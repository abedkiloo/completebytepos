import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
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
  it('shows a clean receipt with remaining items only; admin block has refund info', () => {
    render(
      <SaleDetailDialog sale={sale} open onOpenChange={() => {}} showCustomerName />
    );

    const receipt = document.querySelector('.receipt-content');

    expect(screen.getByText(/Sale — S-100/)).toBeInTheDocument();
    expect(screen.getByText('Martha')).toBeInTheDocument();
    expect(within(receipt).getAllByText('Large / White').length).toBe(2);
    expect(within(receipt).queryByText(/returned/i)).not.toBeInTheDocument();
    expect(within(receipt).queryByText(/refund/i)).not.toBeInTheDocument();
    expect(within(receipt).queryByText(/final state/i)).not.toBeInTheDocument();
    expect(within(receipt).getAllByText('Total').length).toBeGreaterThan(0);
    expect(within(receipt).queryByText(/Net total/i)).not.toBeInTheDocument();

    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getAllByText('Partial refund').length).toBeGreaterThan(0);
    expect(screen.getByText('Partial payment')).toBeInTheDocument();
    expect(screen.getByText(/Amount refunded/)).toBeInTheDocument();
    expect(screen.getByText(/Still refundable/)).toBeInTheDocument();
  });

  it('omits fully returned lines from the receipt', () => {
    render(
      <SaleDetailDialog
        sale={{
          ...sale,
          items: [
            ...sale.items,
            {
              id: 12,
              product_name: 'Returned shirt',
              quantity: 1,
              quantity_refunded: 1,
              unit_price: '300',
              subtotal: '300',
            },
          ],
        }}
        open
        onOpenChange={() => {}}
      />
    );

    const receipt = document.querySelector('.receipt-content');
    expect(within(receipt).queryByText('Returned shirt')).not.toBeInTheDocument();
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

  it('hides admin block when showAdminDetails is false', () => {
    render(
      <SaleDetailDialog
        sale={sale}
        open
        onOpenChange={() => {}}
        showAdminDetails={false}
      />
    );

    expect(screen.queryByText('Admin')).not.toBeInTheDocument();
    expect(screen.queryByText('Partial refund')).not.toBeInTheDocument();
  });
});
