/**
 * Install / Module Settings presets — keep ids in sync with
 * be/settings/module_registry.py PRESETS.
 */
export const MODULE_PRESETS = [
  {
    id: 'retail_starter',
    label: 'Retail starter',
    description:
      'Billing desk, products, customers, and stock — no POS, barcodes, or normal sale.',
  },
  {
    id: 'retail_full',
    label: 'Full retail',
    description: 'Starter plus invoicing, suppliers, barcodes, and reports.',
  },
  {
    id: 'finance_pack',
    label: 'Finance pack',
    description: 'Expenses, income, and accounting (apply after retail).',
  },
];

export const DEFAULT_MODULE_PRESET = 'retail_starter';
