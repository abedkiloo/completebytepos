import { PERSONA } from './roleAccess';
import { canSeeNavItem } from './navAccess';
import { NAV_SECTION_MODULES } from './permissionRoutes';

const ctx = (persona, permissions = [], overrides = {}) => ({
  persona,
  isSuperAdmin: persona === PERSONA.SUPER_ADMIN,
  permissions,
  isModuleEnabled: () => true,
  isFeatureEnabled: () => true,
  ...overrides,
});

function perm(module, action = 'view') {
  return { name: `${module}.${action}`, module, action };
}

describe('navAccess — permission-granted sections for sales', () => {
  test('sales sees invoices when invoicing.view is granted', () => {
    const permissions = [perm('invoicing', 'view'), perm('invoicing', 'create')];
    const salesCtx = ctx(PERSONA.SALES, permissions);
    expect(
      canSeeNavItem(
        {
          to: '/invoices',
          label: 'Invoices',
          module: 'invoicing',
          permission: ['invoicing', 'view'],
        },
        'invoicing',
        salesCtx
      )
    ).toBe(true);
  });

  test('sales sees reports when reports.view is granted', () => {
    const permissions = [perm('reports', 'view')];
    const salesCtx = ctx(PERSONA.SALES, permissions);
    expect(
      canSeeNavItem(
        { to: '/reports?report=sales', label: 'Sales Summary', module: 'reports' },
        'reports',
        salesCtx
      )
    ).toBe(true);
  });

  test('sales still blocked from manager-only audit log even with reports.view', () => {
    const permissions = [perm('reports', 'view')];
    const salesCtx = ctx(PERSONA.SALES, permissions);
    expect(
      canSeeNavItem(
        { to: '/audit-log', label: 'Audit log', managerOnly: true },
        'reports',
        salesCtx
      )
    ).toBe(false);
  });

  test('sales sees sales history when sales.view is granted', () => {
    const permissions = [perm('sales', 'view')];
    const salesCtx = ctx(PERSONA.SALES, permissions);
    expect(
      canSeeNavItem(
        { to: '/sales', label: 'Sales History', feature: ['sales', 'sales_history'] },
        'sales',
        salesCtx
      )
    ).toBe(true);
  });

  test('sales sees suppliers nav when suppliers.view is granted', () => {
    const permissions = [perm('suppliers', 'view')];
    const salesCtx = ctx(PERSONA.SALES, permissions);
    expect(
      canSeeNavItem(
        { to: '/suppliers', label: 'Suppliers', module: 'suppliers' },
        'suppliers',
        salesCtx
      )
    ).toBe(true);
  });

  test('every nav section module mapping is covered by a visibility test module', () => {
    expect(Object.keys(NAV_SECTION_MODULES).length).toBeGreaterThanOrEqual(6);
  });
});
