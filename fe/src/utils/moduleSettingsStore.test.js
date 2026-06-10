import { moduleSettingsAPI } from '../services/api';
import {
  applyModuleSettingsPayload,
  patchModuleSettings,
  resetModuleSettingsStore,
  getModuleSettingsSnapshot,
} from './moduleSettingsStore';
import { readCachedModuleSettings } from './moduleSettingsCache';

jest.mock('../services/api', () => ({
  moduleSettingsAPI: {
    get: jest.fn(),
    patch: jest.fn(),
  },
}));

describe('moduleSettingsStore', () => {
  beforeEach(() => {
    localStorage.clear();
    resetModuleSettingsStore();
    jest.clearAllMocks();
  });

  test('applyModuleSettingsPayload flattens and caches settings', () => {
    const flat = applyModuleSettingsPayload('products', {
      module: 'products',
      settings: {
        show_status: { value: false, default_value: true, label: 'Status' },
      },
    });
    expect(flat.show_status).toBe(false);
    expect(readCachedModuleSettings('products').show_status).toBe(false);
  });

  test('patchModuleSettings applies server payload on 200', async () => {
    applyModuleSettingsPayload('products', {
      module: 'products',
      settings: {
        allow_sales_edit_cost: { value: false, default_value: false, label: 'Cost' },
      },
    });
    moduleSettingsAPI.patch.mockResolvedValue({
      status: 200,
      data: {
        module: 'products',
        settings: {
          allow_sales_edit_cost: { value: true, default_value: false, label: 'Cost' },
        },
      },
    });

    const result = await patchModuleSettings('products', { allow_sales_edit_cost: true });

    expect(result.pending).toBe(false);
    expect(result.settings.allow_sales_edit_cost).toBe(true);
    expect(getModuleSettingsSnapshot('products').settings.allow_sales_edit_cost).toBe(true);
  });

  test('patchModuleSettings keeps optimistic toggle on 202 pending approval', async () => {
    applyModuleSettingsPayload('products', {
      module: 'products',
      settings: {
        allow_sales_edit_cost: { value: false, default_value: false, label: 'Cost' },
      },
    });
    moduleSettingsAPI.patch.mockResolvedValue({
      status: 202,
      data: { message: 'Change submitted for approval, not yet active.' },
    });

    const result = await patchModuleSettings(
      'products',
      { allow_sales_edit_cost: true },
      { reason: 'Stocktake' }
    );

    expect(moduleSettingsAPI.patch).toHaveBeenCalledWith('products', {
      allow_sales_edit_cost: true,
      reason: 'Stocktake',
    });
    expect(result.pending).toBe(true);
    expect(result.settings.allow_sales_edit_cost).toBe(true);
    expect(readCachedModuleSettings('products').allow_sales_edit_cost).toBe(true);
  });

  test('patchModuleSettings rejects axios 400 and preserves cached settings', async () => {
    applyModuleSettingsPayload('products', {
      module: 'products',
      settings: {
        allow_sales_edit_cost: { value: false, default_value: false, label: 'Cost' },
      },
    });
    moduleSettingsAPI.patch.mockRejectedValue({
      response: {
        status: 400,
        data: { reason: ['A reason is required for module settings changes.'] },
      },
    });

    await expect(
      patchModuleSettings('products', { allow_sales_edit_cost: true })
    ).rejects.toMatchObject({
      response: { status: 400 },
    });

    expect(getModuleSettingsSnapshot('products').settings.allow_sales_edit_cost).toBe(false);
    expect(readCachedModuleSettings('products').allow_sales_edit_cost).toBe(false);
  });

  test('patchModuleSettings does not treat resolved 400 as success', async () => {
    applyModuleSettingsPayload('products', {
      module: 'products',
      settings: {
        allow_sales_edit_cost: { value: false, default_value: false, label: 'Cost' },
      },
    });
    moduleSettingsAPI.patch.mockResolvedValue({
      status: 400,
      data: { reason: ['A reason is required for module settings changes.'] },
    });

    await expect(
      patchModuleSettings('products', { allow_sales_edit_cost: true })
    ).rejects.toThrow('Module settings patch failed');

    expect(getModuleSettingsSnapshot('products').settings.allow_sales_edit_cost).toBe(false);
    expect(readCachedModuleSettings('products').allow_sales_edit_cost).toBe(false);
  });
});
