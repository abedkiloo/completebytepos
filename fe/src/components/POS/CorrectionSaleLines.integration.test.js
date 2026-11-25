import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import CorrectionSaleLines from './CorrectionSaleLines';
import {
  lineCatalogFloor,
  saleUnitPriceOverrideError,
  normalizeMoney,
} from '../../utils/saleUnitPrice';

jest.mock('./v2/usePOSState', () => ({
  getLineStockCap: () => null,
}));

/**
 * Integration: CorrectionSaleLines + in-memory setLinePrice (billing POS contract).
 */
function Harness() {
  const [cart, setCart] = useState([
    {
      id: 9,
      name: 'NO 5 Zipper',
      quantity: 11,
      price: 17600,
      catalog_price: 1800,
      selling_price: 1800,
      mrp: 1800,
    },
  ]);

  const setLinePrice = (key, rawPrice, { mayEditPricing = false } = {}) => {
    setCart((prev) => {
      const target = prev.find((i) => String(i.id) === String(key));
      if (!target) return prev;
      const catalog = lineCatalogFloor(target);
      const error = saleUnitPriceOverrideError({
        catalogPrice: catalog,
        requestedPrice: rawPrice,
        mayEditPricing,
      });
      if (error) return prev;
      const nextPrice = normalizeMoney(rawPrice);
      return prev.map((item) =>
        String(item.id) === String(key)
          ? {
              ...item,
              price: nextPrice,
              catalog_price: item.catalog_price ?? catalog,
              selling_price: item.catalog_price ?? item.selling_price ?? catalog,
            }
          : item
      );
    });
  };

  const subtotal = cart.reduce((s, i) => s + i.price * i.quantity, 0);

  return (
    <CorrectionSaleLines
      cart={cart}
      itemCount={cart.reduce((s, i) => s + i.quantity, 0)}
      subtotal={subtotal}
      saleNumber="SALE-INT"
      validateStock={false}
      mayEditPricing={false}
      onUpdateQty={jest.fn()}
      onSetQty={jest.fn()}
      onSetLinePrice={setLinePrice}
      onRemoveLine={jest.fn()}
      onClearLines={jest.fn()}
    />
  );
}

describe('CorrectionSaleLines integration', () => {
  it('updates line total after salesperson lowers selling price to catalog', () => {
    render(<Harness />);
    const priceInput = screen.getByLabelText(/Unit price for NO 5 Zipper/i);
    fireEvent.change(priceInput, { target: { value: '1800' } });
    fireEvent.blur(priceInput);
    expect(screen.getByTestId('correction-lines-subtotal').textContent).toMatch(
      /19,?800/
    );
    expect(priceInput).toHaveValue(1800);
  });

  it('keeps charged price when salesperson tries to go below catalog', () => {
    render(<Harness />);
    const priceInput = screen.getByLabelText(/Unit price for NO 5 Zipper/i);
    fireEvent.change(priceInput, { target: { value: '500' } });
    fireEvent.blur(priceInput);
    expect(priceInput).toHaveValue(17600);
    expect(screen.getByTestId('correction-lines-subtotal').textContent).toMatch(
      /193,?600/
    );
  });
});
