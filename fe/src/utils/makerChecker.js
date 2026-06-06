/**
 * Maker-checker UX helpers (align with be/approvals).
 */

import { hasPermission } from './roleAccess';

export const PENDING_APPROVAL_MESSAGE =
  'Change submitted for approval — not yet active.';

const SENSITIVE_PRODUCT_KEYS = new Set([
  'price',
  'selling_price',
  'mrp',
  'cost',
  'tax_rate',
  'stock_quantity',
  'low_stock_threshold',
  'reorder_quantity',
  'track_stock',
  'is_active',
  'unit',
]);

export function isMakerCheckerEnabled(settings) {
  return Boolean(settings?.maker_checker_enabled);
}

/** Optional P3: post-completion sale metadata edits (off by default). */
export function isSalesMakerCheckerActive(settings) {
  return isMakerCheckerEnabled(settings) && Boolean(settings?.maker_checker_sales_controls);
}

export function completedSaleDirectEditBlocked(settings) {
  return !isSalesMakerCheckerActive(settings);
}

export function isPendingApprovalResponse(status) {
  return status === 202;
}

export function extractPendingChange(responseData) {
  if (!responseData) return null;
  return responseData.pending_change || responseData.pending_changes?.[0] || null;
}

const SENSITIVE_VARIANT_KEYS = new Set([
  'price',
  'selling_price',
  'mrp',
  'cost',
  'stock_quantity',
  'low_stock_threshold',
  'is_active',
]);

function isUnsetFinancialValue(val) {
  if (val == null || val === '') return true;
  const n = parseFloat(val);
  return Number.isFinite(n) && n === 0;
}

/** True when setting a first non-zero price/stock value (not changing an existing one). */
function isInitialSensitiveSet(key, prev, next) {
  if (key === 'is_active') return false;
  const numericKeys = [
    'price',
    'selling_price',
    'mrp',
    'cost',
    'stock_quantity',
    'low_stock_threshold',
  ];
  if (!numericKeys.includes(key)) return false;
  return isUnsetFinancialValue(prev) && !isUnsetFinancialValue(next);
}

function sensitiveFieldNeedsReason(key, prev, next) {
  if (key === 'is_active') {
    return Boolean(next) !== Boolean(prev);
  }
  if (isInitialSensitiveSet(key, prev, next)) {
    return false;
  }
  return String(next ?? '') !== String(prev ?? '');
}

export function variantEditNeedsReason(formData, variant) {
  if (!formData || variant == null) return false;
  for (const key of SENSITIVE_VARIANT_KEYS) {
    if (!(key in formData)) continue;
    const next = formData[key];
    const prev =
      key === 'selling_price'
        ? variant.price ?? variant.selling_price
        : variant[key];
    if (sensitiveFieldNeedsReason(key, prev, next)) return true;
  }
  return false;
}

export function categoryEditNeedsReason(formData, category) {
  if (!category || !formData) return false;
  if ('is_active' in formData && formData.is_active === false && category.is_active !== false) {
    return true;
  }
  return false;
}

export function categoryDeactivateNeedsReason(category) {
  return Boolean(category?.is_active);
}

const STORE_SENSITIVE_KEYS = [
  'enabled_payment_methods',
  'receipt_footer_text',
  'receipt_header_text',
  'allow_sales_add_products',
  'sales_catalog_skip_pricing',
  'hide_entity_status_toggles',
  'receipt_show_logo',
  'receipt_show_sku',
  'receipt_auto_print',
];

export function storeSettingsEditNeedsReason(form, baseline) {
  if (!form || !baseline) return false;
  const methodsEqual =
    JSON.stringify(form.enabled_payment_methods || []) ===
    JSON.stringify(baseline.enabled_payment_methods || []);
  if (!methodsEqual) return true;
  return STORE_SENSITIVE_KEYS.some((key) => {
    if (key === 'enabled_payment_methods') return false;
    const next = form[key];
    const prev = baseline[key];
    if (typeof next === 'boolean' || typeof prev === 'boolean') {
      return Boolean(next) !== Boolean(prev);
    }
    return String(next ?? '') !== String(prev ?? '');
  });
}

