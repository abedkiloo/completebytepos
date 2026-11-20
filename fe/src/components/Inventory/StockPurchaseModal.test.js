import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import StockPurchaseModal from './StockPurchaseModal';
import { inventoryAPI, pendingChangesAPI, productsAPI, variantsAPI } from '../../services/api';
import { useStoreSettings } from '../../hooks/useStoreSettings';

jest.mock('../../services/api', () => ({
  inventoryAPI: { purchase: jest.fn(), pendingPrices: jest.fn() },
  pendingChangesAPI: { mySubmissions: jest.fn() },
  productsAPI: { list: jest.fn() },
  variantsAPI: { getByProduct: jest.fn() },
}));

jest.mock('../../utils/toast', () => ({
  toast: { warning: jest.fn(), success: jest.fn(), error: jest.fn() },
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: jest.fn(() => ({ settings: { maker_checker_enabled: false } })),
}));

jest.mock('../Approvals/ChangeReasonField', () => () => null);

const emptySize = {
  id: 9,
  size_name: 'Small',
  color_name: 'Red',
  sku: 'CLOTH-S',
  stock_quantity: 0,
  price: '90.00',
  is_active: true,
};

describe('StockPurchaseModal variant purchase', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    variantsAPI.getByProduct.mockResolvedValue({ data: { results: [emptySize] } });
    inventoryAPI.pendingPrices.mockResolvedValue({ data: [] });
    inventoryAPI.purchase.mockResolvedValue({ status: 201, data: {} });
    pendingChangesAPI.mySubmissions.mockResolvedValue({ data: [] });
    productsAPI.list.mockResolvedValue({ data: [] });
    useStoreSettings.mockReturnValue({ settings: { maker_checker_enabled: false } });
  });

  test('confirms a purchase onto a size that has no stock yet', async () => {
    const onSave = jest.fn();
    render(
      <StockPurchaseModal
        product={{
          id: 3,
          name: 'Cloth',
          sku: 'CLOTH',
          stock_quantity: 10,
          has_variants: true,
          initial_variant_id: 9,
          variants: [emptySize],
        }}
        onClose={jest.fn()}
        onSave={onSave}
      />
    );

    const size = await screen.findByLabelText(/Size and colour/i);
    await waitFor(() => expect(size.value).toBe('9'));
    fireEvent.change(screen.getByPlaceholderText(/New selling price/i), {
      target: { value: '110' },
    });
    fireEvent.click(screen.getByRole('button', { name: /record purchase/i }));

    expect(await screen.findByText(/no stock yet/i)).toBeInTheDocument();
    expect(screen.getByText('Small / Red')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /confirm & record purchase/i }));

    await waitFor(() => {
      expect(inventoryAPI.purchase).toHaveBeenCalledWith(
        expect.objectContaining({
          product_id: 3,
          variant_id: 9,
          quantity: 1,
          price_mode: 'new',
          unit_sell_price: '110',
        })
      );
    });
    expect(onSave).toHaveBeenCalled();
  });

  test('shows the rejection reason and opens the purchase to correct', async () => {
    useStoreSettings.mockReturnValue({ settings: { maker_checker_enabled: true } });
    pendingChangesAPI.mySubmissions.mockResolvedValue({
      data: [{
        id: 12,
        status: 'rejected',
        entity_repr: 'Nails',
        rejection_reason: 'Wrong quantity',
        apply_payload: {
          product_id: 4,
          quantity: 9,
          price_mode: 'new',
          unit_sell_price: '15',
        },
      }],
    });
    render(<StockPurchaseModal product={null} onClose={jest.fn()} onSave={jest.fn()} />);

    expect(await screen.findByText('Wrong quantity')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Correct' }));
    expect(screen.getByTestId('returned-purchase-reason')).toHaveTextContent('Wrong quantity');
    expect(screen.getByRole('button', { name: 'Send correction' })).toBeInTheDocument();
  });
});
