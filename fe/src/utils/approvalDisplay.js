/**
 * Human-friendly labels for maker-checker pending changes (checker queue).
 */

import { formatCurrency } from './formatters';

export const ACTION_TYPE_LABELS = {
  product_price: 'Selling price change',
  product_stock: 'Stock change',
  product_deactivate: 'Deactivate product',
  product_delete: 'Delete product',
  product_unit: 'Unit of measure change',
  product_tax: 'Tax rate change',
  category_deactivate: 'Deactivate category',
  category_delete: 'Delete category',
  stock_adjust: 'Stock adjustment',
  stock_purchase: 'Stock purchase',
  stock_transfer: 'Stock transfer',
  store_settings: 'Store settings change',
  payment_methods: 'Payment methods change',
  receipt_legal: 'Receipt text change',
  role_permissions: 'Role permissions change',
  sale_completed_edit: 'Completed sale edit',
  sale_refund: 'Sale void / refund',
};

export const ENTITY_TYPE_LABELS = {
  'products.Product': 'Product',
  'products.ProductVariant': 'Product variant',
  'products.Category': 'Category',
  'settings.StoreSettings': 'Store settings',
  'settings.ModuleSetting': 'Module setting',
  'accounts.Role': 'User role',
  'sales.Sale': 'Sale',
  'inventory.StockMovement': 'Stock movement',
};

export const FIELD_LABELS = {
  price: 'Selling price',
  selling_price: 'Selling price',
  mrp: 'MRP (list price)',
  cost: 'Cost',
  stock_quantity: 'Stock on hand',
  low_stock_threshold: 'Low stock alert at',
  reorder_quantity: 'Reorder quantity',
  track_stock: 'Track stock',
  is_active: 'Active',
  tax_rate: 'Tax rate (%)',
  unit: 'Unit',
  name: 'Name',
  description: 'Description',
  enabled_payment_methods: 'Enabled payment methods',
  receipt_footer_text: 'Receipt footer',
  receipt_header_text: 'Receipt header',
  receipt_show_logo: 'Show logo on receipt',
  receipt_show_sku: 'Show SKU on receipt',
  receipt_auto_print: 'Auto-print receipt',
  allow_sales_add_products: 'Allow sales staff to add products',
  sales_catalog_skip_pricing: 'Hide pricing from sales staff',
  hide_entity_status_toggles: 'Hide active/inactive toggles',
  maker_checker_enabled: 'Maker-checker approvals',
  quantity: 'Quantity',
  notes: 'Notes',
  permissions: 'Permissions',
  refund_mode: 'Refund type',
  lines: 'Lines to return',
  amount: 'Refund amount',
  sale_total: 'Sale total',
  refundable_remaining: 'Refundable remaining',
};

const MONEY_FIELDS = new Set([
  'price',
  'selling_price',
  'mrp',
  'cost',
  'amount',
  'sale_total',
  'refundable_remaining',
]);

const BOOLEAN_FIELDS = new Set([
  'is_active',
  'track_stock',
  'receipt_show_logo',
  'receipt_show_sku',
  'receipt_auto_print',
  'allow_sales_add_products',
  'sales_catalog_skip_pricing',
  'hide_entity_status_toggles',
  'maker_checker_enabled',
]);

const PAYMENT_METHOD_LABELS = {
  cash: 'Cash',
  mpesa: 'M-Pesa',
  card: 'Card',
  wallet: 'Wallet',
};

export function formatActionTypeLabel(actionType) {
  if (!actionType) return 'Change awaiting approval';
  return ACTION_TYPE_LABELS[actionType] || actionType.replace(/_/g, ' ');
}

export function formatEntityTypeLabel(entityType, entityRepr) {
  if (entityRepr && String(entityRepr).trim()) {
    return String(entityRepr).trim();
  }
  if (!entityType) return 'Item';
  return ENTITY_TYPE_LABELS[entityType] || String(entityType).split('.').pop();
}

export function formatFieldLabel(fieldKey) {
  if (!fieldKey) return '';
  return FIELD_LABELS[fieldKey] || fieldKey.replace(/_/g, ' ');
}

export function formatApprovalValue(fieldKey, value) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (BOOLEAN_FIELDS.has(fieldKey)) {
    return value === true || value === 'true' || value === 1 || value === '1' ? 'Yes' : 'No';
  }
  if (fieldKey === 'enabled_payment_methods' && Array.isArray(value)) {
    return value
      .map((id) => PAYMENT_METHOD_LABELS[String(id).toLowerCase()] || id)
      .join(', ');
  }
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  if (MONEY_FIELDS.has(fieldKey)) {
    const n = parseFloat(value);
    if (Number.isFinite(n)) {
      return formatCurrency(n);
    }
  }
  if (fieldKey === 'tax_rate') {
    const n = parseFloat(value);
    return Number.isFinite(n) ? `${n}%` : String(value);
  }
  return String(value);
}

/**
 * Rows for the checker diff table — only fields present in proposed (or both).
 */
export function buildApprovalDiffRows(original = {}, proposed = {}) {
  const keys = new Set([
    ...Object.keys(original || {}),
    ...Object.keys(proposed || {}),
  ]);
  const rows = [];
  keys.forEach((key) => {
    const before = original?.[key];
    const after = proposed?.[key];
    if (JSON.stringify(before) === JSON.stringify(after)) {
      return;
    }
    rows.push({
      key,
      label: formatFieldLabel(key),
      before: formatApprovalValue(key, before),
      after: formatApprovalValue(key, after),
    });
  });
  return rows.sort((a, b) => a.label.localeCompare(b.label));
}

export function describeApprovalSummary(row) {
  const action = formatActionTypeLabel(row?.action_type);
  const item = formatEntityTypeLabel(row?.entity_type, row?.entity_repr);
  return { action, item, headline: `${action} — ${item}` };
}
