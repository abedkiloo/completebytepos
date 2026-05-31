import React from 'react';
import { render, screen } from '@testing-library/react';
import { SELLING_PRICE_CLASS } from '../../utils/productDisplay';

function SellingPriceCell({ amount, isCost = false }) {
  const className = isCost ? 'text-muted-foreground tabular-nums' : SELLING_PRICE_CLASS;
  return <span data-testid={isCost ? 'cost' : 'selling'} className={className}>{amount}</span>;
}

describe('Products selling price display', () => {
  test('selling price uses success class', () => {
    render(<SellingPriceCell amount="KES 800.00" />);
    const el = screen.getByTestId('selling');
    expect(el.className).toContain('text-success');
    expect(el.className).not.toContain('text-muted-foreground');
  });

  test('cost price does not use success class', () => {
    render(<SellingPriceCell amount="KES 50.00" isCost />);
    const el = screen.getByTestId('cost');
    expect(el.className).not.toContain('text-success');
    expect(el.className).toContain('text-muted-foreground');
  });
});
