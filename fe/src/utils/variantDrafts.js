import { variantsAPI } from '../services/api';
import { variantCombinationKey, variantDisplayLabel } from './variantCombinations';
import { buildVariantDraftPatchPayload } from './variantPayload';
import { formatApiError } from './apiErrors';

/**
 * After product save creates/regenerates variant rows, apply price/stock the user entered.
 * @param {number} productId
 * @param {Record<string, { price?: string|number|null, stock_quantity?: string|number, is_active?: boolean }>} draftsByKey
 */
export async function applyVariantDraftsAfterProductSave(
  productId,
  draftsByKey,
  { includeStock = true } = {}
) {
  if (!productId || !draftsByKey || !Object.keys(draftsByKey).length) {
    return { applied: 0 };
  }

  const res = await variantsAPI.getByProduct(productId);
  const variants = res.data?.results || res.data || [];
  if (!Array.isArray(variants) || !variants.length) {
    return { applied: 0 };
  }

  let applied = 0;
  for (const variant of variants) {
    const key = variantCombinationKey(variant);
    const draft = draftsByKey[key];
    if (!draft) continue;

    const payload = buildVariantDraftPatchPayload(draft);
    if (!includeStock) {
      delete payload.stock_quantity;
    }
    if (!Object.keys(payload).length) continue;
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
