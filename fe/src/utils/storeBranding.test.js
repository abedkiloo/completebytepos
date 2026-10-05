import {
  DEFAULT_STORE_NAME,
  DEFAULT_BRAND_LOGO,
  resolveStoreName,
  resolveReceiptLogoUrl,
  resolveStoreLogoUrl,
  loadableLogoUrl,
} from './storeBranding';

describe('storeBranding', () => {
  it('defaults to Omuwenga Suppliers', () => {
    expect(DEFAULT_STORE_NAME).toBe('Omuwenga Suppliers');
    expect(resolveStoreName()).toBe('Omuwenga Suppliers');
    expect(resolveStoreName({})).toBe('Omuwenga Suppliers');
    expect(resolveStoreName({ store_name: '  ' })).toBe('Omuwenga Suppliers');
  });

  it('prefers the admin-edited store name over tenant or branch', () => {
    expect(resolveStoreName({ store_name: '  Omuwenga Furniture  ' }, ['Tenant', 'HQ'])).toBe(
      'Omuwenga Furniture'
    );
  });

  it('falls through tenant then branch when settings have no name', () => {
    expect(resolveStoreName({}, ['Tenant Ltd', 'HQ'])).toBe('Tenant Ltd');
    expect(resolveStoreName({}, ['', 'HQ'])).toBe('HQ');
    expect(resolveStoreName(null, [null, ''])).toBe('Omuwenga Suppliers');
  });

  it('uses the packaged plate logo on receipts unless an upload is set', () => {
    expect(resolveReceiptLogoUrl()).toBe(DEFAULT_BRAND_LOGO);
    expect(resolveReceiptLogoUrl({})).toBe(DEFAULT_BRAND_LOGO);
    expect(resolveReceiptLogoUrl({ receipt_logo_url: '  /media/custom.png  ' })).toBe(
      '/media/custom.png'
    );
    expect(resolveReceiptLogoUrl({ receipt_show_logo: false })).toBeNull();
  });

  it('keeps the store logo on documents even when receipts hide it', () => {
    expect(resolveStoreLogoUrl({ receipt_show_logo: false, receipt_logo_url: '/media/x.png' })).toBe(
      '/media/x.png'
    );
    expect(resolveStoreLogoUrl({ receipt_show_logo: false })).toBe(DEFAULT_BRAND_LOGO);
  });

  describe('loadableLogoUrl', () => {
    const RealImage = global.Image;
    afterEach(() => {
      global.Image = RealImage;
    });

    function stubImage(outcome) {
      global.Image = class {
        set src(value) {
          this._src = value;
          if (outcome === 'load') setTimeout(() => this.onload());
          if (outcome === 'error') setTimeout(() => this.onerror());
        }
      };
    }

    it('keeps an uploaded logo that loads', async () => {
      stubImage('load');
      await expect(loadableLogoUrl('/media/receipt/brand.png')).resolves.toBe(
        '/media/receipt/brand.png'
      );
    });

    it('falls back to the packaged logo when the upload is broken', async () => {
      stubImage('error');
      await expect(loadableLogoUrl('http://backend:8000/media/x.png')).resolves.toBe(
        DEFAULT_BRAND_LOGO
      );
    });

    it('falls back when the upload never answers', async () => {
      stubImage('hang');
      await expect(loadableLogoUrl('/media/slow.png', { timeoutMs: 5 })).resolves.toBe(
        DEFAULT_BRAND_LOGO
      );
    });

    it('passes through the packaged logo and a hidden logo untouched', async () => {
      await expect(loadableLogoUrl(DEFAULT_BRAND_LOGO)).resolves.toBe(DEFAULT_BRAND_LOGO);
      await expect(loadableLogoUrl(null)).resolves.toBeNull();
    });
  });
});
