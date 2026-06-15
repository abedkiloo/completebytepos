import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { installLocalStorageMock } from '../../test-utils';

jest.mock(
  'react-router-dom',
  () => ({
    Link: ({ children, ...props }) => <a {...props}>{children}</a>,
  }),
  { virtual: true }
);

jest.mock('../../utils/moduleFeatures', () => ({
  ...jest.requireActual('../../utils/moduleFeatures'),
  isProductVariantsEnabled: jest.fn(() => true),
}));

jest.mock('../../hooks/useProductVariantsEnabled', () => ({
  __esModule: true,
  useProductVariantsEnabled: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  productsAPI: {
    create: jest.fn(),
    update: jest.fn(),
    units: {
      options: jest.fn().mockResolvedValue({ data: { results: [] } }),
    },
  },
  categoriesAPI: { list: jest.fn() },
  sizesAPI: { list: jest.fn() },
  colorsAPI: { list: jest.fn() },
  suppliersAPI: { list: jest.fn() },
  modulesAPI: {
    list: jest.fn().mockResolvedValue({ data: {} }),
  },
}));

jest.mock('../../utils/variantDrafts', () => ({
  applyVariantDraftsAfterProductSave: jest.fn(),
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

jest.mock('../../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (value) => value,
}));

jest.mock('../Shared/SearchableSelect', () => (props) => (
  <select
    data-testid={`select-${props.name}`}
    name={props.name}
    value={props.value}
    onChange={props.onChange}
  >
    <option value="">—</option>
    {(props.options || []).map((opt) => (
      <option key={opt.id} value={String(opt.id)}>
        {opt.name}
      </option>
    ))}
  </select>
));

jest.mock('./CategoryForm', () => () => null);
jest.mock('../Suppliers/SupplierForm', () => () => null);
jest.mock('../Approvals/PendingApprovalBadges', () => () => null);
jest.mock('../Approvals/ChangeReasonField', () => (props) => (
  <textarea
    aria-label="change-reason"
    value={props.value}
    onChange={(e) => props.onChange(e.target.value)}
  />
));
jest.mock('./VariantDraftSummary', () => () => null);

let mockVariantSetup = {
  keys: ['1-10'],
  drafts: { '1-10': { price: '100', stock_quantity: '5', mrp: '120' } },
};

jest.mock('./ProductVariantsPanel', () => {
  const React = require('react');
  return function MockProductVariantsPanel({ onDraftsChange, onCombinationKeysChange }) {
    React.useEffect(() => {
      onCombinationKeysChange?.(mockVariantSetup.keys);
      onDraftsChange?.(mockVariantSetup.drafts);
    }, [onDraftsChange, onCombinationKeysChange]);
    return <div data-testid="variants-panel" />;
  };
});

import { productsAPI, categoriesAPI, sizesAPI, colorsAPI, suppliersAPI } from '../../services/api';
import { applyVariantDraftsAfterProductSave } from '../../utils/variantDrafts';
import { toast } from '../../utils/toast';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { useProductVariantsEnabled } from '../../hooks/useProductVariantsEnabled';
import ProductForm from './ProductForm';

const categories = [{ id: 1, name: 'Apparel', parent: null }];

describe('ProductForm integration', () => {
  beforeEach(() => {
    installLocalStorageMock();
    localStorage.setItem(
      'enabled_modules',
      JSON.stringify({
        products: {
          is_enabled: true,
          features: { product_variants: { is_enabled: true } },
        },
      })
    );

    mockVariantSetup = {
      keys: ['1-10'],
      drafts: { '1-10': { price: '100', stock_quantity: '5', mrp: '120' } },
    };
    useStoreSettings.mockReturnValue({
      settings: { maker_checker_enabled: false },
    });
    useProductVariantsEnabled.mockReturnValue(true);
    productsAPI.create.mockClear();
    productsAPI.update.mockClear();
    applyVariantDraftsAfterProductSave.mockClear();
    toast.warning.mockClear();
    toast.success.mockClear();
    toast.error.mockClear();
    categoriesAPI.list.mockResolvedValue({ data: categories });
    sizesAPI.list.mockResolvedValue({ data: [{ id: 1, name: 'Large', code: 'L' }] });
    colorsAPI.list.mockResolvedValue({ data: [{ id: 10, name: 'Blue' }] });
    suppliersAPI.list.mockResolvedValue({ data: [] });
    productsAPI.create.mockResolvedValue({ status: 201, data: { id: 99 } });
    productsAPI.update.mockResolvedValue({ status: 200, data: { id: 1, name: 'Updated' } });
    applyVariantDraftsAfterProductSave.mockResolvedValue({ applied: 1 });
  });

  const fillNameAndEnableVariants = async () => {
    fireEvent.change(document.querySelector('input[name="name"]'), {
      target: { value: 'Variant Tee', name: 'name' },
    });
    await waitFor(() => {
      expect(document.querySelector('input[name="has_variants"]')).toBeTruthy();
    });
    fireEvent.click(document.querySelector('input[name="has_variants"]'));
    await waitFor(() => {
      expect(screen.getByTestId('variants-panel')).toBeInTheDocument();
    });
  };

  test('create with variants applies drafts including stock', async () => {
    const onSave = jest.fn();
    render(
      <ProductForm categories={categories} onClose={jest.fn()} onSave={onSave} />
    );

    await fillNameAndEnableVariants();
    fireEvent.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => {
      expect(productsAPI.create).toHaveBeenCalled();
    });

    expect(applyVariantDraftsAfterProductSave).toHaveBeenCalledWith(
      99,
      mockVariantSetup.drafts,
      { includeStock: true }
    );

    await waitFor(() => {
      expect(onSave).toHaveBeenCalled();
    }, { timeout: 1000 });
  });

  test('edit with variants applies drafts without stock', async () => {
    const product = {
      id: 1,
      name: 'Variant Tee',
      category: 1,
      has_variants: true,
      available_sizes: [1],
      available_colors: [10],
      price: '100',
      selling_price: '100',
      is_active: true,
      track_stock: true,
    };

    render(
      <ProductForm
        product={product}
        categories={categories}
        onClose={jest.fn()}
        onSave={jest.fn()}
      />
    );

    await screen.findByTestId('variants-panel');
    fireEvent.click(screen.getByRole('button', { name: /update/i }));

    await waitFor(() => {
      expect(productsAPI.update).toHaveBeenCalled();
    });

    expect(applyVariantDraftsAfterProductSave).toHaveBeenCalledWith(
      1,
      mockVariantSetup.drafts,
      { includeStock: false }
    );
  });

  test('edit simple product does not show stock field', async () => {
    const product = {
      id: 3,
      name: 'Simple Widget',
      category: 1,
      has_variants: false,
      price: '50',
      selling_price: '50',
      stock_quantity: 12,
      is_active: true,
      track_stock: true,
    };

    render(
      <ProductForm
        product={product}
        categories={categories}
        onClose={jest.fn()}
        onSave={jest.fn()}
      />
    );

    expect(screen.queryByLabelText(/Stock on hand/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Opening stock/i)).not.toBeInTheDocument();
  });

  test('blocks save when variants enabled but no combinations', async () => {
    mockVariantSetup = { keys: [], drafts: {} };

    render(<ProductForm categories={categories} onClose={jest.fn()} onSave={jest.fn()} />);

    await fillNameAndEnableVariants();
    fireEvent.click(screen.getByRole('button', { name: /create/i }));

    expect(toast.warning).toHaveBeenCalledWith(
      'Add at least one variant combination (size and/or color) before saving.'
    );
    expect(productsAPI.create).not.toHaveBeenCalled();
  });

  test('requires reason for sensitive edit when maker-checker is on', async () => {
    useStoreSettings.mockReturnValue({
      settings: { maker_checker_enabled: true },
    });

    const product = {
      id: 2,
      name: 'Simple Item',
      category: 1,
      has_variants: false,
      price: '100',
      selling_price: '100',
      mrp: '200',
      cost: '40',
      is_active: true,
      track_stock: true,
    };

    render(
      <ProductForm
        product={product}
        categories={categories}
        onClose={jest.fn()}
        onSave={jest.fn()}
      />
    );

    const priceInput = document.querySelector('input[name="selling_price"]');
    fireEvent.change(priceInput, { target: { value: '150', name: 'selling_price' } });
    await waitFor(() => {
      expect(priceInput.value).toBe('150');
    });
    fireEvent.click(screen.getByRole('button', { name: /update/i }));

    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalled();
    });
    expect(toast.warning.mock.calls[0][0]).toMatch(/reason below/i);
    expect(productsAPI.update).not.toHaveBeenCalled();
  });

  test('warns when variant draft apply fails but still completes save', async () => {
    applyVariantDraftsAfterProductSave.mockRejectedValue(new Error('variant API down'));
    const onSave = jest.fn();

    render(
      <ProductForm categories={categories} onClose={jest.fn()} onSave={onSave} />
    );

    await fillNameAndEnableVariants();
    fireEvent.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => {
      expect(productsAPI.create).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledWith(
        'Product saved, but some variant price or stock values could not be applied. variant API down'
      );
    });

    await waitFor(() => {
      expect(onSave).toHaveBeenCalled();
    }, { timeout: 1000 });
  });
});
