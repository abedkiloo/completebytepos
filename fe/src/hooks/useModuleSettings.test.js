import { renderHook, waitFor, act } from '@testing-library/react';

import { useModuleSettings } from './useModuleSettings';
import { moduleSettingsAPI } from '../services/api';
import { readCachedModuleSettings } from '../utils/moduleSettingsCache';
import { resetModuleSettingsStore } from '../utils/moduleSettingsStore';

jest.mock('../services/api', () => ({
  moduleSettingsAPI: {
    get: jest.fn(),
    patch: jest.fn(),
  },
}));

describe('useModuleSettings', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('access_token', 'test-token');
    resetModuleSettingsStore();
    jest.clearAllMocks();
  });

  test('loads module settings from API and caches them', async () => {
    moduleSettingsAPI.get.mockResolvedValue({
      data: {
        module: 'products',
        settings: {
          show_status: { value: true, default_value: true, label: 'Status' },
        },
      },
    });

    const { result } = renderHook(() => useModuleSettings('products'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.settings.show_status).toBe(true);
    expect(readCachedModuleSettings('products').show_status).toBe(true);
  });

  test('dedupes in-flight fetch when multiple hooks use the same module', async () => {
    moduleSettingsAPI.get.mockResolvedValue({
      data: {
        module: 'customers',
        settings: {
          show_customer_code: { value: true, default_value: true, label: 'Code' },
        },
      },
    });

    const hookA = renderHook(() => useModuleSettings('customers'));
    const hookB = renderHook(() => useModuleSettings('customers'));

    await waitFor(() => expect(hookA.result.current.loading).toBe(false));
    await waitFor(() => expect(hookB.result.current.loading).toBe(false));

    expect(moduleSettingsAPI.get).toHaveBeenCalledTimes(1);
    expect(hookA.result.current.settings.show_customer_code).toBe(true);
    expect(hookB.result.current.settings.show_customer_code).toBe(true);
  });

  test('patch updates settings and dispatches moduleSettingsUpdated', async () => {
    moduleSettingsAPI.get.mockResolvedValue({
      data: {
        module: 'sales',
        settings: {
          show_discount: { value: true, default_value: true, label: 'Discount' },
        },
      },
    });
    moduleSettingsAPI.patch.mockResolvedValue({
      data: {
        module: 'sales',
        settings: {
          show_discount: { value: false, default_value: true, label: 'Discount' },
        },
      },
    });

    const handler = jest.fn();
    window.addEventListener('moduleSettingsUpdated', handler);

    const { result } = renderHook(() => useModuleSettings('sales'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      const patchResult = await result.current.patch({ show_discount: false });
      expect(patchResult.pending).toBe(false);
    });

    expect(result.current.settings.show_discount).toBe(false);
    expect(moduleSettingsAPI.patch).toHaveBeenCalledWith('sales', { show_discount: false });
    expect(handler).toHaveBeenCalled();

    window.removeEventListener('moduleSettingsUpdated', handler);
  });
});
