import {
  filterModuleCatalog,
  filterNavSections,
  normalizeNavQuery,
  navTextMatches,
} from './navSearch';

describe('navSearch', () => {
  test('normalizeNavQuery trims and lowercases', () => {
    expect(normalizeNavQuery('  Daily  Notes ')).toBe('daily notes');
    expect(normalizeNavQuery('')).toBe('');
  });

  test('navTextMatches empty needle always true', () => {
    expect(navTextMatches('Anything', '')).toBe(true);
  });

  test('filterNavSections returns same reference when query empty', () => {
    const sections = [
      { id: 'sales', label: 'Sales', visibleItems: [{ label: 'POS', to: '/pos' }] },
    ];
    expect(filterNavSections(sections, '  ')).toBe(sections);
  });

  test('filterNavSections matches item labels', () => {
    const sections = [
      {
        id: 'sales',
        label: 'Sales',
        visibleItems: [
          { label: 'POS', to: '/pos' },
          { label: 'Daily sales', to: '/sales/daily' },
        ],
      },
      {
        id: 'inventory',
        label: 'Inventory',
        visibleItems: [{ label: 'Stock', to: '/inventory' }],
      },
    ];
    const filtered = filterNavSections(sections, 'daily');
    expect(filtered).toHaveLength(1);
    expect(filtered[0].visibleItems.map((i) => i.label)).toEqual(['Daily sales']);
  });

  test('filterNavSections keeps all items when section label matches', () => {
    const sections = [
      {
        id: 'sales',
        label: 'Sales',
        visibleItems: [
          { label: 'POS', to: '/pos' },
          { label: 'Invoices', to: '/invoices' },
        ],
      },
    ];
    const filtered = filterNavSections(sections, 'sales');
    expect(filtered[0].visibleItems).toHaveLength(2);
  });

  test('filterModuleCatalog matches feature names', () => {
    const catalog = [
      {
        id: 'ops',
        label: 'Operations',
        description: 'Day to day',
        modules: [
          {
            id: 1,
            module_name: 'payroll',
            module_name_display: 'Payroll',
            description: 'Pay staff',
            features: {
              sales_commission: {
                feature_name: 'Sales commission',
                description: 'Field agent commission',
              },
            },
          },
          {
            id: 2,
            module_name: 'pos',
            module_name_display: 'Point of sale',
            description: 'Checkout',
            features: {},
          },
        ],
      },
    ];
    const filtered = filterModuleCatalog(catalog, 'commission');
    expect(filtered).toHaveLength(1);
    expect(filtered[0].modules).toHaveLength(1);
    expect(filtered[0].modules[0].module_name).toBe('payroll');
  });
});
