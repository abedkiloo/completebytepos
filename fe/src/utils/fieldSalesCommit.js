/**
 * Pre-commit summary + validation for field sales (pack / assign).
 */

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

export function canMarkReady(order) {
  return ['submitted', 'packing'].includes(order?.status);
}

export function canAssignDriver(order) {
  return ['ready', 'packing'].includes(order?.status)
    && !order?.assigned_delivery_agent_id;
}

export function packReadyError(order, canPack = true) {
  if (!canPack) return 'You cannot pack this order.';
  if (!order) return 'Select an order first.';
  if (!canMarkReady(order)) return 'This order is not waiting to be packed.';
  const qty = fieldOrderQty(order);
  if (qty <= 0) return 'This order has no products to pack.';
  return '';
}

export function assignDriverError(order, driverId, canPack = true) {
  if (!canPack) return 'You cannot assign a driver.';
  if (!order) return 'Select an order first.';
  if (!canAssignDriver(order)) return 'This order is not ready to assign.';
  if (!driverId) return 'Select a delivery driver first.';
  return '';
}

export function packCommitRows(order, formatMoney) {
  const money = typeof formatMoney === 'function' ? formatMoney : String;
  return [
    { label: 'Order', value: order?.id != null ? `#${order.id}` : '', emphasis: true },
    { label: 'Customer', value: order?.customer_name || '—' },
    { label: 'Products', value: fieldOrderLineSummary(order) },
    { label: 'Total', value: money(fieldOrderTotal(order)), emphasis: true },
    { label: 'After confirm', value: 'Ready for pickup' },
  ];
}

export function assignCommitRows(order, driver, formatMoney) {
  const money = typeof formatMoney === 'function' ? formatMoney : String;
  const driverName = driver?.display_name || driver?.username || 'Selected driver';
  return [
    { label: 'Order', value: order?.id != null ? `#${order.id}` : '', emphasis: true },
    { label: 'Customer', value: order?.customer_name || '—' },
    { label: 'Products', value: fieldOrderLineSummary(order) },
    { label: 'Total', value: money(fieldOrderTotal(order)) },
    { label: 'Driver', value: driverName, emphasis: true, tone: 'success' },
  ];
}
