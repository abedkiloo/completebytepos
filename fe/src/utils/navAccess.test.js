import {
  PERSONA,
  canAccessRoute,
} from './roleAccess';
import {
  canSeeNavItem,
  getPersonaFromStorage,
  VISIBLE_SECTIONS,
} from './navAccess';

const ctx = (persona, overrides = {}) => ({
  persona,
  isSuperAdmin: persona === PERSONA.SUPER_ADMIN,
  permissions: [],
  isModuleEnabled: () => true,
  isFeatureEnabled: () => true,
  ...overrides,
});

describe('navAccess', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('sales persona only sees allowed sales paths', () => {
    expect(canAccessRoute(PERSONA.SALES, '/pos')).toBe(true);
    expect(canAccessRoute(PERSONA.SALES, '/pos/billing')).toBe(true);
    expect(canAccessRoute(PERSONA.SALES, '/customers')).toBe(true);
    expect(canAccessRoute(PERSONA.SALES, '/reports')).toBe(false);
    expect(canAccessRoute(PERSONA.SALES, '/users')).toBe(false);
  });

  test('sales nav hides normal sale and sales history', () => {
    const salesCtx = ctx(PERSONA.SALES);
    expect(
      canSeeNavItem(
        { to: '/pos', label: 'POS' },
        'sales',
        salesCtx
      )
    ).toBe(true);
    expect(
      canSeeNavItem(
        { to: '/pos/billing', label: 'Billing' },
        'sales',
        salesCtx
      )
    ).toBe(true);
    expect(
      canSeeNavItem(
        { to: '/normal-sale', label: 'Normal' },
        'sales',
        salesCtx
      )
    ).toBe(false);
    expect(
      canSeeNavItem(
        { to: '/sales', label: 'History' },
        'sales',
        salesCtx
      )
    ).toBe(false);
  });

  test('manager sees reports section but not module settings', () => {
    const mgr = ctx(PERSONA.MANAGER);
    expect(VISIBLE_SECTIONS[PERSONA.MANAGER]).toContain('reports');
    expect(
      canSeeNavItem(
        { to: '/module-settings', label: 'Modules', requireSuperAdmin: true },
        'settings',
        mgr
      )
    ).toBe(false);
  });

  test('super admin sees module settings link', () => {
    const admin = ctx(PERSONA.SUPER_ADMIN);
    expect(
      canSeeNavItem(
        { to: '/module-settings', label: 'Modules', requireSuperAdmin: true },
        'settings',
        admin
      )
    ).toBe(true);
  });

  test('feature flag can hide nav item', () => {
    const mgr = ctx(PERSONA.MANAGER, {
      isFeatureEnabled: (mod, feat) => !(mod === 'sales' && feat === 'pos'),
    });
    expect(
      canSeeNavItem(
        { to: '/pos', label: 'POS', feature: ['sales', 'pos'] },
        'sales',
        mgr
      )
    ).toBe(false);
  });

  test('getPersonaFromStorage reads profile', () => {
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'manager', custom_role: { name: 'Manager' } })
    );
    expect(getPersonaFromStorage()).toBe(PERSONA.MANAGER);
  });
});
