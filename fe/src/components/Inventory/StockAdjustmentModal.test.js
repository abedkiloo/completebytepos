import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import StockAdjustmentModal from './StockAdjustmentModal';
import { inventoryAPI, productsAPI, variantsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { PENDING_APPROVAL_MESSAGE } from '../../utils/makerChecker';

jest.mock('../../services/api', () => ({
  inventoryAPI: { adjust: jest.fn() },
  productsAPI: { list: jest.fn() },
  variantsAPI: { getByProduct: jest.fn() },
}));

jest.mock('../../utils/toast', () => ({
  toast: {
    warning: jest.fn(),
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: jest.fn(() => ({
    settings: { maker_checker_enabled: false },
  })),
}));

jest.mock('../Approvals/ChangeReasonField', () => () => null);

import { useStoreSettings } from '../../hooks/useStoreSettings';

const variantProduct = {
  id: 5,
  name: 'T-Shirt',
  has_variants: true,
  stock_quantity: 20,
};

const variants = [
  { id: 41, product: 5, size_name: 'Large', color_name: 'Blue', sku: 'TS-L-B', stock_quantity: 12 },
  { id: 42, product: 5, size_name: 'Medium', color_name: 'Blue', sku: 'TS-M-B', stock_quantity: 8 },
];

describe('StockAdjustmentModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useStoreSettings.mockReturnValue({
      settings: { maker_checker_enabled: false },
    });
    variantsAPI.getByProduct.mockResolvedValue({ data: { results: variants } });
    inventoryAPI.adjust.mockResolvedValue({ status: 200 });
  });

  test('pre-selected variant product renders per-variant inputs', async () => {
    render(<StockAdjustmentModal product={variantProduct} onClose={jest.fn()} onSave={jest.fn()} />);

    await screen.findByText(/Large/);
    expect(screen.getByText(/Medium/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Product \*/i)).not.toBeInTheDocument();
    expect(screen.getAllByPlaceholderText('+5 or −2').length).toBe(2);
  });

  test('requires reason when maker-checker is on', async () => {
    useStoreSettings.mockReturnValue({
      settings: { maker_checker_enabled: true },
    });

    render(<StockAdjustmentModal product={variantProduct} onClose={jest.fn()} onSave={jest.fn()} />);
    await screen.findByText(/Large/);

    const inputs = screen.getAllByPlaceholderText('+5 or −2');
    fireEvent.change(inputs[0], { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: /submit for approval/i }));

    expect(screen.getByText('A reason is required for stock changes.')).toBeInTheDocument();
    expect(inventoryAPI.adjust).not.toHaveBeenCalled();
  });

  test('variant mode rejects non-numeric adjustment', async () => {
    render(<StockAdjustmentModal product={variantProduct} onClose={jest.fn()} onSave={jest.fn()} />);
    await screen.findByText(/Large/);

    fireEvent.change(screen.getAllByPlaceholderText('+5 or −2')[0], { target: { value: 'abc' } });
    fireEvent.click(screen.getByRole('button', { name: /apply adjustment/i }));

    expect(
      screen.getByText(/Enter a valid whole number for Large \/ Blue/i)
    ).toBeInTheDocument();
    expect(inventoryAPI.adjust).not.toHaveBeenCalled();
  });

  test('variant mode rejects when all adjustments are zero', async () => {
    render(<StockAdjustmentModal product={variantProduct} onClose={jest.fn()} onSave={jest.fn()} />);
    await screen.findByText(/Large/);

    fireEvent.click(screen.getByRole('button', { name: /apply adjustment/i }));

    expect(screen.getByText('Enter an adjustment for at least one variant.')).toBeInTheDocument();
    expect(inventoryAPI.adjust).not.toHaveBeenCalled();
  });

  test('submits multi-variant adjustments and shows success toast', async () => {
    const onSave = jest.fn();
    render(<StockAdjustmentModal product={variantProduct} onClose={jest.fn()} onSave={onSave} />);
    await screen.findByText(/Large/);

    const inputs = screen.getAllByPlaceholderText('+5 or −2');
    fireEvent.change(inputs[0], { target: { value: '2' } });
    fireEvent.change(inputs[1], { target: { value: '-1' } });
    fireEvent.click(screen.getByRole('button', { name: /apply adjustment/i }));

    await waitFor(() => {
      expect(inventoryAPI.adjust).toHaveBeenCalledTimes(2);
    });
    expect(inventoryAPI.adjust).toHaveBeenCalledWith(
      expect.objectContaining({ product_id: 5, variant_id: 41, quantity: 2 })
    );
    expect(toast.success).toHaveBeenCalledWith('Adjusted stock for 2 variant rows');
    expect(onSave).toHaveBeenCalled();
  });

  test('shows pending approval toast on 202 response', async () => {
    inventoryAPI.adjust.mockResolvedValue({ status: 202 });

    render(<StockAdjustmentModal product={variantProduct} onClose={jest.fn()} onSave={jest.fn()} />);
    await screen.findByText(/Large/);

    fireEvent.change(screen.getAllByPlaceholderText('+5 or −2')[0], { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: /apply adjustment/i }));

    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledWith(PENDING_APPROVAL_MESSAGE);
    });
  });

  test('loads products when no product prop is passed', async () => {
    productsAPI.list.mockResolvedValue({
      data: {
        results: [
          { id: 7, name: 'Widget', sku: 'W-1', stock_quantity: 4, has_variants: false },
        ],
      },
    });

    render(<StockAdjustmentModal onClose={jest.fn()} onSave={jest.fn()} />);

    await waitFor(() => {
      expect(productsAPI.list).toHaveBeenCalledWith({
        track_stock: 'true',
        is_active: 'true',
        page_size: 1000,
      });
    });
    expect(screen.getByText('Product *')).toBeInTheDocument();
  });
});
