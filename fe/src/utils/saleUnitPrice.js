/**
 * Sale-line unit price overrides (markup at or above catalog selling price).
 * Matches backend accounts.sensitive_edits.validate_sale_unit_price_override.
 *
 * Anyone may raise the line price; nobody may go below the selling price.
 * `mayEditPricing` is kept for call-site compatibility and ignored for the floor.
 */

export function normalizeMoney(value) {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : NaN;
}

/**
 * First finite money amount from candidates (skips null/undefined/'').
 *
 * Args:
 *   ...candidates: Mixed values coercible with parseFloat. Length 0–32.
 *
 * Returns:
 *   number when a finite value is found; otherwise NaN.
 */
export function firstFiniteMoney(...candidates) {
  for (const value of candidates) {
    if (value === null || value === undefined || value === '') continue;
    const n = typeof value === 'number' ? value : parseFloat(value);
    if (Number.isFinite(n)) return n;
  }
  return NaN;
}

/**
 * Catalog selling-price floor for a POS/rectify cart line.
 *
 * Prefers an explicit ``catalog_price`` stamped at hydrate, then catalog
 * ``selling_price``, and only then the charged ``price`` so a marked-up
 * line does not lock the floor at the charged amount.
 *
 * Args:
 *   item: Cart/holding line object (may be null).
 *
 * Returns:
 *   Finite catalog floor in major currency units, or NaN when missing.
 */
export function lineCatalogFloor(item) {
  if (!item || typeof item !== 'object') return NaN;
  return firstFiniteMoney(item.catalog_price, item.selling_price, item.price);
}

/**
 * Whether a requested unit price is allowed.
 * Must be a non-negative number at or above the catalog selling price.
 */
export function isSaleUnitPriceOverrideAllowed({
  catalogPrice,
  requestedPrice,
  mayEditPricing: _mayEditPricing = false,
}) {
  const catalog = normalizeMoney(catalogPrice);
  const requested = normalizeMoney(requestedPrice);
  if (!Number.isFinite(requested) || requested < 0) return false;
  if (!Number.isFinite(catalog)) return false;
  return requested + 1e-9 >= catalog;
}

export function saleUnitPriceOverrideError({
  catalogPrice,
  requestedPrice,
  mayEditPricing: _mayEditPricing = false,
}) {
  const catalog = normalizeMoney(catalogPrice);
  const requested = normalizeMoney(requestedPrice);
  if (!Number.isFinite(requested) || requested < 0) {
    return 'Enter a valid unit price.';
  }
  if (!Number.isFinite(catalog)) {
    return 'Catalog selling price is missing for this item.';
  }
  if (requested + 1e-9 < catalog) {
    return `Unit price cannot be below the selling price (${catalog}).`;
  }
  return null;
}
