import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ProductDetailPanel from './ProductDetailPanel';
import { productsAPI, inventoryAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  productsAPI: { get: jest.fn() },
  inventoryAPI: { productHistory: jest.fn() },
}));

jest.mock('../Approvals/PendingApprovalBadges', () => () => null);

const fieldAccess = {
  catalog: true,
  pricing: true,
  cost: true,
  stock: true,
  catalogOnly: false,
};

describe('ProductDetailPanel stock history tab', () => {
  beforeEach(() => {
    productsAPI.get.mockResolvedValue({
      data: {
        id: 7,
        name: 'Widget',
        sku: 'W-1',
        track_stock: true,
        stock_quantity: 355,
        has_variants: false,
        is_active: true,
      },
    });
    inventoryAPI.productHistory.mockResolvedValue({
      data: [
        {
          id: 1,
          movement_type: 'sale',
          quantity: 45,
          stock_delta: -45,
          previous_stock: 400,
          new_stock: 355,
          change_label: 'Sold 45',
          stock_flow: 'Previous stock 400 · Sold 45 · New stock 355 · by User K',
          user_name: 'User K',
          created_at: '2026-10-06T10:00:00Z',
          reference: 'SALE-9',
        },
      ],
    });
  });

  it('shows Stock history tab for admins and loads trail', async () => {
    render(
      <ProductDetailPanel
        productId={7}
        fieldAccess={fieldAccess}
        canViewStockHistory
        onClose={() => {}}
      />
    );

    await waitFor(() => expect(screen.getByText('Widget')).toBeInTheDocument());
    expect(screen.getByTestId('product-stock-history-tab')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('product-stock-history-tab'));

    await waitFor(() =>
      expect(
        screen.getByText(/Previous stock 400 · Sold 45 · New stock 355/)
      ).toBeInTheDocument()
    );
    expect(inventoryAPI.productHistory).toHaveBeenCalledWith(7, {});
  });

  it('hides Stock history tab when not permitted', async () => {
    render(
      <ProductDetailPanel
        productId={7}
        fieldAccess={fieldAccess}
        canViewStockHistory={false}
        onClose={() => {}}
      />
    );
    await waitFor(() => expect(screen.getByText('Widget')).toBeInTheDocument());
    expect(screen.queryByTestId('product-stock-history-tab')).not.toBeInTheDocument();
  });
});

describe('ProductDetailPanel variant focus', () => {
  beforeEach(() => {
    productsAPI.get.mockResolvedValue({
      data: {
        id: 12,
        name: 'CUP HOLDER',
        track_stock: true,
        has_variants: true,
        is_active: true,
        variants: [
          {
            id: 101,
            sku: 'SKU-BLACK',
            color_name: 'BLACK',
            stock_quantity: 3,
            price: 80,
            is_active: true,
            is_low_stock: true,
          },
          {
            id: 102,
            sku: 'SKU-GOLD',
            color_name: 'GOLD',
            stock_quantity: 1332,
            price: 100,
            is_active: true,
          },
        ],
      },
    });
  });

  it('opens focused variant detail with stock when variantId is set', async () => {
    render(
      <ProductDetailPanel
        productId={12}
        variantId={101}
        fieldAccess={fieldAccess}
        onClose={() => {}}
      />
    );

    await waitFor(() => expect(screen.getByText('CUP HOLDER')).toBeInTheDocument());
    expect(screen.getByText('Variant details')).toBeInTheDocument();
    expect(screen.getByTestId('focused-variant-detail')).toBeInTheDocument();
    expect(screen.getByTestId('focused-variant-detail')).toHaveTextContent('BLACK');
    expect(screen.getByTestId('focused-variant-detail')).toHaveTextContent('3');
    expect(screen.getByTestId('variant-row-focused')).toBeInTheDocument();
  });

  it('focuses a variant when its row is clicked', async () => {
    render(
      <ProductDetailPanel productId={12} fieldAccess={fieldAccess} onClose={() => {}} />
    );

    await waitFor(() => expect(screen.getByText('CUP HOLDER')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('variant-row-102'));
    expect(screen.getByTestId('focused-variant-detail')).toHaveTextContent('GOLD');
    expect(screen.getByTestId('focused-variant-detail')).toHaveTextContent('1332');
  });
});
