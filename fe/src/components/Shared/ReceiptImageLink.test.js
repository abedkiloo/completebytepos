import React from 'react';
import { render, screen } from '@testing-library/react';

import ReceiptImageLink from './ReceiptImageLink';

describe('ReceiptImageLink', () => {
  it('renders nothing when url is empty', () => {
    const { container } = render(<ReceiptImageLink url="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows a thumbnail that opens the full image', () => {
    render(
      <ReceiptImageLink url="/media/debt_receipts/demo.png" label="Payment screenshot" />
    );
    const link = screen.getByTestId('receipt-image-link');
    expect(link).toHaveAttribute('href', '/media/debt_receipts/demo.png');
    expect(link).toHaveAttribute('target', '_blank');
    expect(screen.getByTestId('receipt-image-thumb')).toBeInTheDocument();
    expect(screen.getByText('Payment screenshot')).toBeInTheDocument();
  });

  it('card variant shows open-full caption', () => {
    render(
      <ReceiptImageLink
        url="/media/sale_backfill/paper.jpg"
        label="Paper receipt"
        variant="card"
      />
    );
    expect(screen.getByText('Open full image')).toBeInTheDocument();
  });
});
