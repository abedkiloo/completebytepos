import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  ThermalReceipt,
  RECEIPT_REACH_US_LABEL,
  RECEIPT_REACH_US_PHONE,
} from './ThermalReceipt';

const store = {
  storeName: 'Test Duka',
  receiptFooter: 'Asante kwa biashara yako.',
};

const sale = {
  sale_number: 'S-9',
  created_at: '2026-09-22T10:00:00Z',
  served_by_name: 'Amina',
  payment_method: 'cash',
  total: 100,
  amount_paid: 100,
  change: 0,
  items: [
    {
      product_name: 'Soap',
      quantity: 1,
      unit_price: 100,
      subtotal: 100,
    },
  ],
};

describe('ThermalReceipt', () => {
  it('shows served by and a reach-us button', () => {
    render(<ThermalReceipt sale={sale} store={store} />);

    expect(screen.getByText('Served by')).toBeInTheDocument();
    expect(screen.getByText('Amina')).toBeInTheDocument();
    expect(screen.queryByText('Cashier')).not.toBeInTheDocument();

    const link = screen.getByTestId('receipt-reach-us');
    expect(link).toHaveAttribute('href', `tel:${RECEIPT_REACH_US_PHONE}`);
    expect(link).toHaveTextContent(RECEIPT_REACH_US_LABEL);
  });

  it('falls back to cashier name when served by is missing', () => {
    render(
      <ThermalReceipt
        sale={{ ...sale, served_by_name: '', cashier_name: 'Kai' }}
        store={store}
      />
    );

    expect(screen.getByText('Served by')).toBeInTheDocument();
    expect(screen.getByText('Kai')).toBeInTheDocument();
  });
});
