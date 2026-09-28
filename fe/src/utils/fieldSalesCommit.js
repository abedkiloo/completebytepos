/**
 * Pre-commit summary + validation for field sales (pack / assign).
 */

export function deliveryAssigneeLabel(person) {
  const name = person?.display_name || person?.username || '';
  const role = (person?.role_name || '').trim();
  if (name && role) return `${name} · ${role}`;
  if (name) return name;
  if (role) return role;
  if (person?.id != null) return `Person #${person.id}`;
  return 'Selected person';
}

export function fieldOrderQty(order) {
  const lines = Array.isArray(order?.lines) ? order.lines : [];
  return lines.reduce((sum, line) => sum + Number(line.quantity || 0), 0);
}

export function fieldOrderTotal(order) {
  const lines = Array.isArray(order?.lines) ? order.lines : [];
  return lines.reduce((sum, line) => {
    const qty = Number(line.quantity || 0);
    const price = Number(line.unit_price || 0);
    const total = line.line_total != null ? Number(line.line_total) : qty * price;
    return sum + (Number.isFinite(total) ? total : 0);
  }, 0);
}

export function fieldOrderLineSummary(order) {
  const lines = Array.isArray(order?.lines) ? order.lines : [];
  if (!lines.length) return '—';
  const qty = fieldOrderQty(order);
  const names = lines
    .slice(0, 2)
    .map((line) => line.product_name || `Product #${line.product_id}`)
    .join(', ');
  const more = lines.length > 2 ? ` +${lines.length - 2}` : '';
  return `${names}${more} · qty ${qty}`;
}

export const DISPATCH_STEP_PACK = 'Pack & mark ready for pickup';
export const DISPATCH_STEP_ASSIGN = 'Assign for delivery';

export function fieldOrderIsPacked(order) {
  return ['ready', 'out_for_delivery', 'done'].includes(order?.status);
}

export function canMarkReady(order) {
  return ['submitted', 'packing'].includes(order?.status);
}

export function canShowAssignStep(order) {
  return ['submitted', 'packing', 'ready'].includes(order?.status)
    && !order?.assigned_delivery_agent_id;
}

export function canAssignDriver(order) {
  return order?.status === 'ready' && !order?.assigned_delivery_agent_id;
}

export function dispatchWorkflowSteps(order) {
  const packed = fieldOrderIsPacked(order);
  const assigned = Boolean(order?.assigned_delivery_agent_id);
  return [
    {
      id: 'pack',
      label: DISPATCH_STEP_PACK,
      done: packed,
      current: !packed,
    },
    {
      id: 'assign',
      label: DISPATCH_STEP_ASSIGN,
      done: assigned,
      current: packed && !assigned,
    },
  ];
}

export function assignBlockedByPreviousStep(order) {
  if (!order) return null;
  if (fieldOrderIsPacked(order)) return null;
  return {
    title: 'Pack this order first',
    message:
      'Assign for delivery is the next step. Finish packing and mark the order ready for pickup before you choose who delivers.',
    currentStep: DISPATCH_STEP_PACK,
    nextStep: DISPATCH_STEP_ASSIGN,
    opensPack: true,
  };
}

export function assignBlockedRows(blocked) {
  if (!blocked) return [];
  return [
    {
      label: 'Do this first',
      value: blocked.currentStep,
      emphasis: true,
      tone: 'warning',
    },
    { label: 'Then', value: blocked.nextStep },
  ];
}

export function fieldOrderHasCustomer(order) {
  return Boolean(order?.customer || String(order?.customer_name || '').trim());
}

export function packReadyError(order, canPack = true) {
  if (!canPack) return 'You cannot pack this order.';
  if (!order) return 'Select an order first.';
  if (!canMarkReady(order)) return 'This order is not waiting to be packed.';
  if (!fieldOrderHasCustomer(order)) {
    return 'This field sale needs a customer before it can be packed.';
  }
  const qty = fieldOrderQty(order);
  if (qty <= 0) return 'This order has no products to pack.';
  return '';
}

export function assignDriverError(order, driverId, canPack = true) {
  if (!canPack) return 'You cannot assign this delivery.';
  if (!order) return 'Select an order first.';
  const blocked = assignBlockedByPreviousStep(order);
  if (blocked) return blocked.message;
  if (!canAssignDriver(order)) return 'This order is not ready to assign.';
  if (!driverId) return 'Select who will deliver first.';
  return '';
}

export const DEBTOR_CONFIRM_COPY =
  'This customer will be added as a debtor in the system. Collect later as Cash or M-Pesa.';

export function assignCreatesCustomerDebt() {
  return false;
}

export function packConfirmDescription(order) {
  const name = String(order?.customer_name || 'this customer').trim() || 'this customer';
  return `After you confirm, ${name} is added as a debtor. Collect the amount later under Debt collection (Cash or M-Pesa).`;
}

export function assignConfirmDescription() {
  return 'The person you pick will see it on their route after you confirm.';
}

export function debtorConfirmRow() {
  return {
    label: 'Customer account',
    value: DEBTOR_CONFIRM_COPY,
    tone: 'warning',
  };
}

export function packCommitRows(order, formatMoney) {
  const money = typeof formatMoney === 'function' ? formatMoney : String;
  return [
    { label: 'Order', value: order?.id != null ? `#${order.id}` : '', emphasis: true },
    { label: 'Customer', value: order?.customer_name || '—' },
    { label: 'Products', value: fieldOrderLineSummary(order) },
    { label: 'Total', value: money(fieldOrderTotal(order)), emphasis: true },
    debtorConfirmRow(),
  ];
}

export function assignCommitRows(order, driver, formatMoney) {
  const money = typeof formatMoney === 'function' ? formatMoney : String;
  const driverName = deliveryAssigneeLabel(driver);
  const rows = [
    { label: 'Order', value: order?.id != null ? `#${order.id}` : '', emphasis: true },
    { label: 'Customer', value: order?.customer_name || '—' },
    { label: 'Products', value: fieldOrderLineSummary(order) },
    { label: 'Total', value: money(fieldOrderTotal(order)) },
    { label: 'Delivered by', value: driverName, emphasis: true, tone: 'success' },
  ];
  return rows;
}

export function mergeDriverIntoList(drivers, driver) {
  const id = Number(driver?.id);
  const list = Array.isArray(drivers) ? drivers : [];
  if (!Number.isFinite(id) || id <= 0) return list;
  return [...list.filter((row) => Number(row.id) !== id), { ...driver, id }];
}
