/**
 * Summary rows for web pre-commit dialogs (create/update/send/toggle).
 */

export function compactCommitRows(rows = []) {
  return (Array.isArray(rows) ? rows : []).filter(
    (row) => row && row.label != null && row.value != null && row.value !== '',
  );
}

export function userCommitRows(form = {}, { isEdit = false } = {}) {
  const name = `${form.first_name || ''} ${form.last_name || ''}`.trim();
  return compactCommitRows([
    { label: 'Username', value: form.username || '—', emphasis: true },
    name ? { label: 'Name', value: name } : null,
    form.email ? { label: 'Email', value: form.email } : null,
    { label: 'Role', value: form.role || '—' },
    { label: 'Action', value: isEdit ? 'Update user' : 'Create user' },
  ]);
}

export function assignRoleRows(user = {}, roleLabel = '') {
  return compactCommitRows([
    { label: 'User', value: user.username || '—', emphasis: true },
    { label: 'New role', value: roleLabel || '—', emphasis: true, tone: 'warning' },
  ]);
}

export function invoiceCommitRows(form = {}, { isEdit = false, formatMoney } = {}) {
  const money = typeof formatMoney === 'function' ? formatMoney : String;
  const itemCount = (form.items || []).filter((item) => item?.product_id).length;
  return compactCommitRows([
    { label: 'Customer', value: form.customer_name || 'Walk-in' },
    { label: 'Items', value: String(itemCount) },
    { label: 'Total', value: money(form.total), emphasis: true },
    { label: 'Action', value: isEdit ? 'Update invoice' : 'Create invoice' },
  ]);
}

export function invoiceSendRows(invoice = {}, formatMoney) {
  const money = typeof formatMoney === 'function' ? formatMoney : String;
  return compactCommitRows([
    {
      label: 'Invoice',
      value: invoice.invoice_number || (invoice.id != null ? `#${invoice.id}` : '—'),
      emphasis: true,
    },
    { label: 'Customer', value: invoice.customer_name || '—' },
    invoice.total != null ? { label: 'Total', value: money(invoice.total) } : null,
    { label: 'After confirm', value: 'Sent — receivable recorded' },
  ]);
}

export function settingsCommitRows(dirtyPayload = {}, { hasLogo = false, clearingLogo = false } = {}) {
  if (clearingLogo) {
    return compactCommitRows([
      { label: 'Action', value: 'Remove receipt logo', emphasis: true, tone: 'warning' },
    ]);
  }
  const keys = Object.keys(dirtyPayload || {});
  return compactCommitRows([
    { label: 'Changes', value: keys.length ? keys.join(', ') : 'No field changes', emphasis: true },
    hasLogo ? { label: 'Receipt logo', value: 'New file will be uploaded' } : null,
  ]);
}

export function roleCommitRows(form = {}, { isEdit = false } = {}) {
  return compactCommitRows([
    { label: 'Role', value: form.name || '—', emphasis: true },
    { label: 'Permissions', value: String((form.permission_ids || []).length) },
    { label: 'Action', value: isEdit ? 'Update role' : 'Create role' },
  ]);
}

export function branchCommitRows(form = {}, { isEdit = false } = {}) {
  return compactCommitRows([
    { label: 'Branch', value: form.name || '—', emphasis: true },
    form.branch_code ? { label: 'Code', value: form.branch_code } : null,
    form.city ? { label: 'City', value: form.city } : null,
    { label: 'Action', value: isEdit ? 'Update branch' : 'Create branch' },
  ]);
}

export function employeeCommitRows(form = {}, { isEdit = false } = {}) {
  const name = `${form.first_name || ''} ${form.last_name || ''}`.trim();
  return compactCommitRows([
    { label: 'Employee', value: name || '—', emphasis: true },
    { label: 'ID', value: form.employee_id || '—' },
    { label: 'Position', value: form.position || '—' },
    { label: 'Action', value: isEdit ? 'Update employee' : 'Create employee' },
  ]);
}

export function customerCommitRows(form = {}, { isEdit = false } = {}) {
  return compactCommitRows([
    { label: 'Customer', value: form.name || '—', emphasis: true },
    form.phone ? { label: 'Phone', value: form.phone } : null,
    form.email ? { label: 'Email', value: form.email } : null,
    { label: 'Action', value: isEdit ? 'Update customer' : 'Create customer' },
  ]);
}

