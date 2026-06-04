/**
 * Invoice API payload helpers (align with be/sales/invoice_items.py).
 */

export function resolveLineProductId(item) {
  const raw = item?.product_id ?? item?.product;
  if (raw == null || raw === '') return null;
  const id = parseInt(raw, 10);
  return Number.isFinite(id) ? id : null;
}

export function formatInvoiceItemsForApi(items = []) {
  return (items || [])
    .filter((item) => {
      const productId = resolveLineProductId(item);
      const qty = parseInt(item.quantity, 10) || 0;
      return productId && qty > 0;
    })
    .map((item) => ({
      product_id: resolveLineProductId(item),
      quantity: Math.max(1, parseInt(item.quantity, 10) || 0),
      unit_price: parseFloat(item.unit_price) || 0,
      description: item.description || '',
      variant_id: item.variant_id || null,
    }));
}

export function formatPaymentPayload({ invoiceId, amount, payment_method, payment_date, reference, notes }) {
  return {
    invoice_id: invoiceId,
    amount: parseFloat(amount),
    payment_method,
    payment_date,
    reference: reference || '',
    notes: notes || '',
  };
}
