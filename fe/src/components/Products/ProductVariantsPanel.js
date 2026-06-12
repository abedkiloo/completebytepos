import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { variantsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import PendingApprovalBadges from '../Approvals/PendingApprovalBadges';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  buildRowFromKey,
  combinationKeyFromParts,
  combinationRowLabel,
  variantCombinationKey,
} from '../../utils/variantCombinations';
import {
  extractApiReasonError,
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  pendingApprovalToastMessage,
  variantEditNeedsReason,
} from '../../utils/makerChecker';
import { buildVariantPatchPayload } from '../../utils/variantPayload';
import VariantDraftSummary from './VariantDraftSummary';

export default function ProductVariantsPanel({
  productId,
  sizes = [],
  colors = [],
  canEditPrice = true,
  canEditStock = true,
  onDraftsChange,
  onCombinationKeysChange,
}) {
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);
  const [variants, setVariants] = useState([]);
  const [loading, setLoading] = useState(Boolean(productId));
  const [combinationKeys, setCombinationKeys] = useState([]);
  const [edits, setEdits] = useState({});
  const [reasons, setReasons] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [reasonFocusId, setReasonFocusId] = useState(null);
  const [pickSizeId, setPickSizeId] = useState('');
  const [pickColorId, setPickColorId] = useState('');
  const reasonRefs = useRef({});
  const initializedFromServerRef = useRef(false);

  const hasSizes = sizes.length > 0;
  const hasColors = colors.length > 0;

  const rows = useMemo(
    () => combinationKeys.map((key) => buildRowFromKey(key, variants, sizes, colors)),
    [combinationKeys, variants, sizes, colors]
  );

  const load = useCallback(async () => {
    if (!productId) {
      setVariants([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await variantsAPI.getByProduct(productId);
      const list = res.data.results || res.data || [];
      setVariants(Array.isArray(list) ? list : []);
    } catch {
      toast.error('Could not load variants');
      setVariants([]);
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!productId) {
      initializedFromServerRef.current = false;
      return;
    }
    if (loading || initializedFromServerRef.current || !variants.length) {
      return;
    }
    initializedFromServerRef.current = true;
    const keys = variants.map((v) => variantCombinationKey(v));
    setCombinationKeys(keys);
    setEdits((prev) => {
      const next = { ...prev };
      variants.forEach((v) => {
        const key = variantCombinationKey(v);
        next[key] = {
          price: v.price ?? v.selling_price ?? '',
          stock_quantity: v.stock_quantity ?? 0,
          is_active: v.is_active !== false,
        };
      });
      return next;
    });
  }, [productId, variants, loading]);

  const draftsByKey = useMemo(() => {
    const map = {};
    combinationKeys.forEach((key) => {
      if (edits[key]) {
        map[key] = edits[key];
      }
    });
    return map;
  }, [combinationKeys, edits]);

  useEffect(() => {
    onDraftsChange?.(draftsByKey);
  }, [draftsByKey, onDraftsChange]);

  useEffect(() => {
    onCombinationKeysChange?.(combinationKeys);
  }, [combinationKeys, onCombinationKeysChange]);

  useEffect(() => {
    if (reasonFocusId && reasonRefs.current[reasonFocusId]) {
      reasonRefs.current[reasonFocusId].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [reasonFocusId]);

  const updateEdit = (key, field, value) => {
    setEdits((prev) => ({
      ...prev,
      [key]: { ...prev[key], [field]: value },
    }));
  };

  const addCombination = () => {
    const sizeId = pickSizeId ? Number(pickSizeId) : null;
    const colorId = pickColorId ? Number(pickColorId) : null;
    if (!sizeId && !colorId) {
      toast.warning('Choose a size and/or color, then click Add variant.');
      return;
    }
    if (hasSizes && !sizeId && hasColors && !colorId) {
      toast.warning('Choose at least a size or a color.');
      return;
    }
    const key = combinationKeyFromParts(sizeId, colorId);
    if (combinationKeys.includes(key)) {
      toast.info('That variant is already in the list.');
      return;
    }
    setCombinationKeys((prev) => [...prev, key]);
    setEdits((prev) => ({
      ...prev,
      [key]: prev[key] || {
        price: '',
        stock_quantity: '',
        is_active: true,
      },
    }));
    setPickSizeId('');
    setPickColorId('');
  };

  const removeCombination = (key) => {
    setCombinationKeys((prev) => prev.filter((k) => k !== key));
    setEdits((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setReasons((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const saveVariant = async (row) => {
    const variant = row.variant;
    if (!variant) return;
    const draft = edits[row.key];
    if (!draft) return;
    const payload = buildVariantPatchPayload(variant, draft);
    if (!Object.keys(payload).length) {
      toast.warning('No changes to save for this variant.');
      return;
    }
    const needsReason = makerCheckerOn && variantEditNeedsReason(payload, variant);
    const reason = (reasons[row.key] || '').trim();
    if (needsReason && !reason) {
      setReasonFocusId(row.key);
      toast.warning('Enter a reason below — price, stock, or status changes need approval.');
      return;
    }
    if (needsReason) {
      payload.reason = reason;
    }
    setBusyId(row.key);
    try {
      const res = await variantsAPI.update(variant.id, payload);
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(pendingApprovalToastMessage());
      } else {
        toast.success('Variant updated');
      }
      setReasons((prev) => ({ ...prev, [row.key]: '' }));
      setReasonFocusId(null);
      load();
    } catch (err) {
      const msg =
        extractApiReasonError(err.response?.data) ||
        err.response?.data?.error ||
        'Failed to update variant';
      toast.error(msg);
      if (/reason/i.test(msg)) {
        setReasonFocusId(row.key);
      }
    } finally {
      setBusyId(null);
    }
  };

  if (!hasSizes && !hasColors) {
    return (
      <p className="text-sm text-muted-foreground">
        Add sizes and/or colors under Sizes &amp; colors, then return here to build variants.
      </p>
    );
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading variants…</p>;
  }

  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <div className="rounded-md border border-dashed border-border/80 bg-muted/10 p-3">
        <p className="mb-2 text-sm font-medium">Add a variant combination</p>
        <div className="flex flex-wrap items-end gap-2">
          {hasSizes ? (
            <div className="form-group min-w-[8rem] flex-1">
              <label className="text-xs text-muted-foreground">Size</label>
              <select
                value={pickSizeId}
                onChange={(e) => setPickSizeId(e.target.value)}
                className="w-full"
              >
                <option value="">— Size —</option>
                {sizes.map((size) => (
                  <option key={size.id} value={String(size.id)}>
                    {size.name} ({size.code})
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {hasColors ? (
            <div className="form-group min-w-[8rem] flex-1">
              <label className="text-xs text-muted-foreground">Color</label>
              <select
                value={pickColorId}
                onChange={(e) => setPickColorId(e.target.value)}
                className="w-full"
              >
                <option value="">— Color —</option>
                {colors.map((color) => (
                  <option key={color.id} value={String(color.id)}>
                    {color.name}
                    {color.hex_code ? ` (${color.hex_code})` : ''}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <Button type="button" size="sm" onClick={addCombination}>
            Add variant
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Example: pick Large + White, click Add variant, enter stock — then add Medium + Blue as
          another row. Remove any row before saving if you change your mind.
        </p>
      </div>

      <VariantDraftSummary
        draftsByKey={draftsByKey}
        sizes={sizes}
        colors={colors}
        compact
      />

      {!rows.length ? (
        <p className="text-sm text-muted-foreground">
          No variants yet. Use the picker above to add your first combination.
        </p>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => {
            const draft = edits[row.key] || {};
            const variant = row.variant;
            const payload = variant ? buildVariantPatchPayload(variant, draft) : null;
            const needsReason =
              Boolean(variant) && makerCheckerOn && variantEditNeedsReason(payload, variant);
            const label = combinationRowLabel(row);

            return (
              <div
                key={row.key}
                className="space-y-3 rounded border border-border/80 bg-muted/20 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium">{label}</p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="shrink-0 text-destructive hover:text-destructive"
                    onClick={() => removeCombination(row.key)}
                  >
                    Remove
                  </Button>
                </div>

                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {canEditPrice ? (
                    <div>
                      <label className="text-xs text-muted-foreground">Price (KES)</label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        value={draft.price ?? ''}
                        onChange={(e) => updateEdit(row.key, 'price', e.target.value)}
                      />
                    </div>
                  ) : null}
                  {canEditStock ? (
                    <div>
                      <label className="text-xs text-muted-foreground">Stock</label>
                      <Input
                        type="number"
                        min="0"
                        value={draft.stock_quantity ?? ''}
                        onChange={(e) => updateEdit(row.key, 'stock_quantity', e.target.value)}
                      />
                    </div>
                  ) : null}
                  {variant ? (
                    <div className="flex items-end">
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={draft.is_active !== false}
                          onChange={(e) => updateEdit(row.key, 'is_active', e.target.checked)}
                        />
                        Active
                      </label>
                    </div>
                  ) : null}
                </div>

                {!variant ? (
                  <p className="text-xs text-muted-foreground">
                    Saved when you create or update the product.
                  </p>
                ) : null}

                {variant ? (
                  <PendingApprovalBadges pendingApproval={variant.pending_approval} />
                ) : null}

                {needsReason ? (
                  <div
                    ref={(el) => {
                      reasonRefs.current[row.key] = el;
                    }}
                    className="rounded-md border border-amber-200/80 bg-amber-50/30 p-1 dark:border-amber-900 dark:bg-amber-950/20"
                  >
                    <ChangeReasonField
                      context="catalog"
                      value={reasons[row.key] || ''}
                      onChange={(v) => setReasons((prev) => ({ ...prev, [row.key]: v }))}
                    />
                  </div>
                ) : null}

                {variant ? (
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      disabled={busyId === row.key}
                      onClick={() => saveVariant(row)}
                    >
                      {busyId === row.key
                        ? 'Saving…'
                        : needsReason
                          ? 'Submit for approval'
                          : 'Save variant'}
                    </Button>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
