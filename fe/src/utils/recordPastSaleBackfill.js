/** Pure helpers for Record past sale — resubmit, served-by, and payload building. */

export function defaultOccurredAtLocal(now = new Date()) {
  const d = new Date(now);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export function minOccurredAtLocal(maxDays, now = new Date()) {
  const d = new Date(now);
  d.setDate(d.getDate() - maxDays);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export function toIsoDatetime(localValue) {
  if (!localValue) return null;
  const d = new Date(localValue);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function localDatetimeFromIso(iso, fallbackNow = new Date()) {
  if (!iso) return defaultOccurredAtLocal(fallbackNow);
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return defaultOccurredAtLocal(fallbackNow);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export function resolveBackfillServedById({ canPickServedBy, servedById, currentUserId }) {
  if (!canPickServedBy) {
    return currentUserId ?? null;
  }
  if (servedById) {
    const parsed = parseInt(servedById, 10);
    return Number.isNaN(parsed) ? currentUserId ?? null : parsed;
  }
  return currentUserId ?? null;
}

export function servedByIdForPrefill({ canPickServedBy, payloadServedById, currentUserId }) {
  if (canPickServedBy && payloadServedById) {
    return String(payloadServedById);
  }
  if (currentUserId != null) {
    return String(currentUserId);
  }
  return '';
}

export function canResubmitBackfillChange(change) {
  return (
    change?.status === 'rejected' &&
    change?.action_type === 'sale_backfill'
  );
}

export function parseRejectedBackfillChange(change, { canPickServedBy = false, currentUserId = null } = {}) {
  if (!canResubmitBackfillChange(change)) {
    return { ok: false, error: 'This submission cannot be edited here.' };
  }
  const payload = change.apply_payload || {};
  return {
    ok: true,
    resubmitPendingId: change.id,
    rejectionReason: change.rejection_reason || '',
    prefill: {
      occurredAtLocal: localDatetimeFromIso(payload.occurred_at),
      backfillReason: payload.backfill_reason || change.reason || '',
      saleType: payload.sale_type || 'pos',
      customerId: payload.customer_id ? String(payload.customer_id) : '',
      paymentMethod: payload.payment_method || 'cash',
      paymentReference: payload.payment_reference || '',
      amountPaid: String(payload.amount_paid ?? ''),
      allowPartial: Boolean(payload.allow_partial_payment),
      servedById: servedByIdForPrefill({
        canPickServedBy,
        payloadServedById: payload.served_by_id,
        currentUserId,
      }),
      items: payload.items || [],
    },
  };
}

export function buildBackfillSubmitPayload({
  occurredAt,
  backfillReason,
  saleType,
  canPickServedBy,
  servedById,
  currentUserId,
  customerId,
  paymentMethod,
  paymentReference,
  amountPaid,
  allowPartial,
  ackStockWarnings,
  lines,
  resubmitPendingId,
}) {
  const paid = parseFloat(amountPaid) || 0;
  const payload = {
    occurred_at: toIsoDatetime(occurredAt),
    backfill_reason: String(backfillReason || '').trim(),
    sale_type: saleType,
    served_by_id: resolveBackfillServedById({ canPickServedBy, servedById, currentUserId }),
    customer_id: customerId ? parseInt(customerId, 10) : null,
    payment_method: paymentMethod,
    payment_reference: paymentReference,
    amount_paid: paid,
    allow_partial_payment: allowPartial,
    acknowledge_stock_warnings: ackStockWarnings,
    items: (lines || []).map((row) => ({
      product_id: row.product_id,
      variant_id: row.variant_id ?? undefined,
      quantity: row.quantity,
      unit_price: row.unit_price,
    })),
  };
  if (resubmitPendingId) {
    payload.resubmit_of = resubmitPendingId;
  }
  if (saleType === 'normal') {
    payload.create_invoice = true;
  }
  return payload;
}

export function backfillPendingNavigatePath(resubmitPendingId) {
  return resubmitPendingId ? '/sales/record-past' : '/pending-approvals';
}

export function backfillPendingToastMessage(resubmitPendingId, defaultPendingMessage) {
  return resubmitPendingId
    ? 'Corrected sale sent back for approval.'
    : defaultPendingMessage;
}

export function backfillRejectionSuccessMessage(actionType) {
  if (actionType === 'sale_backfill') {
    return 'Rejected — sent back to staff to fix on Record past sale.';
  }
  return 'Rejected — nothing was changed';
}

export async function linesFromBackfillPayload(items = [], deps) {
  if (!deps?.getProduct || !deps?.getVariants || !deps?.getVariantRowLabel) {
    throw new Error('linesFromBackfillPayload requires product fetch dependencies');
  }
  const { getProduct, getVariants, getVariantRowLabel } = deps;

  const lines = [];
  for (const row of items) {
    let productName = `Product #${row.product_id}`;
    try {
      const product = await getProduct(row.product_id);
      productName = product.name;
      if (row.variant_id) {
        const variants = await getVariants(product.id);
        const variant = variants.find((v) => String(v.id) === String(row.variant_id));
        if (variant) {
          productName = `${product.name} — ${getVariantRowLabel(variant)}`;
        }
      } else if (product.sku) {
        productName = `${product.name} (${product.sku})`;
      }
    } catch {
      // keep fallback label
    }
    lines.push({
      key: `${row.product_id}-${row.variant_id || 'base'}-${lines.length}`,
      product_id: row.product_id,
      variant_id: row.variant_id ?? null,
      product_name: productName,
      quantity: row.quantity,
      unit_price: parseFloat(row.unit_price),
    });
  }
  return lines;
}
