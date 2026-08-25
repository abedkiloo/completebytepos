import React, { useState, useEffect, useMemo, useRef } from 'react';
import { inventoryAPI, variantsAPI } from '../../services/api';
import SearchableSelect from '../Shared/SearchableSelect';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import { toast } from '../../utils/toast';
import { variantDisplayLabel } from '../../utils/variantCombinations';
import {
  fetchTrackedStockProducts,
  findProductById,
  toStockProductSelectOptions,
} from '../../utils/stockProductOptions';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  PENDING_APPROVAL_MESSAGE,
  stockReasonValidationMessage,
} from '../../utils/makerChecker';
import { isValidStockAdjustmentQuantity } from '../../utils/variantPayload';
import { STOCK_ADJUST_HINT } from '../../utils/productDisplay';
import CommitConfirm from '../Shared/CommitConfirm';
import { formatSignedQty } from '../../utils/commitConfirm';

const StockAdjustmentModal = ({ product, onClose, onSave, nested = false }) => {
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    quantity: 0,
    notes: '',
  });
  const [products, setProducts] = useState([]);
  const [productSearch, setProductSearch] = useState('');
  const [variants, setVariants] = useState([]);
  const searchRequestId = useRef(0);
  const [variantAdjustments, setVariantAdjustments] = useState({});
  const [variantsLoading, setVariantsLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const [pendingLines, setPendingLines] = useState(null);
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  const pickedProduct = useMemo(
    () => (product ? product : findProductById(products, formData.product_id)),
    [product, products, formData.product_id]
  );

  const contextProductId = pickedProduct?.id || formData.product_id || null;
  const variantMode = Boolean(pickedProduct?.has_variants);

  useEffect(() => {
    if (!product) {
      loadProducts();
    } else {
      setFormData((prev) => ({ ...prev, product_id: product.id }));
    }
  }, [product]);

  useEffect(() => {
    if (!contextProductId || !variantMode) {
      setVariants([]);
      setVariantAdjustments({});
      return;
    }
    loadVariants(contextProductId);
  }, [contextProductId, variantMode]);

  const loadProducts = async (search = '') => {
    const requestId = ++searchRequestId.current;
    try {
      const list = await fetchTrackedStockProducts({ search });
      if (requestId !== searchRequestId.current) return;
      setProducts(list);
    } catch (err) {
      if (requestId !== searchRequestId.current) return;
      setProducts([]);
    }
  };

  useEffect(() => {
    if (product) return undefined;
    const timer = setTimeout(() => loadProducts(productSearch), 300);
    return () => clearTimeout(timer);
  }, [productSearch, product]);

  const loadVariants = async (productId) => {
    setVariantsLoading(true);
    try {
      const res = await variantsAPI.getByProduct(productId);
      const rows = res.data?.results || res.data || [];
      const list = Array.isArray(rows) ? rows : [];
      setVariants(list);
      const next = {};
      list.forEach((v) => {
        next[v.id] = '';
      });
      setVariantAdjustments(next);
    } catch {
      setVariants([]);
      setError('Could not load variant stock rows.');
    } finally {
      setVariantsLoading(false);
    }
  };

  const productOptions = toStockProductSelectOptions(products);

  const handleProductChange = (e) => {
    const productId = e.target.value;
    setFormData((prev) => ({
      ...prev,
      product_id: productId ? parseInt(productId, 10) : '',
      quantity: 0,
    }));
    setError('');
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'quantity' || name === 'product_id' ? parseInt(value, 10) || 0 : value,
    }));
  };

  const updateVariantAdjustment = (variantId, value) => {
    setVariantAdjustments((prev) => ({
      ...prev,
      [variantId]: value,
    }));
  };

  const submitAdjustments = async (lines) => {
    const notes = formData.notes;
    const reason = makerCheckerOn ? changeReason.trim() : '';
    let lastResponse = null;
    let pendingCount = 0;

    for (const line of lines) {
      const payload = {
        product_id: line.product_id,
        quantity: line.quantity,
        notes,
      };
      if (line.variant_id) {
        payload.variant_id = line.variant_id;
      }
      if (makerCheckerOn) {
        payload.reason = reason;
      }
      const res = await inventoryAPI.adjust(payload);
      lastResponse = res;
      if (isPendingApprovalResponse(res.status)) {
        pendingCount += 1;
      }
    }

    return { lastResponse, pendingCount };
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    try {
      const productId = contextProductId;
      if (!productId) {
        setError('Select a product.');
        return;
      }

      if (makerCheckerOn) {
        const reasonError = stockReasonValidationMessage(changeReason);
        if (reasonError) {
          setError(reasonError);
          return;
        }
      }

      let lines = [];
      if (variantMode) {
        for (const v of variants) {
          const raw = variantAdjustments[v.id];
          if (raw === '' || raw === undefined || raw === null) continue;
          if (!isValidStockAdjustmentQuantity(raw)) {
            setError(
              `Enter a valid whole number for ${variantDisplayLabel(v)} (digits only, + or -).`
            );
            return;
          }
        }
        lines = variants
          .filter((v) => {
            const raw = variantAdjustments[v.id];
            if (raw === '' || raw === undefined || raw === null) return false;
            const qty = parseInt(raw, 10);
            return !Number.isNaN(qty) && qty !== 0;
          })
          .map((v) => ({
            product_id: productId,
            variant_id: v.id,
            quantity: parseInt(variantAdjustments[v.id], 10),
            label: variantDisplayLabel(v),
          }));
        if (!lines.length) {
          setError('Enter an adjustment for at least one variant.');
          return;
        }
      } else {
        if (!formData.quantity) {
          setError('Enter a non-zero adjustment quantity.');
          return;
        }
        lines = [
          {
            product_id: productId,
            variant_id: null,
            quantity: formData.quantity,
            label: pickedProduct?.name || 'Product',
          },
        ];
      }

      setPendingLines(lines);
      setShowCommitConfirm(true);
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.detail || 'Failed to prepare adjustment');
    }
  };

  const confirmCommit = async () => {
    if (!pendingLines?.length || loading) return;
    setLoading(true);
    setError('');
    try {
      const { pendingCount } = await submitAdjustments(pendingLines);
      if (pendingCount > 0) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      } else if (pendingLines.length > 1) {
        toast.success(`Adjusted stock for ${pendingLines.length} variant rows`);
      } else if (variantMode) {
        toast.success('Variant stock adjusted');
      }
      setShowCommitConfirm(false);
      setPendingLines(null);
      onSave();
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.detail || 'Failed to adjust stock');
      setShowCommitConfirm(false);
    } finally {
      setLoading(false);
    }
  };

  const commitRows = (pendingLines || []).flatMap((line, index) => [
    {
      label: pendingLines.length > 1 ? `Line ${index + 1}` : 'Product',
      value: line.label || pickedProduct?.name || `Product #${line.product_id}`,
    },
    {
      label: pendingLines.length > 1 ? `Qty Δ ${index + 1}` : 'Quantity change',
      value: formatSignedQty(line.quantity),
      tone: line.quantity < 0 ? 'danger' : 'success',
      emphasis: true,
    },
  ]);
  if (formData.notes) {
    commitRows.push({ label: 'Notes', value: formData.notes });
  }

  return (
    <>
    <div
      className={nested ? 'slide-in-overlay nested' : 'slide-in-overlay'}
      onClick={onClose}
    >
      <div
        className={nested ? 'slide-in-panel nested' : 'slide-in-panel'}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="slide-in-panel-header">
          <div>
            <h2>Stock adjustment</h2>
            <p className="mt-0.5 text-sm font-normal text-muted-foreground">
              Add or remove units on top of current stock
            </p>
          </div>
          <button type="button" onClick={onClose} className="slide-in-panel-close">
            ×
          </button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit}>
            {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}

            {pickedProduct ? (
              <p className="mb-3 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{pickedProduct.name}</span>
                {variantMode
                  ? ' — enter how many units to add (+) or remove (−) for each variant.'
                  : ' — enter how many units to add (+) or remove (−).'}
              </p>
            ) : null}

            {!product && (
              <div className="form-group">
                <label>Product *</label>
                <SearchableSelect
                  value={formData.product_id || ''}
                  onChange={handleProductChange}
                  options={productOptions}
                  placeholder="Search and select product..."
                  name="product_id"
                  searchable
                  onSearchTermChange={setProductSearch}
                  noResultsHint="Keep typing — search looks up the full catalog."
                />
                <small className="form-text">
                  Variant products show per-variant add/remove fields after you select them.
                </small>
              </div>
            )}

            {variantMode ? (
              <div className="form-group space-y-3">
                <label>Add or remove by variant *</label>
                {variantsLoading ? (
                  <p className="text-sm text-muted-foreground">Loading variants…</p>
                ) : variants.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No variant rows found. Add size/color variants on the product first.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {variants.map((variant) => (
                      <div
                        key={variant.id}
                        className="flex flex-wrap items-center gap-2 rounded-md border border-border/60 bg-muted/20 px-3 py-2"
                      >
                        <div className="min-w-0 flex-1 text-sm">
                          <p className="font-medium">{variantDisplayLabel(variant)}</p>
                          <p className="text-xs text-muted-foreground">
                            On hand: {variant.stock_quantity ?? 0}
                            {variant.sku ? ` · ${variant.sku}` : ''}
                          </p>
                        </div>
                        <Input
                          type="text"
                          inputMode="numeric"
                          className="h-9 w-28 shrink-0"
                          value={variantAdjustments[variant.id] ?? ''}
                          onChange={(e) => updateVariantAdjustment(variant.id, e.target.value)}
                          placeholder="+5 or −2"
                          title="Units to add (+) or remove (−)"
                        />
                      </div>
                    ))}
                  </div>
                )}
                <small className="form-text">{STOCK_ADJUST_HINT}</small>
              </div>
            ) : (
              contextProductId ? (
                <div className="form-group">
                  <label>Add or remove *</label>
                  <input
                    type="number"
                    name="quantity"
                    value={formData.quantity}
                    onChange={handleChange}
                    required
                    placeholder="e.g. +5 to add, −2 to remove"
                  />
                  <small className="form-text">{STOCK_ADJUST_HINT}</small>
                </div>
              ) : null
            )}

            <div className="form-group">
              <label>Notes</label>
              <textarea
                name="notes"
                value={formData.notes}
                onChange={handleChange}
                rows="3"
                placeholder="Optional notes for this adjustment..."
              />
            </div>

            {makerCheckerOn ? (
              <ChangeReasonField context="stock" value={changeReason} onChange={setChangeReason} />
            ) : null}

            <div className="slide-in-panel-footer">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading || (variantMode && variantsLoading)}>
                {loading
                  ? 'Submitting…'
                  : makerCheckerOn
                    ? 'Submit for approval'
                    : 'Apply adjustment'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
    <CommitConfirm
      open={showCommitConfirm}
      onOpenChange={(open) => {
        if (!open) {
          setShowCommitConfirm(false);
          setPendingLines(null);
        }
      }}
      title="Confirm stock adjustment?"
      description="Review the quantity changes, then confirm to save them."
      rows={commitRows}
      submitting={loading}
      confirmText={makerCheckerOn ? 'Submit for approval' : 'Confirm & adjust'}
      onConfirm={confirmCommit}
      variant="warning"
    />
    </>
  );
};

export default StockAdjustmentModal;
