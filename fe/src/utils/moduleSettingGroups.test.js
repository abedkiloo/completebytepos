import { groupModuleSettings, stripSettingLabelPrefix } from './moduleSettingGroups';

describe('moduleSettingGroups', () => {
  test('stripSettingLabelPrefix removes role prefixes', () => {
    expect(stripSettingLabelPrefix('Sales: set selling price / MRP')).toBe('set selling price / MRP');
    expect(stripSettingLabelPrefix('Managers: set cost of goods')).toBe('set cost of goods');
    expect(stripSettingLabelPrefix('Show SKU in product list')).toBe('Show SKU in product list');
  });

  test('groupModuleSettings buckets by label prefix', () => {
    const entries = [
      ['show_sku', { label: 'Show SKU', display_order: 1 }],
      ['allow_sales_edit_pricing', { label: 'Sales: set selling price', display_order: 2 }],
      ['allow_manager_edit_cost', { label: 'Managers: set cost', display_order: 3 }],
    ];
    const groups = groupModuleSettings(entries);
    expect(groups.map((g) => g.id)).toEqual(['general', 'sales', 'managers']);
    expect(groups[1].items[0][0]).toBe('allow_sales_edit_pricing');
  });
});
