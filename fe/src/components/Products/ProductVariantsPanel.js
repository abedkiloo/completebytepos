import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { variantsAPI } from '../../services/api';
import { formatApiError } from '../../utils/apiErrors';
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
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  pendingApprovalToastMessage,
  variantEditNeedsReason,
  stockReasonValidationMessage,
} from '../../utils/makerChecker';
import {
  buildVariantPatchPayload,
  editableNumericString,
  variantDraftNumericValidationMessage,
  variantFinancialValidationMessage,
} from '../../utils/variantPayload';
import {
  STOCK_OPENING_LABEL,
  STOCK_OPENING_HINT,
} from '../../utils/productDisplay';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import VariantDraftSummary from './VariantDraftSummary';

function draftSizeId(draft, row) {
  if (draft?.size_id !== undefined && draft.size_id !== '') {
    return draft.size_id ? Number(draft.size_id) : null;
  }
  return row?.sizeId ?? null;
}

function draftColorId(draft, row) {
  if (draft?.color_id !== undefined && draft.color_id !== '') {
    return draft.color_id ? Number(draft.color_id) : null;
  }
  return row?.colorId ?? null;
}

function labelForParts(sizeId, colorId, sizes, colors) {
  const size = sizeId ? sizes.find((s) => Number(s.id) === Number(sizeId)) : null;
  const color = colorId ? colors.find((c) => Number(c.id) === Number(colorId)) : null;
  const parts = [size?.name, color?.name].filter(Boolean);
  return parts.length ? parts.join(' / ') : 'Variant';
}

