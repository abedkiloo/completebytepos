import {
  applyVariantDraftsAfterProductSave,
  variantDraftsApplyNeedsReason,
} from './variantDrafts';
import { variantsAPI } from '../services/api';

jest.mock('../services/api', () => ({
  variantsAPI: {
    getByProduct: jest.fn(),
    update: jest.fn(),
  },
}));

describe('variantDraftsApplyNeedsReason', () => {
  test('returns false when draft matches new-variant defaults', () => {
    expect(
      variantDraftsApplyNeedsReason(
        { '1-2': { price: '', stock_quantity: '', is_active: true } },
        ['1-2'],
        {
          product: { price: '100', mrp: '120', cost: '50' },
          sizes: [{ id: 1, name: 'L' }],
          colors: [{ id: 2, name: 'Blue' }],
        }
      )
    ).toBe(false);
  });

  test('returns true when draft price differs from product default', () => {
    expect(
      variantDraftsApplyNeedsReason(
        { '1-2': { price: '80', is_active: true } },
        ['1-2'],
        {
          product: { price: '100' },
          sizes: [{ id: 1, name: 'L' }],
          colors: [{ id: 2, name: 'Blue' }],
        }
      )
    ).toBe(true);
  });

  test('returns true when existing variant price changes', () => {
    expect(
      variantDraftsApplyNeedsReason(
        { '1-2': { price: '90' } },
        ['1-2'],
        {
          product: { price: '100' },
          variants: [{ id: 5, size: 1, color: 2, price: '100', stock_quantity: 0, is_active: true }],
          sizes: [{ id: 1, name: 'L' }],
          colors: [{ id: 2, name: 'Blue' }],
        }
      )
    ).toBe(true);
  });
});

describe('applyVariantDraftsAfterProductSave', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('returns zero applied when no drafts', async () => {
    const result = await applyVariantDraftsAfterProductSave(1, {});
    expect(result).toEqual({ applied: 0 });
    expect(variantsAPI.getByProduct).not.toHaveBeenCalled();
  });

  test('updates matching variants with PATCH payload for changed fields only', async () => {
    variantsAPI.getByProduct.mockResolvedValue({
      data: {
        results: [
          {
            id: 10,
            product: 5,
            size: 1,
            color: 2,
            sku: 'SKU-A',
            price: '50.00',
            stock_quantity: 0,
            is_active: true,
          },
          {
            id: 11,
            product: 5,
            size: 2,
            color: 2,
            sku: 'SKU-B',
            price: '60.00',
            stock_quantity: 1,
            is_active: true,
          },
        ],
      },
    });
    variantsAPI.update.mockResolvedValue({ status: 200 });

    const result = await applyVariantDraftsAfterProductSave(5, {
      '1-2': { price: '55.00', stock_quantity: '4', is_active: true },
    });

    expect(result).toEqual({ applied: 1 });
    expect(variantsAPI.update).toHaveBeenCalledTimes(1);
    expect(variantsAPI.update).toHaveBeenCalledWith(10, {
      price: '55.00',
      selling_price: '55.00',
      stock_quantity: 4,
    });
  });

  test('skips PATCH when draft leaves defaults unchanged', async () => {
    variantsAPI.getByProduct.mockResolvedValue({
      data: {
        results: [
          {
            id: 10,
            product: 5,
            size: 1,
            color: 2,
            sku: 'SKU-A',
            price: '50.00',
            stock_quantity: 0,
            is_active: true,
          },
        ],
      },
    });

    const result = await applyVariantDraftsAfterProductSave(5, {
      '1-2': { price: '', stock_quantity: '', is_active: true },
    });

    expect(result).toEqual({ applied: 0 });
    expect(variantsAPI.update).not.toHaveBeenCalled();
  });

  test('includeStock false strips stock from payload on edit', async () => {
    variantsAPI.getByProduct.mockResolvedValue({
      data: {
        results: [
          {
            id: 10,
            product: 5,
            size: 1,
            color: 2,
            sku: 'SKU-A',
            price: '50.00',
            stock_quantity: 0,
            is_active: true,
          },
        ],
      },
    });
    variantsAPI.update.mockResolvedValue({ status: 200 });

    const result = await applyVariantDraftsAfterProductSave(
      5,
      { '1-2': { price: '55.00', stock_quantity: '4', mrp: '70.00' } },
      { includeStock: false }
    );

    expect(result).toEqual({ applied: 1 });
    expect(variantsAPI.update).toHaveBeenCalledWith(10, {
      price: '55.00',
      selling_price: '55.00',
      mrp: '70.00',
    });
  });

  test('forwards maker-checker reason on variant PATCH', async () => {
    variantsAPI.getByProduct.mockResolvedValue({
      data: {
        results: [
          {
            id: 10,
            product: 5,
            size: 1,
            color: 2,
            price: '50.00',
            stock_quantity: 0,
            is_active: true,
          },
        ],
      },
    });
    variantsAPI.update.mockResolvedValue({ status: 200 });

    await applyVariantDraftsAfterProductSave(
      5,
      { '1-2': { price: '55.00' } },
      { reason: 'New supplier price list' }
    );

    expect(variantsAPI.update).toHaveBeenCalledWith(10, {
      price: '55.00',
      selling_price: '55.00',
      reason: 'New supplier price list',
    });
  });

  test('returns zero applied when no matching keys', async () => {
    variantsAPI.getByProduct.mockResolvedValue({
      data: {
        results: [
          {
            id: 10,
            product: 5,
            size: 1,
            color: 2,
            sku: 'SKU-A',
            price: '50.00',
            stock_quantity: 0,
            is_active: true,
          },
        ],
      },
    });

    const result = await applyVariantDraftsAfterProductSave(5, {
      '9-9': { price: '55.00' },
    });
    expect(result).toEqual({ applied: 0 });
    expect(variantsAPI.update).not.toHaveBeenCalled();
  });

  test('returns zero applied without product id', async () => {
    const result = await applyVariantDraftsAfterProductSave(null, {
      '1-2': { price: '55.00' },
    });
    expect(result).toEqual({ applied: 0 });
    expect(variantsAPI.getByProduct).not.toHaveBeenCalled();
  });
});
