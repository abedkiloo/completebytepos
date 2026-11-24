/**
 * Field module mental model: Field orders (customer orders from the road)
 * vs Field loads (stock bag). Kept as its own sidebar section for navigation.
 */
jest.mock('../../services/api', () => ({
  modulesAPI: {},
  storeSettingsAPI: {},
}));

import { NAV_SECTIONS } from './Layout';
import { PERSONA } from '../../utils/roleAccess';
import { canSeeNavItem, VISIBLE_SECTIONS } from '../../utils/navAccess';
import {
  NAV_SECTION_MODULES,
  routePermissionGateForPath,
} from '../../utils/permissionRoutes';

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

const fieldSection = () => NAV_SECTIONS.find((s) => s.id === 'field');
const salesSection = () => NAV_SECTIONS.find((s) => s.id === 'sales');

describe('Field nav mental model', () => {
  test('unit: Field is its own section with Field orders then Field loads', () => {
    const field = fieldSection();
    expect(field).toBeTruthy();
    expect(field.label).toBe('Field');
    expect(field.items.map((i) => i.label)).toEqual(['Field orders', 'Field loads']);
    expect(field.items.map((i) => i.to)).toEqual(['/sales/field', '/sales/field-loads']);
  });

  test('corrected: Sales no longer lists field peers under the shop checkout tools', () => {
    const salesLabels = salesSection().items.map((i) => i.label);
    expect(salesLabels).not.toContain('Field sales');
    expect(salesLabels).not.toContain('Field orders');
    expect(salesLabels).not.toContain('Field loads');
  });

  test('module: field section maps to dispatch + agents for permission grants', () => {
    expect(NAV_SECTION_MODULES.field).toEqual(['dispatch', 'agents']);
    expect(VISIBLE_SECTIONS[PERSONA.MANAGER]).toContain('field');
    expect(VISIBLE_SECTIONS[PERSONA.SALES]).toContain('field');
  });

  test('security: Field orders needs dispatch.view; Field loads needs agents.field_load', () => {
    const orders = fieldSection().items[0];
    const loads = fieldSection().items[1];
    expect(canSeeNavItem(orders, 'field', ctx(PERSONA.MANAGER, []))).toBe(false);
    expect(
      canSeeNavItem(orders, 'field', ctx(PERSONA.MANAGER, [perm('dispatch', 'view')]))
    ).toBe(true);
    expect(canSeeNavItem(loads, 'field', ctx(PERSONA.MANAGER, [perm('agents', 'view')]))).toBe(
      false
    );
    expect(
      canSeeNavItem(loads, 'field', ctx(PERSONA.MANAGER, [perm('agents', 'field_load')]))
    ).toBe(true);
    expect(
      canSeeNavItem(loads, 'field', ctx(PERSONA.MANAGER, [perm('agents', 'field_load')], {
        isFeatureEnabled: (mod, feat) => !(mod === 'sales' && feat === 'field_load'),
      }))
    ).toBe(false);
  });

  test('security: route gates stay on dispatch.view and agents.field_load', () => {
    expect(routePermissionGateForPath('/sales/field')).toEqual(
      expect.objectContaining({ module: 'dispatch', action: 'view' })
    );
    expect(routePermissionGateForPath('/sales/field-loads')).toEqual(
      expect.objectContaining({ module: 'agents', action: 'field_load' })
    );
  });

  test('stress: field visibility stays stable across many permission checks', () => {
    const orders = fieldSection().items[0];
    const loads = fieldSection().items[1];
    const withDispatch = ctx(PERSONA.MANAGER, [perm('dispatch', 'view')]);
    const withLoad = ctx(PERSONA.MANAGER, [perm('agents', 'field_load')]);
    for (let i = 0; i < 400; i += 1) {
      expect(canSeeNavItem(orders, 'field', withDispatch)).toBe(true);
      expect(canSeeNavItem(loads, 'field', withLoad)).toBe(true);
      expect(canSeeNavItem(orders, 'field', withLoad)).toBe(false);
    }
  });
});
