import { renderHook, waitFor } from '@testing-library/react';
import { useProductVariantsEnabled } from './useProductVariantsEnabled';
import { installLocalStorageMock } from '../test-utils';

jest.mock('../utils/moduleFeatures', () => ({
  isProductVariantsEnabled: jest.fn(() => false),
}));

jest.mock('../services/api', () => ({
  modulesAPI: {
    list: jest.fn(() => Promise.resolve({ data: {} })),
  },
}));

const { isProductVariantsEnabled } = require('../utils/moduleFeatures');
const { modulesAPI } = require('../services/api');

describe('useProductVariantsEnabled', () => {
  beforeEach(() => {
    installLocalStorageMock();
    jest.clearAllMocks();
    isProductVariantsEnabled.mockReturnValue(false);
    localStorage.setItem('enabled_modules', JSON.stringify({ products: { is_enabled: true } }));
  });

  it('reads enabled flag from moduleFeatures', () => {
    isProductVariantsEnabled.mockReturnValue(true);
    const { result } = renderHook(() => useProductVariantsEnabled());
    expect(result.current).toBe(true);
  });

  it('updates when moduleSettingsUpdated fires in the same tab', async () => {
    const { normalizeModuleSettings } = require('../utils/moduleCache');
    isProductVariantsEnabled.mockReturnValueOnce(false).mockReturnValueOnce(true);
    const { result } = renderHook(() => useProductVariantsEnabled());
    expect(result.current).toBe(false);
    window.dispatchEvent(
      new CustomEvent('moduleSettingsUpdated', {
        detail: normalizeModuleSettings({
          products: {
            is_enabled: true,
            features: { product_variants: { is_enabled: true } },
          },
        }),
      })
    );
    await waitFor(() => expect(result.current).toBe(true));
  });

  it('updates when enabled_modules storage event fires', async () => {
    isProductVariantsEnabled.mockReturnValueOnce(false).mockReturnValueOnce(true);
    const { result } = renderHook(() => useProductVariantsEnabled());
    window.dispatchEvent(new StorageEvent('storage', { key: 'enabled_modules' }));
    await waitFor(() => expect(result.current).toBe(true));
  });

  it('fetches modules when cache is empty', async () => {
    localStorage.setItem('enabled_modules', '{}');
    modulesAPI.list.mockResolvedValue({ data: { products: { is_enabled: true } } });
    renderHook(() => useProductVariantsEnabled());
    await waitFor(() => expect(modulesAPI.list).toHaveBeenCalled());
  });
});
