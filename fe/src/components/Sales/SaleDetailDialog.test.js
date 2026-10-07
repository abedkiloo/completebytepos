import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import SaleDetailDialog from './SaleDetailDialog';
import { salesAPI } from '../../services/api';

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: () => ({ settings: { store_name: 'Omuwenga Suppliers' } }),
}));

jest.mock('../../services/api', () => ({
  salesAPI: { rejectComplete: jest.fn(), correctDate: jest.fn() },
}));

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
  it('renders nothing when sale is missing without violating hooks', () => {
    const { container } = render(
      <SaleDetailDialog sale={null} open onOpenChange={() => {}} />
    );
    expect(container.querySelector('[role="dialog"]')).not.toBeInTheDocument();
    expect(screen.queryByText(/Sale —/)).not.toBeInTheDocument();
  });

  it('shows a clean receipt with remaining items only; admin block has refund info', () => {
    render(
      <SaleDetailDialog sale={sale} open onOpenChange={() => {}} showCustomerName />
    );

    const receipt = document.querySelector('.receipt-content');

    expect(screen.getByText(/Sale — S-100/)).toBeInTheDocument();
    expect(screen.getByText('Omuwenga Suppliers')).toBeInTheDocument();
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

  it('shows accountability activity when the sale payload includes it', () => {
    render(
      <SaleDetailDialog
        sale={{
          ...sale,
          activity: [
            {
              id: 'recorded-1',
              kind: 'recorded',
              label: 'Sale recorded',
              actor: 'cashier1',
              actor_role: 'Cashier',
              at: '2026-06-24T10:00:00Z',
              comment: '',
              detail: '',
            },
            {
              id: 'void-1',
              kind: 'void',
              label: 'Void / refund applied',
              actor: 'manager1',
              actor_role: 'Applied by',
              at: '2026-06-24T12:00:00Z',
              comment: 'Damaged item',
              detail: '',
            },
          ],
        }}
        open
        onOpenChange={() => {}}
      />
    );

    expect(screen.getByTestId('sale-activity-trail')).toBeInTheDocument();
    expect(screen.getByText(/Cashier: cashier1/)).toBeInTheDocument();
    expect(screen.getByText(/Applied by: manager1/)).toBeInTheDocument();
    expect(screen.getByText('Damaged item')).toBeInTheDocument();
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

    fireEvent.click(screen.getByRole('button', { name: /^Void \/ refund$/i }));
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

    expect(screen.queryByRole('button', { name: /^Void \/ refund$/i })).not.toBeInTheDocument();
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
    expect(screen.queryByText(/Amount refunded/)).not.toBeInTheDocument();
  });

  it('shows salesperson action copy when a sale was returned', () => {
    render(
      <SaleDetailDialog
        sale={{
          ...sale,
          status: 'holding',
          needs_salesperson_action: true,
          rejection_reason: 'Wrong prices',
        }}
        open
        onOpenChange={() => {}}
        onPrint={jest.fn()}
      />
    );

    expect(screen.getAllByText('Needs salesperson action').length).toBeGreaterThan(0);
    expect(screen.getByText(/Manager comment: Wrong prices/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Print receipt/i })).not.toBeInTheDocument();
  });

  it('has no separate collect-payment step (money is taken before approval)', () => {
    render(
      <SaleDetailDialog
        sale={{ ...sale, status: 'pending_approval', refund_status: 'none' }}
        open
        onOpenChange={() => {}}
      />
    );
    expect(screen.queryByRole('button', { name: /Collect payment/i })).not.toBeInTheDocument();
  });

  it('lets admin return an approved sale for correction', async () => {
    salesAPI.rejectComplete.mockResolvedValue({
      data: { id: 1, status: 'holding', needs_salesperson_action: true },
    });
    const onReturned = jest.fn();
    const onOpenChange = jest.fn();
    render(
      <SaleDetailDialog
        sale={{ ...sale, status: 'completed', refund_status: 'none' }}
        open
        onOpenChange={onOpenChange}
        canReturnForCorrection
        onReturned={onReturned}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Return for correction/i }));
    fireEvent.change(screen.getByLabelText(/Reason/i), {
      target: { value: 'Wrong customer' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Confirm return/i }));
    await waitFor(() => {
      expect(salesAPI.rejectComplete).toHaveBeenCalledWith(1, {
        rejection_reason: 'Wrong customer',
      });
    });
    expect(onReturned).toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('lets a manager save a new sale date', async () => {
    salesAPI.correctDate.mockResolvedValue({
      data: { ...sale, occurred_at: '2026-10-01T10:00:00Z', can_correct_date: true },
    });
    const onUpdated = jest.fn();
    render(
      <SaleDetailDialog
        sale={{
          ...sale,
          occurred_at: '2026-09-30T10:00:00Z',
          can_correct_date: true,
        }}
        open
        onOpenChange={() => {}}
        onUpdated={onUpdated}
      />
    );

    fireEvent.change(screen.getByLabelText(/^Sale date$/i), {
      target: { value: '2026-10-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Save date/i }));
    await waitFor(() => {
      expect(salesAPI.correctDate).toHaveBeenCalledWith(1, { occurred_on: '2026-10-01' });
    });
    expect(onUpdated).toHaveBeenCalled();
  });
});
