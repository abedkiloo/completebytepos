import { renderHook } from '@testing-library/react';
import { useStoreInfo } from './useStoreInfo';
import { cacheStoreSettings, clearStoreSettingsCache } from '../../../utils/storeSettingsCache';
import { installLocalStorageMock } from '../../../test-utils';

describe('useStoreInfo', () => {
  beforeEach(() => {
    installLocalStorageMock();
    clearStoreSettingsCache();
  });

  it('uses the admin-edited store name before tenant or branch', () => {
    cacheStoreSettings({ store_name: 'Omuwenga Furniture' });
    const { result } = renderHook(() =>
      useStoreInfo({
        branch: { name: 'HQ', tenant: { name: 'Legal Tenant Ltd' } },
      })
    );
    expect(result.current.storeName).toBe('Omuwenga Furniture');
    expect(result.current.branchName).toBe('HQ');
  });

  it('falls back to Omuwenga Suppliers when nothing else is set', () => {
    const { result } = renderHook(() => useStoreInfo({}));
    expect(result.current.storeName).toBe('Omuwenga Suppliers');
  });

  it('uses tenant then branch when store settings have no name', () => {
    cacheStoreSettings({ store_name: '   ' });
    localStorage.setItem(
      'user',
      JSON.stringify({
        profile: {
          tenant: { name: 'Legal Ltd', tax_id: 'P051', phone: '0700', email: 'a@b.c' },
          branch: { name: 'HQ', address: '1 Road', city: 'Nairobi', country: 'Kenya' },
        },
      })
    );
    const { result } = renderHook(() => useStoreInfo(null));
    expect(result.current.storeName).toBe('Legal Ltd');
    expect(result.current.branchName).toBe('HQ');
    expect(result.current.address).toBe('1 Road, Nairobi, Kenya');
    expect(result.current.taxId).toBe('P051');
    expect(result.current.phone).toBe('0700');
    expect(result.current.email).toBe('a@b.c');
  });

  it('uses tenant address and kra pin when the branch has none', () => {
    cacheStoreSettings({ store_name: 'Omuwenga Suppliers', receipt_footer_text: '' });
    const { result } = renderHook(() =>
      useStoreInfo({
        branch: {
          name: 'HQ',
          tenant: {
            name: 'Legal Tenant Ltd',
            kra_pin: 'A123',
            address: 'Plot 9',
            city: 'Kisumu',
            country: 'Kenya',
            receipt_footer: 'Karibu',
          },
        },
      })
    );
    expect(result.current.storeName).toBe('Omuwenga Suppliers');
    expect(result.current.branchName).toBe('HQ');
    expect(result.current.address).toBe('Plot 9, Kisumu, Kenya');
    expect(result.current.taxId).toBe('A123');
    expect(result.current.receiptFooter).toBe('Karibu');
  });

  it('exposes receipt logo and sku flags from cached store settings', () => {
    cacheStoreSettings({
      store_name: 'Omuwenga Furniture',
      receipt_header_text: 'Welcome',
      receipt_show_logo: true,
      receipt_logo_url: '/media/logo.png',
      receipt_show_sku: true,
      receipt_footer_text: 'Thank you',
    });
    const { result } = renderHook(() => useStoreInfo({}));
    expect(result.current.receiptHeader).toBe('Welcome');
    expect(result.current.receiptLogoUrl).toBe('/media/logo.png');
    expect(result.current.showSku).toBe(true);
    expect(result.current.receiptFooter).toBe('Thank you');
  });

  it('defaults the receipt logo to the packaged plate mark', () => {
    const { result } = renderHook(() => useStoreInfo({}));
    expect(result.current.receiptLogoUrl).toBe('/logo.jpg');
    expect(result.current.tagline).toBe('Think Furniture, Think Omuwenga');
  });

  it('hides the receipt logo when the admin turns it off', () => {
    cacheStoreSettings({ receipt_show_logo: false, receipt_logo_url: '/media/logo.png' });
    const { result } = renderHook(() => useStoreInfo({}));
    expect(result.current.receiptLogoUrl).toBeNull();
  });

  it('ignores corrupt localStorage JSON', () => {
    localStorage.setItem('user', '{not-json');
    localStorage.setItem('current_branch', '{also-bad');
    const { result } = renderHook(() => useStoreInfo({}));
    expect(result.current.storeName).toBe('Omuwenga Suppliers');
  });
});
