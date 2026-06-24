import { variantsAPI } from '../services/api';
import {
  buildRowFromKey,
  variantCombinationKey,
  variantDisplayLabel,
} from './variantCombinations';
import { buildVariantPatchPayload } from './variantPayload';
import { formatApiError } from './apiErrors';
import { variantEditNeedsReason } from './makerChecker';

/**
 * True when post-save variant draft PATCHes would need a maker-checker reason.
 */
export function variantDraftsApplyNeedsReason(
  draftsByKey,
  combinationKeys,
  { product, variants = [], sizes = [], colors = [] } = {}
) {
  if (!draftsByKey || !combinationKeys?.length) return false;

  const productDefaults = {
    price: product?.price ?? product?.selling_price,
    mrp: product?.mrp ?? product?.price,
    cost: product?.cost,
    stock_quantity: 0,
    is_active: true,
  };

  for (const key of combinationKeys) {
    const draft = draftsByKey[key];
    if (!draft) continue;
    const row = buildRowFromKey(key, variants, sizes, colors);
    const baseline = row.variant || productDefaults;
    const payload = buildVariantPatchPayload(baseline, draft);
    if (variantEditNeedsReason(payload, baseline)) return true;
  }
  return false;
}

/**
 * After product save creates/regenerates variant rows, apply price/stock the user entered.
 * @param {number} productId
 * @param {Record<string, { price?: string|number|null, stock_quantity?: string|number, is_active?: boolean }>} draftsByKey
 */
export async function applyVariantDraftsAfterProductSave(
  productId,
  draftsByKey,
  { includeStock = true, reason = '' } = {}
) {
  if (!productId || !draftsByKey || !Object.keys(draftsByKey).length) {
    return { applied: 0 };
  }

  const res = await variantsAPI.getByProduct(productId);
  const variants = res.data?.results || res.data || [];
  if (!Array.isArray(variants) || !variants.length) {
    return { applied: 0 };
  }

  const trimmedReason = String(reason || '').trim();
  let applied = 0;
  for (const variant of variants) {
    const key = variantCombinationKey(variant);
    const draft = draftsByKey[key];
    if (!draft) continue;

    const payload = buildVariantPatchPayload(variant, draft);
    if (!includeStock) {
      delete payload.stock_quantity;
    }
    if (!Object.keys(payload).length) continue;
    if (trimmedReason) {
      payload.reason = trimmedReason;
    }
    try {
      await variantsAPI.update(variant.id, payload);
      applied += 1;
    } catch (err) {
      const label = variantDisplayLabel(variant);
      const detail = formatApiError(err, 'Failed to update variant');
      throw new Error(`${label}: ${detail}`);
    }
  }

  return { applied };
}
