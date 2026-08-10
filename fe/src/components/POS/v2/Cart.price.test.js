import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Cart } from './Cart';

jest.mock('./usePOSState', () => ({
  getLineStockCap: () => null,
}));

jest.mock('../../../utils/roleAccess', () => ({
  userMayEditFinancialFieldsFromStorage: jest.fn(() => false),
}));

describe('Cart unit price editing', () => {
  const item = {
    id: 1,
    name: 'Zipper',
    quantity: 2,
    price: 20,
    catalog_price: 20,
    selling_price: 20,
    stock_quantity: 100,
    track_stock: true,
  };

  it('lets cashier raise unit price above catalog selling price', () => {
    const onSetPrice = jest.fn(() => true);
    render(
      <Cart
        items={[item]}
        onAdjust={jest.fn()}
        onSetQuantity={jest.fn()}
        onSetPrice={onSetPrice}
        onRemove={jest.fn()}
        onClear={jest.fn()}
        validateStock={false}
      />
    );

    const priceInput = screen.getByLabelText(/Unit price for Zipper/i);
    fireEvent.change(priceInput, { target: { value: '50' } });
    fireEvent.blur(priceInput);

    expect(onSetPrice).toHaveBeenCalledWith(
      expect.objectContaining({ id: 1 }),
      '50',
      expect.any(Object)
    );
    expect(onSetPrice.mock.calls[0][2].mayEditPricing).toBeFalsy();
  });
});
