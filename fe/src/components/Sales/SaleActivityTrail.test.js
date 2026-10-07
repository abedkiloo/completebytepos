import React from 'react';
import { render, screen } from '@testing-library/react';
import SaleActivityTrail from './SaleActivityTrail';

describe('SaleActivityTrail', () => {
  it('renders nothing when activity is empty', () => {
    const { container } = render(<SaleActivityTrail activity={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows who recorded, approved, and voided the sale', () => {
    render(
      <SaleActivityTrail
        activity={[
          {
            id: 'recorded-1',
            kind: 'recorded',
            label: 'Sale recorded',
            actor: 'cashier1',
            actor_role: 'Cashier',
            at: '2026-10-07T08:00:00Z',
            comment: '',
            detail: '',
          },
          {
            id: 'approved-2',
            kind: 'approved',
            label: 'Sale approved',
            actor: 'manager1',
            actor_role: 'Approver',
            at: '2026-10-07T09:00:00Z',
            comment: '',
            detail: '',
          },
          {
            id: 'void-3',
            kind: 'void',
            label: 'Void / refund applied',
            actor: 'admin1',
            actor_role: 'Applied by',
            at: '2026-10-07T10:00:00Z',
            comment: 'Customer return',
            detail: 'RF-1 · 100.00',
          },
        ]}
      />
    );

    expect(screen.getByTestId('sale-activity-trail')).toBeInTheDocument();
    expect(screen.getByText('Sale recorded')).toBeInTheDocument();
    expect(screen.getByText(/Cashier: cashier1/)).toBeInTheDocument();
    expect(screen.getByText('Sale approved')).toBeInTheDocument();
    expect(screen.getByText(/Approver: manager1/)).toBeInTheDocument();
    expect(screen.getByText('Void / refund applied')).toBeInTheDocument();
    expect(screen.getByText('Customer return')).toBeInTheDocument();
  });
});
