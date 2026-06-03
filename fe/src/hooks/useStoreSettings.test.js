import { renderHook, act, waitFor } from '@testing-library/react';
import { useStoreSettings } from './useStoreSettings';
import { installLocalStorageMock } from '../test-utils';

jest.mock('../services/api', () => ({
  storeSettingsAPI: {
    get: jest.fn(),
  },
}));

const { storeSettingsAPI } = require('../services/api');

describe('useStoreSettings', () => {
  beforeEach(() => {
    installLocalStorageMock();
    localStorage.setItem('access_token', 'tok');
    jest.clearAllMocks();
  });

  it('fetches and caches settings on mount', async () => {
    storeSettingsAPI.get.mockResolvedValue({
      data: { allow_sales_add_products: true },
    });
    const { result } = renderHook(() => useStoreSettings());
    await waitFor(() => {
      expect(result.current.settings.allow_sales_add_products).toBe(true);
    });
  });

  it('skips fetch when not logged in', () => {
    localStorage.removeItem('access_token');
    renderHook(() => useStoreSettings());
    expect(storeSettingsAPI.get).not.toHaveBeenCalled();
  });

  it('listens for storeSettingsUpdated events', async () => {
    storeSettingsAPI.get.mockResolvedValue({ data: {} });
    const { result } = renderHook(() => useStoreSettings());
    await waitFor(() => expect(storeSettingsAPI.get).toHaveBeenCalled());
    act(() => {
      window.dispatchEvent(
        new CustomEvent('storeSettingsUpdated', {
          detail: { allow_sales_add_products: true },
        })
      );
    });
    expect(result.current.settings.allow_sales_add_products).toBe(true);
  });

  it('refresh reloads from API', async () => {
    storeSettingsAPI.get.mockResolvedValue({ data: { receipt_show_sku: true } });
    const { result } = renderHook(() => useStoreSettings());
    await waitFor(() => expect(result.current.settings.receipt_show_sku).toBe(true));
    storeSettingsAPI.get.mockResolvedValue({ data: { receipt_show_sku: false } });
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.settings.receipt_show_sku).toBe(false);
  });

  it('applyLocal patches settings', async () => {
    storeSettingsAPI.get.mockResolvedValue({ data: { receipt_show_sku: false } });
    const { result } = renderHook(() => useStoreSettings());
    await waitFor(() => expect(result.current.settings).toBeDefined());
    act(() => {
      result.current.applyLocal({ receipt_show_sku: true });
    });
    expect(result.current.settings.receipt_show_sku).toBe(true);
  });
});
