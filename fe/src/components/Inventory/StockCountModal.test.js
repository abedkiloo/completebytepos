import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import StockCountModal from './StockCountModal';
import { productsAPI, variantsAPI } from '../../services/api';
import { useStoreSettings } from '../../hooks/useStoreSettings';

jest.mock('../../services/api', () => ({
  productsAPI: { list: jest.fn(), update: jest.fn() },
  variantsAPI: { getByProduct: jest.fn(), update: jest.fn() },
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: jest.fn(() => ({
    settings: { maker_checker_enabled: false },
  })),
}));

jest.mock('../Approvals/ChangeReasonField', () => () => null);

const simpleProduct = {
  id: 7,
  name: 'Widget',
  has_variants: false,
  stock_quantity: 12,
  track_stock: true,
};

const variantProduct = {
  id: 5,
  name: 'Bottled Water',
  has_variants: true,
  stock_quantity: 50,
  track_stock: true,
};

describe('StockCountModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useStoreSettings.mockReturnValue({
      settings: { maker_checker_enabled: false },
    });
    productsAPI.update.mockResolvedValue({ status: 200 });
    variantsAPI.update.mockResolvedValue({ status: 200 });
  });

  test('pre-selected simple product shows stock on hand prefilled', async () => {
    const onSave = jest.fn();
    render(<StockCountModal product={simpleProduct} onClose={jest.fn()} onSave={onSave} />);

    expect(screen.getByRole('heading', { name: /Stock count/i })).toBeInTheDocument();
    expect(screen.getByText(/System shows: 12/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Stock on hand/i)).toHaveValue('12');

    fireEvent.change(screen.getByLabelText(/Stock on hand/i), { target: { value: '20' } });
    fireEvent.click(screen.getByRole('button', { name: /save stock count/i }));

    await waitFor(() => {
      expect(productsAPI.update).toHaveBeenCalledWith(7, { stock_quantity: 20 });
    });
    expect(variantsAPI.getByProduct).not.toHaveBeenCalled();
    expect(onSave).toHaveBeenCalled();
  });

  test('global variant product loads all variants and saves changed rows', async () => {
    variantsAPI.getByProduct.mockResolvedValue({
      data: {
        results: [
          {
            id: 41,
            product: 5,
            size_name: 'Large',
            color_name: 'Blue',
            stock_quantity: 40,
          },
          {
            id: 42,
            product: 5,
            size_name: 'Small',
            color_name: 'Red',
            stock_quantity: 10,
          },
        ],
      },
    });

    render(
      <StockCountModal product={variantProduct} onClose={jest.fn()} onSave={jest.fn()} />
    );

    await screen.findByText(/Large/);
    expect(screen.getByText(/Small/)).toBeInTheDocument();
    expect(variantsAPI.getByProduct).toHaveBeenCalledWith(5);

    const input = screen.getByLabelText(/Stock on hand for Large \/ Blue/i);
    fireEvent.change(input, { target: { value: '35' } });
    fireEvent.click(screen.getByRole('button', { name: /save stock count/i }));

    await waitFor(() => {
      expect(variantsAPI.update).toHaveBeenCalledWith(41, { stock_quantity: 35 });
      expect(variantsAPI.update).toHaveBeenCalledTimes(1);
    });
  });

  test('single variant row only updates that variant without loading all', async () => {
    const variant = {
      id: 42,
      product: 5,
      size_name: 'Small',
      color_name: 'Red',
      stock_quantity: 10,
    };

    render(
      <StockCountModal
        product={variantProduct}
        variant={variant}
        onClose={jest.fn()}
        onSave={jest.fn()}
      />
    );

    expect(variantsAPI.getByProduct).not.toHaveBeenCalled();
    expect(screen.queryByText(/Large \/ Blue/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Stock on hand for Small \/ Red/i)).toHaveValue('10');

    fireEvent.change(screen.getByLabelText(/Stock on hand for Small \/ Red/i), {
      target: { value: '15' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save stock count/i }));

    await waitFor(() => {
      expect(variantsAPI.update).toHaveBeenCalledWith(42, { stock_quantity: 15 });
      expect(variantsAPI.update).toHaveBeenCalledTimes(1);
    });
  });

  test('single variant unchanged count shows validation error', async () => {
    const variant = {
      id: 42,
      size_name: 'Small',
      color_name: 'Red',
      stock_quantity: 10,
    };

    render(
      <StockCountModal
        product={variantProduct}
        variant={variant}
        onClose={jest.fn()}
        onSave={jest.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /save stock count/i }));

    await waitFor(() => {
      expect(screen.getByText(/Change at least one variant count/i)).toBeInTheDocument();
    });
    expect(variantsAPI.update).not.toHaveBeenCalled();
  });

  test('maker-checker requires reason for stock changes', async () => {
    useStoreSettings.mockReturnValue({
      settings: { maker_checker_enabled: true },
    });

    render(<StockCountModal product={simpleProduct} onClose={jest.fn()} onSave={jest.fn()} />);

    fireEvent.change(screen.getByLabelText(/Stock on hand/i), { target: { value: '20' } });
    fireEvent.click(screen.getByRole('button', { name: /submit for approval/i }));

    await waitFor(() => {
      expect(screen.getByText(/reason is required/i)).toBeInTheDocument();
    });
    expect(productsAPI.update).not.toHaveBeenCalled();
  });
});
