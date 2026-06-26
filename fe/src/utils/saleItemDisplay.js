import { cartVariantLabel } from './variantCombinations';

/** Human-readable variant label for a sale line item. */
export function saleItemVariantLabel(item) {
  if (!item) return '';
  const variantId = item.variant_id ?? item.variant;
  return cartVariantLabel({
    variant_id: variantId,
    variant:
      variantId != null
        ? typeof item.variant === 'object' && item.variant !== null
          ? item.variant
          : {
              id: variantId,
              size_name: item.size_name,
              color_name: item.color_name,
            }
        : null,
    size_name: item.size_name,
    color_name: item.color_name,
  });
}

/** Quantity already returned on this line. */
export function saleItemQuantityRefunded(item) {
  if (!item) return 0;
  return parseInt(item.quantity_refunded, 10) || 0;
}

/** Quantity still considered sold after refunds. */
export function saleItemNetQuantity(item) {
  if (!item) return 0;
  const sold = parseInt(item.quantity, 10) || 0;
  return Math.max(0, sold - saleItemQuantityRefunded(item));
}

/** Line subtotal after refunds (unit price × net qty). */
export function saleItemNetSubtotal(item) {
  if (!item) return 0;
  const unit = parseFloat(item.unit_price ?? 0);
  return unit * saleItemNetQuantity(item);
}

export function saleAmountRefunded(sale) {
  return parseFloat(sale?.amount_refunded ?? 0) || 0;
}

/** Sale total after refunds — the effective revenue kept on this sale. */
export function saleNetTotal(sale) {
  const total = parseFloat(sale?.total ?? 0);
  const refunded = saleAmountRefunded(sale);
  return Math.max(0, total - refunded);
}

/** Sum of net item quantities across all lines. */
export function saleNetItemCount(sale) {
  return (sale?.items || []).reduce((sum, item) => sum + saleItemNetQuantity(item), 0);
}

export function saleHasRefundActivity(sale) {
  return saleAmountRefunded(sale) > 0.009 || sale?.refund_status === 'partial' || sale?.refund_status === 'refunded';
}

/** Human-readable final sale state for lists and receipts. */
export function saleFinalStatusLabel(sale) {
  if (sale?.refund_status === 'refunded' || saleNetTotal(sale) <= 0.009) {
    return 'Fully refunded';
  }
  if (saleHasRefundActivity(sale)) {
    return 'Partial refund';
  }
  return salePaymentStatusLabel(sale);
}

/** Primary amount to show in sale lists — net after refunds. */
export function saleDisplayTotal(sale) {
  return saleHasRefundActivity(sale) ? saleNetTotal(sale) : parseFloat(sale?.total ?? 0);
}

/** Item/unit count for lists — remaining qty after refunds when line data is present. */
export function saleDisplayItemCount(sale) {
  if (sale?.items?.length) {
    return saleNetItemCount(sale);
  }
  return parseInt(sale?.item_count, 10) || 0;
}

/** Remaining quantity that can still be refunded on this line. */
export function saleItemRefundableQuantity(item) {
  if (!item) return 0;
  if (item.refundable_quantity != null) {
    return parseInt(item.refundable_quantity, 10) || 0;
  }
  const refunded = parseInt(item.quantity_refunded, 10) || 0;
  const sold = parseInt(item.quantity, 10) || 0;
  return Math.max(0, sold - refunded);
}

/** Outstanding balance when customer paid less than sale total. */
export function saleBalanceDue(sale) {
  const total = parseFloat(sale?.total ?? 0);
  const paid = parseFloat(sale?.amount_paid ?? 0);
  const due = total - paid;
  return due > 0.009 ? due : 0;
}

export function salePaymentStatusLabel(sale) {
  const total = parseFloat(sale?.total ?? 0);
  const paid = parseFloat(sale?.amount_paid ?? 0);
  if (paid >= total - 0.009) return 'Paid in full';
  if (paid > 0) return 'Partial payment';
  return 'Unpaid';
}

/** Balance due against the current (post-refund) sale total. */
export function saleNetBalanceDue(sale) {
  const total = saleNetTotal(sale);
  const paid = parseFloat(sale?.amount_paid ?? 0);
  const due = total - paid;
  return due > 0.009 ? due : 0;
}

export function saleNetPaymentStatusLabel(sale) {
  const total = saleNetTotal(sale);
  const paid = parseFloat(sale?.amount_paid ?? 0);
  if (paid >= total - 0.009) return 'Paid in full';
  if (paid > 0) return 'Partial payment';
  return 'Unpaid';
}

/**
 * Receipt-ready sale: drops fully returned lines and uses net qty/amounts only.
 * No refund wording — looks like a normal completed sale.
 */
export function normalizeSaleForReceipt(sale) {
  if (!sale) return null;

  const hasRefund = saleHasRefundActivity(sale);
  const items = (sale.items || [])
    .map((item) => {
      const qty = saleItemNetQuantity(item);
      const subtotal = saleItemNetSubtotal(item);
      return { ...item, quantity: qty, subtotal };
    })
    .filter((item) => item.quantity > 0);

  if (!hasRefund) {
    const total = parseFloat(sale.total) || 0;
    const amountPaid = parseFloat(sale.amount_paid) || 0;
    return {
      ...sale,
      items,
      subtotal: parseFloat(sale.subtotal) || 0,
      tax_amount: parseFloat(sale.tax_amount) || 0,
      discount_amount: parseFloat(sale.discount_amount) || 0,
      delivery_cost: parseFloat(sale.delivery_cost) || 0,
      total,
      amount_paid: amountPaid,
      change: Math.max(0, amountPaid - total),
    };
  }

  const lineSubtotal = items.reduce((sum, item) => sum + item.subtotal, 0);
  const originalSubtotal = parseFloat(sale.subtotal) || parseFloat(sale.total) || 0;
  const ratio = originalSubtotal > 0.009 ? lineSubtotal / originalSubtotal : 0;

  const taxAmount = (parseFloat(sale.tax_amount) || 0) * ratio;
  const discountAmount = (parseFloat(sale.discount_amount) || 0) * ratio;
  const deliveryCost = (parseFloat(sale.delivery_cost) || 0) * ratio;
  const total = Math.max(0, lineSubtotal - discountAmount + taxAmount + deliveryCost);

  const amountPaidRaw = parseFloat(sale.amount_paid) || 0;
  const amountPaid = Math.min(amountPaidRaw, total);

  return {
    ...sale,
    items,
    subtotal: lineSubtotal,
    tax_amount: taxAmount,
    discount_amount: discountAmount,
    delivery_cost: deliveryCost,
    total,
    amount_paid: amountPaid,
    change: Math.max(0, amountPaid - total),
  };
}
