/**
 * Maker-checker UX helpers (align with be/approvals).
 */

import { hasPermission, getPersonaFromStorage, PERSONA } from './roleAccess';

export const PENDING_APPROVALS_NAV = 'Reports → Pending approvals';

export const PENDING_APPROVAL_MESSAGE =
  'Submitted for approval — the change is not active yet. A manager will review it shortly.';

const REASON_CONTEXT_COPY = {
  default: {
    label: 'Reason for this change',
    placeholder: 'e.g. Supplier price list update, cycle count correction',
    summary:
      'This change will be sent to a manager for approval and will not take effect until it is approved.',
  },
  role_permissions: {
    label: 'Reason for permission changes',
    placeholder: 'e.g. Sales team needs invoice access for credit customers',
    summary:
      'These permission updates require manager approval. Users will not receive the new access until the change is approved.',
  },
  catalog: {
    label: 'Reason for this catalog change',
    placeholder: 'e.g. New supplier price list, seasonal deactivation',
    summary:
      'This catalog change will be submitted for approval and will not appear in POS or reports until it is approved.',
  },
  stock: {
    label: 'Reason for this stock change',
    placeholder: 'e.g. Cycle count correction, received shipment',
    summary:
      'This stock change will be submitted for approval. Quantities on hand stay unchanged until a manager approves it.',
  },
  settings: {
    label: 'Reason for this settings change',
    placeholder: 'e.g. Enable card payments for month-end promotion',
    summary:
      'This settings change will be submitted for approval and will not apply to the store until it is approved.',
  },
  financial: {
    label: 'Reason for this entry',
    placeholder: 'e.g. Monthly rent payment, supplier invoice #1042',
    summary:
      'This entry will be submitted for approval and will not affect accounts until a manager approves it.',
  },
};

/** True when the signed-in user can open the pending-approvals queue. */
export function userMayReviewPendingApprovals(permissions = getPermissionsFromStorage()) {
  const persona = getPersonaFromStorage();
  if (persona === PERSONA.SUPER_ADMIN || persona === PERSONA.MANAGER) {
    return true;
  }
  if (hasPermission(permissions, 'settings', 'approve')) {
    return true;
  }
  const approveModules = [
    'products',
    'categories',
    'inventory',
    'invoicing',
    'roles',
    'settings',
  ];
  return approveModules.some((module) => hasPermission(permissions, module, 'approve'));
}

/**
 * Friendly copy for maker-checker reason fields and prompts.
 * @param {'default'|'role_permissions'|'catalog'|'stock'|'settings'|'financial'} context
 */
export function makerCheckerReasonCopy(
  context = 'default',
  permissions = getPermissionsFromStorage()
) {
  const base = REASON_CONTEXT_COPY[context] || REASON_CONTEXT_COPY.default;
  const approverHint = userMayReviewPendingApprovals(permissions)
    ? `You can review and approve this request under ${PENDING_APPROVALS_NAV} in the sidebar.`
    : null;
  return {
    label: base.label,
    placeholder: base.placeholder,
    summary: base.summary,
    approverHint,
  };
}

/** Toast after HTTP 202 — includes approve path when the user is a checker. */
export function pendingApprovalToastMessage(permissions = getPermissionsFromStorage()) {
  if (userMayReviewPendingApprovals(permissions)) {
    return `Submitted for approval — not active yet. Open ${PENDING_APPROVALS_NAV} to approve it.`;
  }
  return PENDING_APPROVAL_MESSAGE;
}

/** Text for window.prompt when a reason is required (module settings toggles). */
export function makerCheckerPromptMessage(
  context = 'default',
  permissions = getPermissionsFromStorage()
) {
  const copy = makerCheckerReasonCopy(context, permissions);
  const lines = [copy.summary];
  if (copy.approverHint) {
    lines.push('', copy.approverHint);
  }
  lines.push('', 'Enter your reason:');
  return lines.join('\n');
}

/** Price, cost, stock, and status — not catalog metadata like unit or track_stock. */
const SENSITIVE_PRODUCT_KEYS = new Set([
  'price',
  'selling_price',
  'mrp',
  'cost',
  'stock_quantity',
  'is_active',
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

/** True when a module-settings PATCH was applied immediately (not queued for approval). */
export function isAppliedModuleSettingsResponse(status) {
  return status >= 200 && status < 300 && status !== 202;
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
  'is_active',
]);

export function isUnsetFinancialValue(val) {
  if (val == null || val === '') return true;
  const n = parseFloat(val);
  return Number.isFinite(n) && n === 0;
}

function parseSensitiveNumber(val) {
  if (val == null || val === '') return null;
  const n = parseFloat(val);
  return Number.isFinite(n) ? n : null;
}

function sensitiveNumericValuesEqual(prev, next) {
  if (isUnsetFinancialValue(prev) && isUnsetFinancialValue(next)) return true;
  const a = parseSensitiveNumber(prev);
  const b = parseSensitiveNumber(next);
  if (a != null && b != null) return a === b;
  return String(prev ?? '') === String(next ?? '');
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
  ];
  if (!numericKeys.includes(key)) return false;
  return isUnsetFinancialValue(prev) && !isUnsetFinancialValue(next);
}

function sensitiveFieldNeedsReason(key, prev, next) {
  if (key === 'is_active') {
    return Boolean(prev) !== Boolean(next);
  }
  if (isInitialSensitiveSet(key, prev, next)) {
    return false;
  }
  const numericKeys = [
    'price',
    'selling_price',
    'mrp',
    'cost',
    'stock_quantity',
  ];
  if (numericKeys.includes(key)) {
    return !sensitiveNumericValuesEqual(prev, next);
  }
  return String(next ?? '') !== String(prev ?? '');
}

/** Extract maker-checker reason error from an API error body. */
export function extractApiReasonError(data) {
  if (!data || typeof data !== 'object') return '';
  const reason = data.reason;
  if (Array.isArray(reason)) return reason[0] || '';
  if (typeof reason === 'string') return reason;
  return '';
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

export function productEditNeedsReason(
  formData,
  product,
  { financialFieldsLocked = false, variantProduct = false } = {},
) {
  if (financialFieldsLocked) return false;
  if (!formData) return false;
  // First-time create: setting opening price/stock is not a "change".
  if (product == null) return false;
  const keysToCheck = variantProduct ? new Set(['cost']) : SENSITIVE_PRODUCT_KEYS;
  for (const key of keysToCheck) {
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
