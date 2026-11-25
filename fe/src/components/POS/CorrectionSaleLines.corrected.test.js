import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import CorrectionSaleLines from './CorrectionSaleLines';

jest.mock('./v2/usePOSState', () => ({
  getLineStockCap: () => null,
}));

/**
 * Corrected functionality: rectify sale must let the salesperson edit selling
 * price down toward catalog (same as a normal sale), not lock at the charged markup.
 */
describe('CorrectionSaleLines corrected selling price', () => {
  const markedUpLine = {
    id: 9,
    name: 'NO 5 Zipper',
    quantity: 11,
    price: 17600,
    catalog_price: 1800,
    selling_price: 1800,
    mrp: 1800,
    color_name: 'BLACK',
    stock_quantity: 100,
    track_stock: true,
  };

  function renderLines(overrides = {}) {
    const onSetLinePrice = jest.fn();
    render(
      <CorrectionSaleLines
        cart={[markedUpLine]}
        itemCount={11}
        subtotal={17600 * 11}
        saleNumber="SALE-683BE2DC"
        validateStock={false}
        mayEditPricing={false}
        onUpdateQty={jest.fn()}
        onSetQty={jest.fn()}
        onSetLinePrice={onSetLinePrice}
        onRemoveLine={jest.fn()}
        onClearLines={jest.fn()}
        {...overrides}
      />
    );
    return { onSetLinePrice };
  }

  it('shows controlled selling input at charged price with catalog min', () => {
    renderLines();
    const priceInput = screen.getByLabelText(/Unit price for NO 5 Zipper/i);
    expect(priceInput).toHaveValue(17600);
    expect(priceInput).toHaveAttribute('min', '1800');
    expect(screen.getByText(/List/i).textContent).toMatch(/1,?800/);
    expect(screen.getByText(/Custom price/i)).toBeInTheDocument();
  });

  it('commits a lower unit price when still at or above catalog (rectify markup)', () => {
    const { onSetLinePrice } = renderLines();
    const priceInput = screen.getByLabelText(/Unit price for NO 5 Zipper/i);
    fireEvent.change(priceInput, { target: { value: '1800' } });
    fireEvent.blur(priceInput);
    expect(onSetLinePrice).toHaveBeenCalledWith(
      '9',
      '1800',
      expect.objectContaining({ mayEditPricing: false })
    );
  });

  it('still forwards below-catalog attempts so parent can reject with toast', () => {
    const { onSetLinePrice } = renderLines();
    const priceInput = screen.getByLabelText(/Unit price for NO 5 Zipper/i);
    fireEvent.change(priceInput, { target: { value: '100' } });
    fireEvent.blur(priceInput);
    expect(onSetLinePrice).toHaveBeenCalledWith(
      '9',
      '100',
      expect.any(Object)
    );
  });
});
