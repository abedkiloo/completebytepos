import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import RefundSaleDialog from './RefundSaleDialog';

jest.mock('../Approvals/ChangeReasonField', () => ({
  __esModule: true,
  default: ({ value, onChange, label }) => (
    <label>
      {label}
      <input
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  ),
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: jest.fn(() => ({ settings: { maker_checker_enabled: false } })),
}));

const baseSale = {
  id: 1,
  sale_number: 'S-001',
  status: 'completed',
  refund_status: 'none',
  total: '500',
  refundable_remaining: '500',
  items: [
    {
      id: 10,
      product_id: 1,
      variant_id: 5,
      product_name: 'Zipper',
      quantity: 2,
      quantity_refunded: 0,
      refundable_quantity: 2,
      size_name: 'Large',
      color_name: 'White',
    },
    {
      id: 11,
      product_id: 1,
      variant_id: 5,
      product_name: 'Zipper',
      quantity: 1,
      quantity_refunded: 0,
      refundable_quantity: 1,
      size_name: 'Large',
      color_name: 'White',
    },
  ],
};

describe('RefundSaleDialog', () => {
  beforeEach(() => {
    const { useStoreSettings } = require('../../hooks/useStoreSettings');
    useStoreSettings.mockReturnValue({ settings: { maker_checker_enabled: false } });
  });

  it('blocks refund UI for non-refundable sales', () => {
    render(
      <RefundSaleDialog
        sale={{
          ...baseSale,
          status: 'completed',
          refund_status: 'refunded',
          refundable_remaining: '0',
        }}
        open
        onOpenChange={() => {}}
        onSubmit={() => {}}
        submitting={false}
      />
    );

    expect(screen.getByText(/cannot be voided/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Confirm void/i })).not.toBeInTheDocument();
  });

  it('submits full refund payload with reason', () => {
    const onSubmit = jest.fn();
    render(
      <RefundSaleDialog
        sale={baseSale}
        open
        onOpenChange={() => {}}
        onSubmit={onSubmit}
        submitting={false}
      />
    );

    fireEvent.change(screen.getByLabelText(/Reason for void/i), {
      target: { value: 'Customer return' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Confirm void/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      full: true,
      reason: 'Customer return',
    });
  });

  it('initializes partial qty from refundable quantity after prior refund', () => {
    const sale = {
      ...baseSale,
      items: [
        {
          id: 10,
          product_id: 1,
          product_name: 'Zipper',
          quantity: 3,
          quantity_refunded: 1,
          refundable_quantity: 2,
        },
      ],
    };

    render(
      <RefundSaleDialog
        sale={sale}
        open
        onOpenChange={() => {}}
        onSubmit={() => {}}
        submitting={false}
      />
    );

    fireEvent.click(screen.getByLabelText(/Partial \(by line\)/i));
    expect(screen.getByText(/1 already refunded/)).toBeInTheDocument();
    expect(screen.getByText(/2 refundable/)).toBeInTheDocument();
    const qtyInput = screen.getByDisplayValue('2');
    expect(qtyInput).toHaveAttribute('max', '2');
  });

  it('does not show duplicate helper for unique lines', () => {
    render(
      <RefundSaleDialog
        sale={{
          ...baseSale,
          items: [baseSale.items[0]],
        }}
        open
        onOpenChange={() => {}}
        onSubmit={() => {}}
        submitting={false}
      />
    );

    expect(screen.queryByText(/Duplicate lines detected/i)).not.toBeInTheDocument();
  });

  it('shows variant labels on refund lines', () => {
    render(
      <RefundSaleDialog
        sale={baseSale}
        open
        onOpenChange={() => {}}
        onSubmit={() => {}}
        submitting={false}
      />
    );

    fireEvent.click(screen.getByLabelText(/Partial \(by line\)/i));
    expect(screen.getAllByText('Large / White').length).toBeGreaterThan(0);
  });

  it('offers duplicate-line refund preset', () => {
    const onSubmit = jest.fn();
    render(
      <RefundSaleDialog
        sale={baseSale}
        open
        onOpenChange={() => {}}
        onSubmit={onSubmit}
        submitting={false}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Refund duplicate lines/i }));
    fireEvent.change(screen.getByLabelText(/Reason for void/i), {
      target: { value: 'Duplicate invoice lines' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Confirm void/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      full: false,
      reason: 'Duplicate invoice lines',
      items: [{ sale_item_id: 11, quantity: 1 }],
    });
  });

  it('shows submit for approval when maker-checker is on', () => {
    const { useStoreSettings } = require('../../hooks/useStoreSettings');
    useStoreSettings.mockReturnValue({ settings: { maker_checker_enabled: true } });

    render(
      <RefundSaleDialog
        sale={baseSale}
        open
        onOpenChange={() => {}}
        onSubmit={() => {}}
        submitting={false}
      />
    );

    expect(screen.getByRole('button', { name: /Submit for approval/i })).toBeInTheDocument();
  });
});
