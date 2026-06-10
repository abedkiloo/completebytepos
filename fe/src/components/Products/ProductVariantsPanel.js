import React, { useCallback, useEffect, useRef, useState } from 'react';
import { variantsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import PendingApprovalBadges from '../Approvals/PendingApprovalBadges';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  extractApiReasonError,
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  pendingApprovalToastMessage,
  variantEditNeedsReason,
} from '../../utils/makerChecker';

function variantLabel(variant) {
  const parts = [];
  if (variant.size_name) parts.push(variant.size_name);
  if (variant.color_name) parts.push(variant.color_name);
  return parts.length ? parts.join(' / ') : variant.sku || `Variant #${variant.id}`;
}

function buildVariantPayload(draft) {
  return {
    price: draft.price === '' ? null : draft.price,
    stock_quantity: parseInt(draft.stock_quantity, 10) || 0,
    is_active: draft.is_active,
  };
}

export default function ProductVariantsPanel({ productId }) {
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);
  const [variants, setVariants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [edits, setEdits] = useState({});
  const [reasons, setReasons] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [reasonFocusId, setReasonFocusId] = useState(null);
  const reasonRefs = useRef({});

  const load = useCallback(async () => {
    if (!productId) return;
    setLoading(true);
    try {
      const res = await variantsAPI.getByProduct(productId);
      const rows = res.data.results || res.data || [];
      setVariants(Array.isArray(rows) ? rows : []);
      const nextEdits = {};
      rows.forEach((v) => {
        nextEdits[v.id] = {
          price: v.price ?? v.selling_price ?? '',
          stock_quantity: v.stock_quantity ?? 0,
          is_active: v.is_active !== false,
        };
      });
      setEdits(nextEdits);
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
    if (reasonFocusId && reasonRefs.current[reasonFocusId]) {
      reasonRefs.current[reasonFocusId].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [reasonFocusId]);

  const updateEdit = (id, field, value) => {
    setEdits((prev) => ({
      ...prev,
      [id]: { ...prev[id], [field]: value },
    }));
  };

  const saveVariant = async (variant) => {
    const draft = edits[variant.id];
    if (!draft) return;
    const payload = buildVariantPayload(draft);
    const needsReason = makerCheckerOn && variantEditNeedsReason(payload, variant);
    const reason = (reasons[variant.id] || '').trim();
    if (needsReason && !reason) {
      setReasonFocusId(variant.id);
      toast.warning('Enter a reason below — price, stock, or status changes need approval.');
      return;
    }
    if (needsReason) {
      payload.reason = reason;
    }
    setBusyId(variant.id);
    try {
      const res = await variantsAPI.update(variant.id, payload);
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(pendingApprovalToastMessage());
      } else {
        toast.success('Variant updated');
      }
      setReasons((prev) => ({ ...prev, [variant.id]: '' }));
      setReasonFocusId(null);
      load();
    } catch (err) {
      const msg =
        extractApiReasonError(err.response?.data) ||
        err.response?.data?.error ||
        'Failed to update variant';
      toast.error(msg);
      if (/reason/i.test(msg)) {
        setReasonFocusId(variant.id);
      }
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading variants…</p>;
  }
  if (!variants.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No variant rows yet. Save size/color selections on the product to generate variants.
      </p>
    );
  }

  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <p className="text-sm font-medium">Variant prices &amp; stock</p>
      <p className="text-xs text-muted-foreground">
        Edit each size/color row separately. Changing price, stock, or active status may require
        approval when maker-checker is on.
      </p>
      <div className="space-y-4">
        {variants.map((variant) => {
          const draft = edits[variant.id] || {};
          const payload = buildVariantPayload(draft);
          const needsReason =
            makerCheckerOn && variantEditNeedsReason(payload, variant);
          return (
            <div
              key={variant.id}
              className="space-y-3 rounded border border-border/80 bg-muted/20 p-3"
            >
              <div>
                <span className="text-sm font-medium">{variantLabel(variant)}</span>
                <span className="ml-2 text-xs text-muted-foreground">{variant.sku}</span>
                <PendingApprovalBadges
                  pendingApproval={variant.pending_approval}
                  className="ml-2"
                />
              </div>

              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label className="text-xs text-muted-foreground">Price (KES)</label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={draft.price ?? ''}
                    onChange={(e) => updateEdit(variant.id, 'price', e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Stock</label>
                  <Input
                    type="number"
                    min="0"
                    value={draft.stock_quantity ?? 0}
                    onChange={(e) => updateEdit(variant.id, 'stock_quantity', e.target.value)}
                  />
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={draft.is_active !== false}
                      onChange={(e) => updateEdit(variant.id, 'is_active', e.target.checked)}
                    />
                    Active
                  </label>
                </div>
              </div>

              {needsReason ? (
                <div
                  ref={(el) => {
                    reasonRefs.current[variant.id] = el;
                  }}
                  className="rounded-md border border-amber-200/80 bg-amber-50/30 p-1 dark:border-amber-900 dark:bg-amber-950/20"
                >
                  <ChangeReasonField
                    context="catalog"
                    value={reasons[variant.id] || ''}
                    onChange={(v) =>
                      setReasons((prev) => ({ ...prev, [variant.id]: v }))
                    }
                  />
                </div>
              ) : null}

              <div className="flex justify-end">
                <Button
                  type="button"
                  size="sm"
                  disabled={busyId === variant.id}
                  onClick={() => saveVariant(variant)}
                >
                  {busyId === variant.id
                    ? 'Saving…'
                    : needsReason
                      ? 'Submit for approval'
                      : 'Save variant'}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
