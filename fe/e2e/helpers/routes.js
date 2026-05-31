// @ts-check

/**
 * Super-admin smoke routes — each must render without crashing.
 * Use `heading` for role=heading match, or `text` for visible copy (dashboard home).
 */
const SMOKE_ROUTES = [
  { path: '/', text: /Welcome back/i },
  { path: '/products', heading: /^products$/i },
  { path: '/categories', heading: /categor/i },
  { path: '/customers', heading: /customers/i },
  { path: '/suppliers', heading: /suppliers/i },
  { path: '/employees', heading: /employees/i },
  { path: '/inventory', heading: /inventory|stock/i },
  { path: '/sales', heading: /sales history|sales/i },
  { path: '/reports', heading: /reports/i },
  { path: '/expenses', heading: /expenses/i },
  { path: '/income', heading: /income/i },
  { path: '/accounting', heading: /accounting/i },
  { path: '/invoices', heading: /invoices/i },
  { path: '/users', heading: /users/i },
  { path: '/roles', heading: /roles/i },
  { path: '/barcodes', heading: /barcode/i },
  { path: '/normal-sale', heading: /normal sale/i },
  { path: '/module-settings', heading: /app modules|module settings/i },
  { path: '/system-settings', heading: /system settings/i },
  { path: '/branches', heading: /branch management/i },
  { path: '/pos/billing', heading: /terminal pos/i },
];

module.exports = { SMOKE_ROUTES };
