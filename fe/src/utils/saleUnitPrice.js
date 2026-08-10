/**
 * Sale-line unit price overrides (markup above catalog selling price).
 * Matches backend accounts.sensitive_edits.validate_sale_unit_price_override.
 */

export function normalizeMoney(value) {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : NaN;
}

/**
 * Whether a requested unit price is allowed for this user.
 * - Managers/pricing editors: any price >= 0
 * - Sales staff: only catalog price or higher (markup / customer-specific charge)
 */
export function isSaleUnitPriceOverrideAllowed({
  catalogPrice,
  requestedPrice,
  mayEditPricing = false,
}) {
  const catalog = normalizeMoney(catalogPrice);
  const requested = normalizeMoney(requestedPrice);
  if (!Number.isFinite(requested) || requested < 0) return false;
  if (mayEditPricing) return true;
  if (!Number.isFinite(catalog)) return false;
  return requested + 1e-9 >= catalog;
}

export function saleUnitPriceOverrideError({
  catalogPrice,
  requestedPrice,
  mayEditPricing = false,
}) {
  const catalog = normalizeMoney(catalogPrice);
  const requested = normalizeMoney(requestedPrice);
  if (!Number.isFinite(requested) || requested < 0) {
    return 'Enter a valid unit price.';
  }
  if (mayEditPricing) return null;
  if (!Number.isFinite(catalog)) {
    return 'Catalog selling price is missing for this item.';
  }
  if (requested + 1e-9 < catalog) {
    return `Unit price cannot be below the selling price (${catalog}). Ask a manager to discount.`;
  }
  return null;
}
