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