export default function ProductVariantsPanel({
  productId,
  sizes = [],
  colors = [],
  canEditPrice = true,
  canEditMrp = false,
  canEditStock = true,
  canEditCost = false,
  defaultLowStockThreshold = 10,
  onDraftsChange,
  onCombinationKeysChange,
}) {
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);
  const isProductEdit = Boolean(productId);
  const allowStockInput = canEditStock && !isProductEdit;
  const [variants, setVariants] = useState([]);
  const [loading, setLoading] = useState(Boolean(productId));
  const [combinationKeys, setCombinationKeys] = useState([]);
  const [edits, setEdits] = useState({});
  const [reasons, setReasons] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [reasonFocusId, setReasonFocusId] = useState(null);
  const [pickSizeId, setPickSizeId] = useState('');
  const [pickColorId, setPickColorId] = useState('');
  const [pendingConfigSave, setPendingConfigSave] = useState(null);
  const [pendingRemoveKey, setPendingRemoveKey] = useState(null);
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
          price: editableNumericString(v.price ?? v.selling_price),
          mrp: editableNumericString(v.mrp),
          cost: editableNumericString(v.cost),
          stock_quantity: editableNumericString(v.stock_quantity),
          low_stock_threshold: editableNumericString(
            v.low_stock_threshold ?? defaultLowStockThreshold
          ),
          is_active: v.is_active !== false,
          size_id: v.size != null ? String(v.size) : '',
          color_id: v.color != null ? String(v.color) : '',
        };
      });
      return next;
    });
  }, [productId, variants, loading, defaultLowStockThreshold]);

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
        mrp: '',
        cost: '',
        stock_quantity: '',
        low_stock_threshold: String(defaultLowStockThreshold ?? ''),
        is_active: true,
        size_id: sizeId ? String(sizeId) : '',
        color_id: colorId ? String(colorId) : '',
      },
    }));
    setPickSizeId('');
    setPickColorId('');
  };

  const remappingDraftKey = (oldKey, newKey, patch = {}) => {
    if (oldKey === newKey) {
      setEdits((prev) => ({
        ...prev,
        [oldKey]: { ...prev[oldKey], ...patch },
      }));
      return false;
    }
    if (combinationKeys.includes(newKey)) {
      toast.warning('That size / color combination is already configured.');
      return false;
    }
    setCombinationKeys((prev) => prev.map((k) => (k === oldKey ? newKey : k)));
    setEdits((prev) => {
      const next = { ...prev };
      next[newKey] = { ...prev[oldKey], ...patch };
      delete next[oldKey];
      return next;
    });
    setReasons((prev) => {
      if (!(oldKey in prev)) return prev;
      const next = { ...prev };
      next[newKey] = prev[oldKey];
      delete next[oldKey];
      return next;
    });
    return true;
  };

  const changeRowSize = (row, nextSizeId) => {
    const draft = edits[row.key] || {};
    const sizeId = nextSizeId ? Number(nextSizeId) : null;
    const colorId = draftColorId(draft, row);
    const newKey = combinationKeyFromParts(sizeId, colorId);
    // Saved variants keep their key until save succeeds (variant still has old size/color).
    if (row.variant) {
      if (newKey !== row.key && combinationKeys.includes(newKey)) {
        toast.warning('That size / color combination is already configured.');
        return;
      }
      updateEdit(row.key, 'size_id', nextSizeId || '');
      return;
    }
    remappingDraftKey(row.key, newKey, { size_id: nextSizeId || '' });
  };

  const changeRowColor = (row, nextColorId) => {
    const draft = edits[row.key] || {};
    const sizeId = draftSizeId(draft, row);
    const colorId = nextColorId ? Number(nextColorId) : null;
    const newKey = combinationKeyFromParts(sizeId, colorId);
    if (row.variant) {
      if (newKey !== row.key && combinationKeys.includes(newKey)) {
        toast.warning('That size / color combination is already configured.');
        return;
      }
      updateEdit(row.key, 'color_id', nextColorId || '');
      return;
    }
    remappingDraftKey(row.key, newKey, { color_id: nextColorId || '' });
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
    setPendingRemoveKey(null);
  };

  const requestRemoveCombination = (row) => {
    if (row.variant) {
      setPendingRemoveKey(row.key);
      return;
    }
    removeCombination(row.key);
  };

  const commitVariantSave = async (row, draft) => {
    const variant = row.variant;
    if (!variant || !draft) return;

    const nextSizeId = draftSizeId(draft, row);
    const nextColorId = draftColorId(draft, row);
    const nextLabel = labelForParts(nextSizeId, nextColorId, sizes, colors);
    const numericError = variantDraftNumericValidationMessage(draft, {
      label: nextLabel,
      canEditMrp,
      canEditCost,
      allowStockInput,
      stockLabel: isProductEdit ? 'stock on hand' : 'opening stock',
    });
    if (numericError) {
      toast.warning(numericError);
      return;
    }
    const financialError = variantFinancialValidationMessage(draft, {
      label: nextLabel,
      canEditMrp,
      canEditCost,
      requireCost: canEditCost,
    });
    if (financialError) {
      toast.warning(financialError);
      return;
    }

    const payload = buildVariantPatchPayload(variant, {
      ...draft,
      size_id: nextSizeId == null ? '' : String(nextSizeId),
      color_id: nextColorId == null ? '' : String(nextColorId),
    });
    if (isProductEdit) {
      delete payload.stock_quantity;
    }
    if (!Object.keys(payload).length) {
      toast.warning('No changes to save for this variant.');
      return;
    }

    const configChanged = 'size' in payload || 'color' in payload;
    if (configChanged) {
      const newKey = combinationKeyFromParts(nextSizeId, nextColorId);
      const conflict = variants.some(
        (v) => v.id !== variant.id && variantCombinationKey(v) === newKey
      );
      if (conflict || (newKey !== row.key && combinationKeys.includes(newKey))) {
        toast.warning('That size / color combination already exists on this product.');
        return;
      }
    }

    const needsReason = makerCheckerOn && variantEditNeedsReason(payload, variant);
    const reason = (reasons[row.key] || '').trim();
    if (needsReason) {
      const reasonError = stockReasonValidationMessage(reason);
      if (reasonError) {
        setReasonFocusId(row.key);
        toast.warning(
          reasonError === 'A reason is required for stock changes.'
            ? 'Enter a reason below — price, cost, stock, or status changes need approval.'
            : reasonError
        );
        return;
      }
      payload.reason = reason;
    }
    setBusyId(row.key);
    try {
      const res = await variantsAPI.update(variant.id, payload);
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(pendingApprovalToastMessage());
      } else {
        toast.success(configChanged ? 'Variant configuration updated' : 'Variant updated');
      }
      setReasons((prev) => ({ ...prev, [row.key]: '' }));
      setReasonFocusId(null);
      setPendingConfigSave(null);
      if (configChanged) {
        initializedFromServerRef.current = false;
      }
      await load();
    } catch (err) {
      const msg = formatApiError(err, 'Failed to update variant');
      toast.error(msg);
      if (/reason/i.test(msg)) {
        setReasonFocusId(row.key);
      }
    } finally {
      setBusyId(null);
    }
  };

  const saveVariant = async (row) => {
    const variant = row.variant;
    if (!variant) return;
    const draft = edits[row.key];
    if (!draft) return;

    const nextSizeId = draftSizeId(draft, row);
    const nextColorId = draftColorId(draft, row);
    const prevSizeId = row.sizeId ?? null;
    const prevColorId = row.colorId ?? null;
    const configChanged =
      Number(nextSizeId || 0) !== Number(prevSizeId || 0) ||
      Number(nextColorId || 0) !== Number(prevColorId || 0);

    if (configChanged) {
      setPendingConfigSave({
        row,
        draft,
        fromLabel: combinationRowLabel(row),
        toLabel: labelForParts(nextSizeId, nextColorId, sizes, colors),
      });
      return;
    }
    await commitVariantSave(row, draft);
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
          {isProductEdit
            ? 'Price and cost save per row below. To set stock on hand, click the stock quantity on the product row in Products.'
            : `Example: pick Large + White, click Add variant, enter ${STOCK_OPENING_LABEL.toLowerCase()} — then add more rows as needed.`}
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
            const selectedSizeId = draftSizeId(draft, row);
            const selectedColorId = draftColorId(draft, row);
            const draftForPatch = {
              ...draft,
              size_id: selectedSizeId == null ? '' : String(selectedSizeId),
              color_id: selectedColorId == null ? '' : String(selectedColorId),
            };
            const payload = variant ? buildVariantPatchPayload(variant, draftForPatch) : null;
            const needsReason =
              Boolean(variant) && makerCheckerOn && variantEditNeedsReason(payload, variant);
            const label = labelForParts(selectedSizeId, selectedColorId, sizes, colors);
            const configDirty =
              Boolean(variant) &&
              (Number(selectedSizeId || 0) !== Number(row.sizeId || 0) ||
                Number(selectedColorId || 0) !== Number(row.colorId || 0));

            return (
              <div
                key={row.key}
                className="space-y-2 rounded border border-border/80 bg-muted/20 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">{label}</p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="shrink-0 text-destructive hover:text-destructive"
                    onClick={() => requestRemoveCombination(row)}
                  >
                    Remove
                  </Button>
                </div>

                <div className="flex flex-wrap items-end gap-2">
                  {hasSizes ? (
                    <div className="form-group min-w-[8rem] flex-1">
                      <label className="text-xs text-muted-foreground" htmlFor={`variant-size-${row.key}`}>
                        Size
                      </label>
                      <select
                        id={`variant-size-${row.key}`}
                        value={selectedSizeId ? String(selectedSizeId) : ''}
                        onChange={(e) => changeRowSize(row, e.target.value)}
                        className="w-full"
                        data-testid={`variant-size-${row.key}`}
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
                      <label className="text-xs text-muted-foreground" htmlFor={`variant-color-${row.key}`}>
                        Color
                      </label>
                      <select
                        id={`variant-color-${row.key}`}
                        value={selectedColorId ? String(selectedColorId) : ''}
                        onChange={(e) => changeRowColor(row, e.target.value)}
                        className="w-full"
                        data-testid={`variant-color-${row.key}`}
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
                </div>
                {configDirty ? (
                  <p className="text-xs text-amber-800 dark:text-amber-200">
                    Size/color changed — click Save variant and confirm to apply.
                  </p>
                ) : null}
                <p className="text-[11px] text-muted-foreground">
                  Need a new size like “Single puller”? Add or rename it under Sizes &amp; colors first,
                  then pick it here.
                </p>

                <div className="flex flex-wrap items-end gap-2">
                  {canEditMrp ? (
                    <div className="w-[6.75rem] shrink-0">
                      <label className="text-xs text-muted-foreground">MRP (KES)</label>
                      <Input
                        type="text"
                        inputMode="decimal"
                        className="h-9"
                        value={editableNumericString(draft.mrp)}
                        onChange={(e) => updateEdit(row.key, 'mrp', e.target.value)}
                        placeholder="List price"
                      />
                    </div>
                  ) : null}
                  {canEditPrice ? (
                    <div className="w-[6.75rem] shrink-0">
                      <label
                        className="text-xs text-muted-foreground"
                        htmlFor={`variant-price-${row.key}`}
                      >
                        Price (KES)
                      </label>
                      <Input
                        id={`variant-price-${row.key}`}
                        type="text"
                        inputMode="decimal"
                        className="h-9"
                        value={editableNumericString(draft.price)}
                        onChange={(e) => updateEdit(row.key, 'price', e.target.value)}
                      />
                    </div>
                  ) : null}
                  {canEditCost ? (
                    <div className="w-[6.75rem] shrink-0">
                      <label className="text-xs text-muted-foreground">Cost (KES)</label>
                      <Input
                        type="text"
                        inputMode="decimal"
                        className="h-9"
                        value={editableNumericString(draft.cost)}
                        onChange={(e) => updateEdit(row.key, 'cost', e.target.value)}
                      />
                    </div>
                  ) : null}
                  {allowStockInput ? (
                    <div className="w-[5.5rem] shrink-0">
                      <label
                        className="text-xs text-muted-foreground"
                        htmlFor={`variant-stock-${row.key}`}
                      >
                        {STOCK_OPENING_LABEL}
                      </label>
                      <Input
                        id={`variant-stock-${row.key}`}
                        type="text"
                        inputMode="numeric"
                        className="h-9"
                        value={editableNumericString(draft.stock_quantity)}
                        onChange={(e) => updateEdit(row.key, 'stock_quantity', e.target.value)}
                        title={STOCK_OPENING_HINT}
                      />
                    </div>
                  ) : null}
                  <div className="w-[5.5rem] shrink-0">
                    <label
                      className="text-xs text-muted-foreground"
                      htmlFor={`variant-threshold-${row.key}`}
                    >
                      Low stock at
                    </label>
                    <Input
                      id={`variant-threshold-${row.key}`}
                      type="text"
                      inputMode="numeric"
                      className="h-9"
                      value={editableNumericString(draft.low_stock_threshold)}
                      onChange={(e) => updateEdit(row.key, 'low_stock_threshold', e.target.value)}
                      title="Alert when this variant falls to this quantity or below"
                    />
                  </div>
                  {variant ? (
                    <label className="form-inline-checkbox shrink-0 self-end">
                      <input
                        type="checkbox"
                        className="form-inline-checkbox__input"
                        checked={draft.is_active !== false}
                        onChange={(e) => updateEdit(row.key, 'is_active', e.target.checked)}
                      />
                      <span>Active</span>
                    </label>
                  ) : null}
                  {variant ? (
                    <Button
                      type="button"
                      size="sm"
                      className="h-9 shrink-0"
                      disabled={busyId === row.key}
                      onClick={() => saveVariant(row)}
                    >
                      {busyId === row.key
                        ? 'Saving…'
                        : needsReason
                          ? 'Submit for approval'
                          : configDirty
                            ? 'Save configuration'
                            : 'Save variant'}
                    </Button>
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
                      minLength={5}
                      value={reasons[row.key] || ''}
                      onChange={(v) => setReasons((prev) => ({ ...prev, [row.key]: v }))}
                    />
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        isOpen={Boolean(pendingConfigSave)}
        type="warning"
        title="Change variant configuration?"
        message={
          pendingConfigSave
            ? `Update this variant from “${pendingConfigSave.fromLabel}” to “${pendingConfigSave.toLabel}”? Stock and sales history stay on this variant; only the size/color label changes.`
            : ''
        }
        confirmText="Confirm & save"
        cancelText="Cancel"
        busy={Boolean(pendingConfigSave && busyId === pendingConfigSave.row.key)}
        onCancel={() => {
          if (!busyId) setPendingConfigSave(null);
        }}
        onConfirm={() => {
          if (!pendingConfigSave) return;
          commitVariantSave(pendingConfigSave.row, pendingConfigSave.draft);
        }}
      />

      <ConfirmDialog
        isOpen={Boolean(pendingRemoveKey)}
        type="danger"
        title="Remove this variant from the list?"
        message="Confirm to drop this size/color row from the product form. The saved variant record is not deleted until you manage stock separately."
        confirmText="Remove"
        cancelText="Cancel"
        onCancel={() => setPendingRemoveKey(null)}
        onConfirm={() => {
          if (pendingRemoveKey) removeCombination(pendingRemoveKey);
        }}
      />
    </div>
  );
}
