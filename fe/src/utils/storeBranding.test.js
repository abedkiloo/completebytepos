import { DEFAULT_STORE_NAME, resolveStoreName } from './storeBranding';

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
});
