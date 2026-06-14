import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ProductVariantsPanel from './ProductVariantsPanel';
import { variantsAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  variantsAPI: {
    getByProduct: jest.fn(),
    update: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: {
    warning: jest.fn(),
    success: jest.fn(),
    error: jest.fn(),
    info: jest.fn(),
  },
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: jest.fn(() => ({
    settings: { maker_checker_enabled: true },
  })),
}));

import { useStoreSettings } from '../../hooks/useStoreSettings';

const sizes = [{ id: 1, name: 'Large', code: 'L' }];
const colors = [{ id: 10, name: 'Blue' }];

describe('ProductVariantsPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Element.prototype.scrollIntoView = jest.fn();
    useStoreSettings.mockReturnValue({
      settings: { maker_checker_enabled: true },
    });
  });

  test('create mode adds combination and notifies parent via onDraftsChange', async () => {
    const onDraftsChange = jest.fn();
    render(
      <ProductVariantsPanel
        sizes={sizes}
        colors={colors}
        canEditPrice
        canEditMrp
        canEditStock
        onDraftsChange={onDraftsChange}
      />
    );

    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '1' } });
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: /add variant/i }));

    await waitFor(() => {
      expect(onDraftsChange).toHaveBeenCalled();
    });
    const drafts = onDraftsChange.mock.calls.at(-1)[0];
    expect(drafts['1-10']).toMatchObject({
      price: '',
      mrp: '',
      stock_quantity: '',
      is_active: true,
    });
    expect(screen.getByPlaceholderText('List price')).toBeInTheDocument();
    expect(screen.getAllByRole('spinbutton').length).toBeGreaterThanOrEqual(3);
  });

  test('edit mode hides stock input and strips stock from patch', async () => {
    useStoreSettings.mockReturnValue({
      settings: { maker_checker_enabled: false },
    });
    variantsAPI.getByProduct.mockResolvedValue({
      data: {
        results: [
          {
            id: 42,
            product: 5,
            size: 1,
            color: 10,
            sku: 'SKU-1',
            price: '100.00',
            mrp: '120.00',
            stock_quantity: 8,
            is_active: true,
          },
        ],
      },
    });
    variantsAPI.update.mockResolvedValue({ status: 200 });

    render(
      <ProductVariantsPanel
        productId={5}
        sizes={sizes}
        colors={colors}
        canEditPrice
        canEditMrp
        canEditStock
      />
    );

    await screen.findByRole('button', { name: /save variant/i });
    expect(screen.queryByLabelText(/Opening stock/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue('100.00'), {
      target: { value: '110.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save variant/i }));

    await waitFor(() => {
      expect(variantsAPI.update).toHaveBeenCalled();
    });
    const payload = variantsAPI.update.mock.calls[0][1];
    expect(payload).toMatchObject({
      price: '110.00',
      selling_price: '110.00',
    });
    expect(payload.stock_quantity).toBeUndefined();
    expect(payload.reason).toBeUndefined();
  });

  test('blocks save when MRP is below selling price', async () => {
    variantsAPI.getByProduct.mockResolvedValue({
      data: {
        results: [
          {
            id: 42,
            product: 5,
            size: 1,
            color: 10,
            sku: 'SKU-1',
            price: '100.00',
            stock_quantity: 8,
            is_active: true,
          },
        ],
      },
    });

    render(
      <ProductVariantsPanel
        productId={5}
        sizes={sizes}
        colors={colors}
        canEditPrice
        canEditMrp
      />
    );

    await screen.findByRole('button', { name: /save variant/i });
    fireEvent.change(screen.getByPlaceholderText('List price'), {
      target: { value: '80.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save variant/i }));

    expect(toast.warning).toHaveBeenCalledWith(
      'MRP should be at least the selling price for variant Large / Blue.'
    );
    expect(variantsAPI.update).not.toHaveBeenCalled();
  });

  test('requires reason when maker-checker on and price changes', async () => {
    variantsAPI.getByProduct.mockResolvedValue({
      data: {
        results: [
          {
            id: 42,
            product: 5,
            size: 1,
            color: 10,
            sku: 'SKU-1',
            price: '100.00',
            stock_quantity: 8,
            is_active: true,
          },
        ],
      },
    });

    render(
      <ProductVariantsPanel
        productId={5}
        sizes={sizes}
        colors={colors}
        canEditPrice
      />
    );

    await screen.findByRole('button', { name: /save variant/i });
    fireEvent.change(screen.getByDisplayValue('100.00'), {
      target: { value: '140.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: /submit for approval/i }));

    expect(toast.warning).toHaveBeenCalledWith(
      'Enter a reason below — price, cost, or status changes need approval.'
    );
    expect(variantsAPI.update).not.toHaveBeenCalled();
  });
});
