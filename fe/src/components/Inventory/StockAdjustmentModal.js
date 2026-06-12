import React, { useState, useEffect } from 'react';
import { inventoryAPI, productsAPI, variantsAPI } from '../../services/api';
import SearchableSelect from '../Shared/SearchableSelect';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import { toast } from '../../utils/toast';
import { variantDisplayLabel } from '../../utils/variantCombinations';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  PENDING_APPROVAL_MESSAGE,
} from '../../utils/makerChecker';

const StockAdjustmentModal = ({ product, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    quantity: 0,
    notes: '',
  });
  const [products, setProducts] = useState([]);
  const [variants, setVariants] = useState([]);
  const [variantAdjustments, setVariantAdjustments] = useState({});
  const [variantsLoading, setVariantsLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  const variantMode = Boolean(product?.has_variants);

  useEffect(() => {
    if (!product) {
      loadProducts();
      setVariants([]);
      setVariantAdjustments({});
      return;
    }
    setFormData((prev) => ({ ...prev, product_id: product.id }));
    if (product.has_variants) {
      loadVariants(product.id);
    } else {
      setVariants([]);
      setVariantAdjustments({});
    }
  }, [product]);

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
      console.error('Error loading products:', err);
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
        next[v.id] = 0;
      });
      setVariantAdjustments(next);
    } catch {
      setVariants([]);
      setError('Could not load variant stock rows.');
    } finally {
      setVariantsLoading(false);
    }
  };

  const productOptions = products.map((prod) => ({
    id: prod.id,
    name: `${prod.name}${prod.sku ? ` (${prod.sku})` : ''} - Stock: ${prod.stock_quantity || 0}`,
  }));

  const handleProductChange = (e) => {
    const productId = e.target.value;
    setFormData((prev) => ({
      ...prev,
      product_id: productId ? parseInt(productId, 10) : '',
    }));
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
      [variantId]: parseInt(value, 10) || 0,
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
    setLoading(true);

    try {
      const productId = product?.id || formData.product_id;
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

      let lines = [];
      if (variantMode) {
        lines = variants
          .filter((v) => (variantAdjustments[v.id] || 0) !== 0)
          .map((v) => ({
            product_id: productId,
            variant_id: v.id,
            quantity: variantAdjustments[v.id],
          }));
        if (!lines.length) {
          setError('Enter an adjustment for at least one variant.');
          setLoading(false);
          return;
        }
      } else {
        if (!formData.quantity) {
          setError('Enter a non-zero adjustment quantity.');
          setLoading(false);
          return;
        }
        lines = [
          {
            product_id: productId,
            variant_id: null,
            quantity: formData.quantity,
          },
        ];
      }

      const { lastResponse, pendingCount } = await submitAdjustments(lines);
      if (pendingCount > 0) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      } else if (lines.length > 1) {
        toast.success(`Adjusted stock for ${lines.length} variant rows`);
      }
      if (lastResponse && !pendingCount && lines.length === 1) {
        // single immediate adjust — no extra toast (parent may refresh list)
      }
      onSave();
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.detail || 'Failed to adjust stock');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Stock adjustment</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">
            ×
          </button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit}>
            {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}

            {product ? (
              <p className="mb-3 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{product.name}</span>
                {variantMode ? ' — adjust each variant below.' : null}
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
              </div>
            )}

            {variantMode ? (
              <div className="form-group space-y-3">
                <label>Variant adjustments *</label>
                {variantsLoading ? (
                  <p className="text-sm text-muted-foreground">Loading variants…</p>
                ) : variants.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No variant rows found. Save size/color on the product first.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {variants.map((variant) => (
                      <div
                        key={variant.id}
                        className="grid grid-cols-[1fr_auto_auto] items-center gap-2 rounded-md border border-border/60 bg-muted/20 px-3 py-2"
                      >
                        <div className="min-w-0 text-sm">
                          <p className="font-medium">{variantDisplayLabel(variant)}</p>
                          <p className="text-xs text-muted-foreground">
                            On hand: {variant.stock_quantity ?? 0}
                          </p>
                        </div>
                        <span className="text-xs text-muted-foreground">+ / −</span>
                        <Input
                          type="number"
                          className="w-24"
                          value={variantAdjustments[variant.id] ?? 0}
                          onChange={(e) => updateVariantAdjustment(variant.id, e.target.value)}
                          placeholder="0"
                        />
                      </div>
                    ))}
                  </div>
                )}
                <small className="form-text">
                  Positive adds stock, negative removes. Leave 0 to skip a variant.
                </small>
              </div>
            ) : (
              <div className="form-group">
                <label>Adjustment quantity *</label>
                <input
                  type="number"
                  name="quantity"
                  value={formData.quantity}
                  onChange={handleChange}
                  required
                  placeholder="Positive to add, negative to remove"
                />
                <small className="form-text">
                  Enter positive number to add stock, negative to remove
                </small>
              </div>
            )}

            <div className="form-group">
              <label>Notes</label>
              <textarea
                name="notes"
                value={formData.notes}
                onChange={handleChange}
                rows="3"
                placeholder="Reason for adjustment..."
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
                    : 'Adjust stock'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default StockAdjustmentModal;
