/**
 * Domain labels for permission grouping (fallback when API omits fields).
 * Canonical list lives in be/settings/module_registry.py DOMAINS.
 */
export const DOMAIN_LABELS = {
  commerce: 'Sell & serve',
  catalog: 'Catalog & buying',
  inventory: 'Stock & warehouse',
  finance: 'Money & accounting',
  insights: 'Insights',
  people: 'People',
  platform: 'Platform',
};

export const DOMAIN_ORDER = [
  'commerce',
  'catalog',
  'inventory',
  'finance',
  'insights',
  'people',
  'platform',
];