export function moduleSettingsPatchNeedsReason(values, baselineSettings = {}) {
  if (!values || typeof values !== 'object') return false;
  return Object.keys(values).some(
    (key) => String(values[key]) !== String(baselineSettings[key] ?? '')
  );
}

export function rolePermissionsChanged(nextIds, role) {
  const prev = (role?.permissions || []).map((p) => p.id).sort((a, b) => a - b);
  const next = [...(nextIds || [])].map(Number).sort((a, b) => a - b);
  return JSON.stringify(prev) !== JSON.stringify(next);
}

export function productEditNeedsReason(formData, product, { financialFieldsLocked = false } = {}) {
  if (financialFieldsLocked) return false;
  if (!formData) return false;
  // First-time create: setting opening price/stock is not a "change".
  if (product == null) return false;
  for (const key of SENSITIVE_PRODUCT_KEYS) {
    if (!(key in formData)) continue;
    const next = formData[key];
    const prev =
      key === 'selling_price'
        ? product.price ?? product.selling_price
        : product[key];
    if (sensitiveFieldNeedsReason(key, prev, next)) return true;
  }
  return false;
}

/** True when proposed price moves more than 50% from the approved price. */
export function priceChangeExceedsFiftyPercent(row) {
  if (!row || row.action_type !== 'product_price') return false;
  const orig = parseFloat(row.original_values?.price);
  const proposed = parseFloat(row.proposed_values?.price);
  if (!Number.isFinite(orig) || !Number.isFinite(proposed) || orig <= 0) {
    return false;
  }
  return Math.abs(proposed - orig) / orig > 0.5;
}

export function needsExtremePriceConfirm(row) {
  return priceChangeExceedsFiftyPercent(row);
}

export function pendingApprovalLabels(pendingApproval) {
  if (!pendingApproval || typeof pendingApproval !== 'object') return [];
  const labels = [];
  if (pendingApproval.pending_price) labels.push('Price');
  if (pendingApproval.pending_stock) labels.push('Stock');
  if (pendingApproval.pending_deactivation) labels.push('Deactivation');
  if (pendingApproval.pending_delete) labels.push('Delete');
  return labels;
}

export function formatPendingApprovalHint(pendingApproval) {
  const parts = pendingApprovalLabels(pendingApproval);
  if (!parts.length) return PENDING_APPROVAL_MESSAGE;
  return `${PENDING_APPROVAL_MESSAGE} (${parts.join(', ')})`;
}

/** Records with own pending/approve status (expense, income, money transfer). */
export function financialRecordNeedsReason() {
  return true;
}

export function getPermissionsFromStorage() {
  try {
    const raw = localStorage.getItem('permissions');
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function userMayApproveModule(module, permissions = getPermissionsFromStorage()) {
  return hasPermission(permissions, module, 'approve');
}

export function getCurrentUserId() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    if (user?.id != null) return Number(user.id);
    const profile = JSON.parse(localStorage.getItem('profile') || '{}');
    if (profile?.user != null) return Number(profile.user);
    if (profile?.user_id != null) return Number(profile.user_id);
    return null;
  } catch {
    return null;
  }
}

/**
 * @param {'expenses'|'income'|'money_transfer'} module
 */
export function canApproveFinancialRecord(
  record,
  settings,
  currentUserId = getCurrentUserId(),
  module = 'expenses',
  permissions = getPermissionsFromStorage(),
) {
  if (!userMayApproveModule(module, permissions)) {
    return false;
  }
  if (!isMakerCheckerEnabled(settings)) {
    return true;
  }
  const makerId = record?.created_by;
  if (makerId == null || currentUserId == null) {
    return true;
  }
  return Number(makerId) !== Number(currentUserId);
}

export function financialSubmitSuccessMessage(settings) {
  return isMakerCheckerEnabled(settings)
    ? 'Submitted for approval — a checker must approve before it takes effect.'
    : null;
}

export function handleWriteResponse(response, { onApplied, onPending } = {}) {
  if (isPendingApprovalResponse(response?.status)) {
    const pending = extractPendingChange(response?.data);
    onPending?.(pending, response.data);
    return 'pending';
  }
  onApplied?.(response?.data);
  return 'applied';
}
