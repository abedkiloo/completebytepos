import React, { useState, useEffect, useMemo } from 'react';
import { productsAPI, variantsAPI } from '../../services/api';
import SearchableSelect from '../Shared/SearchableSelect';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import { toast } from '../../utils/toast';
import { variantDisplayLabel } from '../../utils/variantCombinations';
import {
  formatStockProductOptionLabel,
  findProductById,
} from '../../utils/stockProductOptions';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  PENDING_APPROVAL_MESSAGE,
} from '../../utils/makerChecker';
import { isValidOptionalInteger } from '../../utils/variantPayload';
import {
  STOCK_COUNT_HINT,
  STOCK_COUNT_LABEL,
  STOCK_ON_HAND_LABEL,
} from '../../utils/productDisplay';

const StockCountModal = ({ product, variant = null, onClose, onSave, nested = false }) => {
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    stock_quantity: '',
  });
  const [products, setProducts] = useState([]);
  const [variants, setVariants] = useState([]);
  const [variantCounts, setVariantCounts] = useState({});
  const [variantsLoading, setVariantsLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  const pickedProduct = useMemo(
    () => (product ? product : findProductById(products, formData.product_id)),
    [product, products, formData.product_id]
  );

  const contextProductId = pickedProduct?.id || formData.product_id || null;
  const variantMode = Boolean(pickedProduct?.has_variants);
  const singleVariantMode = Boolean(variantMode && variant?.id);

  useEffect(() => {
    if (!product) {
      loadProducts();
    } else {
      setFormData((prev) => ({
        ...prev,
        product_id: product.id,
        stock_quantity: String(product.stock_quantity ?? 0),
      }));
    }
  }, [product]);

  useEffect(() => {
    if (!contextProductId || !variantMode) {
      setVariants([]);
      setVariantCounts({});
      return;
    }
    if (singleVariantMode) {
      setVariants([variant]);
      setVariantCounts({ [variant.id]: String(variant.stock_quantity ?? 0) });
      setVariantsLoading(false);
      return;
    }
    loadVariants(contextProductId);
  }, [contextProductId, variantMode, singleVariantMode, variant]);

  useEffect(() => {
    if (!variantMode && pickedProduct && !product) {
      setFormData((prev) => ({
        ...prev,
        stock_quantity: String(pickedProduct.stock_quantity ?? 0),
      }));
    }
  }, [pickedProduct, variantMode, product]);

  const loadProducts = async () => {
    try {
      const response = await productsAPI.list({
        track_stock: 'true',
        is_active: 'true',
        page_size: 1000,
      });
      const productsData = response.data.results || response.data || [];
      setProducts(Array.isArray(productsData) ? productsData : []);
    } catch (err) {
    }
  };

  const loadVariants = async (productId) => {
    setVariantsLoading(true);
    try {
      const res = await variantsAPI.getByProduct(productId);
      const rows = res.data?.results || res.data || [];
      const list = Array.isArray(rows) ? rows : [];
      setVariants(list);
      const next = {};
      list.forEach((v) => {
        next[v.id] = String(v.stock_quantity ?? 0);
      });
      setVariantCounts(next);
    } catch {
      setVariants([]);
      setError('Could not load variant stock rows.');
    } finally {
      setVariantsLoading(false);
    }
  };

  const productOptions = products.map((prod) => ({
    id: prod.id,
    name: formatStockProductOptionLabel(prod),
  }));

  const handleProductChange = (e) => {
    const productId = e.target.value;
    setFormData((prev) => ({
      ...prev,
      product_id: productId ? parseInt(productId, 10) : '',
      stock_quantity: '',
    }));
    setError('');
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const updateVariantCount = (variantId, value) => {
    setVariantCounts((prev) => ({
      ...prev,
      [variantId]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const productId = contextProductId;
      if (!productId) {
        setError('Select a product.');
        setLoading(false);
        return;
      }

      if (makerCheckerOn && !changeReason.trim()) {
        setError('A reason is required for stock changes.');
        setLoading(false);
        return;
      }

      const reason = makerCheckerOn ? changeReason.trim() : undefined;
      let pendingCount = 0;
      let updatedCount = 0;

      if (variantMode) {
        const lines = [];
        for (const v of variants) {
          const raw = variantCounts[v.id];
          if (!isValidOptionalInteger(raw)) {
            setError(`Enter a valid whole number for ${variantDisplayLabel(v)}.`);
            setLoading(false);
            return;
          }
          const next = parseInt(raw, 10) || 0;
          const prev = parseInt(v.stock_quantity, 10) || 0;
          if (next !== prev) {
            lines.push({ variant: v, stock_quantity: next });
          }
        }
        if (!lines.length) {
          setError('Change at least one variant count or cancel.');
          setLoading(false);
          return;
        }
        for (const line of lines) {
          const payload = { stock_quantity: line.stock_quantity };
          if (reason) payload.reason = reason;
          const res = await variantsAPI.update(line.variant.id, payload);
          if (isPendingApprovalResponse(res.status)) {
            pendingCount += 1;
          }
          updatedCount += 1;
        }
      } else {
        if (!isValidOptionalInteger(formData.stock_quantity)) {
          setError('Enter a valid whole number for stock on hand.');
          setLoading(false);
          return;
        }
        const next = parseInt(formData.stock_quantity, 10) || 0;
        const prev = parseInt(pickedProduct?.stock_quantity, 10) || 0;
        if (next === prev) {
          setError('Stock on hand is unchanged.');
          setLoading(false);
          return;
        }
        const payload = { stock_quantity: next };
        if (reason) payload.reason = reason;
        const res = await productsAPI.update(productId, payload);
        if (isPendingApprovalResponse(res.status)) {
          pendingCount += 1;
        }
        updatedCount = 1;
      }

      if (pendingCount > 0) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      } else if (updatedCount > 1) {
        toast.success(`Updated stock count for ${updatedCount} variant rows`);
      } else {
        toast.success('Stock count saved');
      }
      onSave();
    } catch (err) {
      const detail =
        err.response?.data?.error ||
        err.response?.data?.detail ||
        (typeof err.response?.data === 'object'
          ? Object.values(err.response.data).flat().join(', ')
          : null);
      setError(detail || 'Failed to save stock count');
    } finally {
      setLoading(false);
    }
  };

  return (
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
            <h2>{STOCK_COUNT_LABEL}</h2>
            <p className="mt-0.5 text-sm font-normal text-muted-foreground">
              Set the correct quantity on hand after a physical count
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
                  ? singleVariantMode
                    ? ` — enter the counted ${STOCK_ON_HAND_LABEL.toLowerCase()} for ${variantDisplayLabel(variant)}.`
                    : ` — enter the counted ${STOCK_ON_HAND_LABEL.toLowerCase()} for each variant.`
                  : ` — enter the counted ${STOCK_ON_HAND_LABEL.toLowerCase()}.`}
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
                />
                <small className="form-text">
                  Variant products show a row for each size/color combination.
                </small>
              </div>
            )}

            {variantMode ? (
              <div className="form-group space-y-3">
                <label>
                  {singleVariantMode ? STOCK_ON_HAND_LABEL : `${STOCK_ON_HAND_LABEL} by variant`} *
                </label>
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
                            System shows: {variant.stock_quantity ?? 0}
                            {variant.sku ? ` · ${variant.sku}` : ''}
                          </p>
                        </div>
                        <Input
                          type="text"
                          inputMode="numeric"
                          className="h-9 w-24 shrink-0"
                          value={variantCounts[variant.id] ?? ''}
                          onChange={(e) => updateVariantCount(variant.id, e.target.value)}
                          placeholder="Count"
                          title="Exact units on hand after your count"
                          aria-label={`${STOCK_ON_HAND_LABEL} for ${variantDisplayLabel(variant)}`}
                        />
                      </div>
                    ))}
                  </div>
                )}
                <small className="form-text">{STOCK_COUNT_HINT}</small>
              </div>
            ) : (
              contextProductId ? (
                <div className="form-group">
                  <label htmlFor="stock-count-quantity">{STOCK_ON_HAND_LABEL} *</label>
                  <p className="mb-1.5 text-xs text-muted-foreground">
                    System shows: {pickedProduct?.stock_quantity ?? 0}
                  </p>
                  <input
                    id="stock-count-quantity"
                    type="text"
                    inputMode="numeric"
                    name="stock_quantity"
                    value={formData.stock_quantity}
                    onChange={handleChange}
                    required
                    placeholder="Counted quantity"
                  />
                  <small className="form-text">{STOCK_COUNT_HINT}</small>
                </div>
              ) : null
            )}

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
                    : 'Save stock count'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default StockCountModal;