export function supplierCommitRows(form = {}, { isEdit = false } = {}) {
  return compactCommitRows([
    { label: 'Supplier', value: form.name || '—', emphasis: true },
    form.phone ? { label: 'Phone', value: form.phone } : null,
    { label: 'Action', value: isEdit ? 'Update supplier' : 'Create supplier' },
  ]);
}

export function productCommitRows(form = {}, { isEdit = false } = {}) {
  return compactCommitRows([
    { label: 'Product', value: form.name || '—', emphasis: true },
    form.has_variants
      ? { label: 'Type', value: 'With variants' }
      : { label: 'Price', value: String(form.selling_price || form.price || '0') },
    { label: 'Action', value: isEdit ? 'Update product' : 'Create product' },
  ]);
}

export function categoryCommitRows(form = {}, { isSubcategory = false } = {}) {
  return compactCommitRows([
    { label: isSubcategory ? 'Subcategory' : 'Category', value: form.name || '—', emphasis: true },
    form.description ? { label: 'Description', value: form.description } : null,
    { label: 'Action', value: 'Create' },
  ]);
}

export function moduleToggleRows(module = {}, nextEnabled = false) {
  return compactCommitRows([
    {
      label: 'Module',
      value: module.module_name_display || module.module_name || '—',
      emphasis: true,
    },
    {
      label: 'After confirm',
      value: nextEnabled ? 'Enabled' : 'Disabled',
      tone: nextEnabled ? 'success' : 'danger',
    },
  ]);
}

export function attributeDeleteRows(row = {}, kind = 'sizes') {
  return compactCommitRows([
    { label: kind === 'colors' ? 'Color' : 'Size', value: row.name || '—', emphasis: true },
    { label: 'After confirm', value: 'Deleted', tone: 'danger' },
  ]);
}

export function approvalCommitRows(row = {}) {
  return compactCommitRows([
    { label: 'Change', value: row.action_type || 'Pending change', emphasis: true },
    row.reason ? { label: 'Reason', value: row.reason } : null,
    { label: 'Action', value: 'Approve and make live', tone: 'success' },
  ]);
}

export function installCommitRows({ preset = '', includeTestData = false } = {}) {
  return compactCommitRows([
    {
      label: 'Action',
      value: 'Reset database and install',
      emphasis: true,
      tone: 'danger',
    },
    { label: 'Preset', value: preset || '—' },
    { label: 'Test data', value: includeTestData ? 'Included' : 'Not included' },
  ]);
}

export function expenseCategoryCommitRows(form = {}, { isEdit = false } = {}) {
  return compactCommitRows([
    { label: 'Category', value: form.name || '—', emphasis: true },
    form.description ? { label: 'Description', value: form.description } : null,
    { label: 'Action', value: isEdit ? 'Update category' : 'Create category' },
  ]);
}

export function attributeSaveRows(form = {}, { kind = 'sizes', isEdit = false } = {}) {
  return compactCommitRows([
    { label: kind === 'colors' ? 'Color' : 'Size', value: form.name || '—', emphasis: true },
    { label: 'Action', value: isEdit ? 'Update' : 'Create' },
  ]);
}

export function presetApplyRows(preset = {}) {
  return compactCommitRows([
    { label: 'Preset', value: preset.label || preset.id || '—', emphasis: true },
    { label: 'After confirm', value: 'Modules will match this preset', tone: 'warning' },
  ]);
}

export function featureToggleRows(feature = {}, nextEnabled = false) {
  return compactCommitRows([
    { label: 'Feature', value: feature.feature_name || '—', emphasis: true },
    {
      label: 'After confirm',
      value: nextEnabled ? 'On' : 'Off',
      tone: nextEnabled ? 'success' : 'danger',
    },
  ]);
}

export function approvalExpenseRows(expense = {}) {
  return compactCommitRows([
    {
      label: 'Expense',
      value: expense.description || expense.expense_number || '—',
      emphasis: true,
    },
    expense.amount != null ? { label: 'Amount', value: String(expense.amount) } : null,
    { label: 'Action', value: 'Approve expense', tone: 'success' },
  ]);
}
