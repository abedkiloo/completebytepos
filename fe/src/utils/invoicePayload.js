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

export function parseInvoiceBalance(invoice) {
  const balance = parseFloat(invoice?.balance);
  return Number.isFinite(balance) ? Math.max(0, balance) : 0;
}

/**
 * Parse and validate a partial (or full) payment amount against invoice balance.
 * @returns {{ ok: true, amount: number } | { ok: false, error: string }}
 */
export function validatePaymentAmount(rawAmount, invoice) {
  const balance = parseInvoiceBalance(invoice);
  if (balance <= 0) {
    return { ok: false, error: 'This invoice has no remaining balance.' };
  }

  const amount = parseFloat(String(rawAmount ?? '').trim());
  if (!Number.isFinite(amount) || amount <= 0) {
    return { ok: false, error: 'Enter a payment amount greater than zero.' };
  }
  if (amount > balance + 0.001) {
    return {
      ok: false,
      error: `Amount cannot exceed the remaining balance (${balance.toFixed(2)}).`,
    };
  }
  return { ok: true, amount: Math.round(amount * 100) / 100 };
}

export function formatPaymentPayload({ invoiceId, amount, payment_method, payment_date, reference, notes }) {
  return {
    invoice_id: invoiceId,
    amount: typeof amount === 'number' ? amount : parseFloat(amount),
    payment_method,
    payment_date,
    reference: reference || '',
    notes: notes || '',
  };
}
