import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { inventoryAPI, variantsAPI } from '../../services/api';
import SearchableSelect from '../Shared/SearchableSelect';
import { Button } from '../ui/button';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import { toast } from '../../utils/toast';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  PENDING_APPROVAL_MESSAGE,
  stockReasonValidationMessage,
} from '../../utils/makerChecker';
import {
  fetchTrackedStockProducts,
  findProductById,
  formatVariantStockOptionLabel,
  toStockProductSelectOptions,
} from '../../utils/stockProductOptions';

const emptyLine = () => ({
  product_id: '',
  variant_id: '',
  quantity: '',
  notes: '',
});

const StockBulkAdjustModal = ({ onClose, onSave }) => {
  const [lines, setLines] = useState([emptyLine(), emptyLine()]);
  const [products, setProducts] = useState([]);
  const [selectedProducts, setSelectedProducts] = useState({});
  const [productSearch, setProductSearch] = useState('');
  const [variantsByProduct, setVariantsByProduct] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);
  const searchRequestId = useRef(0);

  const loadProducts = useCallback(async (search = '') => {
    const requestId = ++searchRequestId.current;
    try {
      const list = await fetchTrackedStockProducts({ search });
      if (requestId !== searchRequestId.current) return;
      setProducts(list);
    } catch {
      if (requestId !== searchRequestId.current) return;
      setProducts([]);
    }
  }, []);

  useEffect(() => {
    loadProducts('');
  }, [loadProducts]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadProducts(productSearch);
    }, 300);
    return () => clearTimeout(timer);
  }, [productSearch, loadProducts]);

  const catalogProducts = useMemo(() => {
    const byId = new Map();
    products.forEach((p) => byId.set(Number(p.id), p));
    Object.values(selectedProducts).forEach((p) => {
      if (p?.id != null) byId.set(Number(p.id), p);
    });
    return Array.from(byId.values());
  }, [products, selectedProducts]);

  const productOptions = useMemo(
    () => toStockProductSelectOptions(catalogProducts),
    [catalogProducts]
  );

  const ensureVariantsLoaded = async (productId) => {
    if (!productId || variantsByProduct[productId]) return;
    try {
      const res = await variantsAPI.getByProduct(productId);
      const rows = res.data?.results || res.data || [];
      const list = Array.isArray(rows) ? rows : [];
      setVariantsByProduct((prev) => ({ ...prev, [productId]: list }));
    } catch {
      setVariantsByProduct((prev) => ({ ...prev, [productId]: [] }));
    }
  };

  const updateLine = (index, patch) => {
    setLines((prev) =>
      prev.map((line, i) => (i === index ? { ...line, ...patch } : line))
    );
  };

  const handleProductChange = async (index, value) => {
    const productId = value ? parseInt(value, 10) : '';
    updateLine(index, {
      product_id: productId,
      variant_id: '',
    });
    const product = findProductById(catalogProducts, productId);
    if (product) {
      setSelectedProducts((prev) => ({ ...prev, [product.id]: product }));
    }
    if (product?.has_variants) {
      await ensureVariantsLoaded(productId);
    }
  };

  const addLine = () => setLines((prev) => [...prev, emptyLine()]);

  const removeLine = (index) => {
    setLines((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const adjustments = [];
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      if (!line.product_id || line.quantity === '' || line.quantity === undefined) {
        continue;
      }
      const product = findProductById(catalogProducts, line.product_id);
      if (product?.has_variants && !line.variant_id) {
        setError(`Line ${i + 1}: select a variant for ${product.name}.`);
        return;
      }
      adjustments.push({
        product_id: line.product_id,
        ...(line.variant_id ? { variant_id: Number(line.variant_id) } : {}),
        quantity: parseInt(line.quantity, 10) || 0,
        notes: line.notes || '',
      });
    }

    if (!adjustments.length) {
      setError('Add at least one product with a quantity.');
      return;
    }
    if (makerCheckerOn) {
      const reasonError = stockReasonValidationMessage(changeReason);
      if (reasonError) {
        setError(
          reasonError === 'A reason is required for stock changes.'
            ? 'A reason is required for bulk stock changes.'
            : reasonError
        );
        return;
      }
    }

    setLoading(true);
    try {
      const payload = { adjustments };
      if (makerCheckerOn) {
        payload.reason = changeReason.trim();
      }
      const res = await inventoryAPI.bulkAdjust(payload);
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      } else {
        toast.success('Bulk adjustments recorded');
      }
      onSave();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to submit bulk adjustments');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel slide-in-panel-wide" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Bulk stock adjustment</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">
            ×
          </button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="stock-form space-y-3">
            {error ? <div className="error-message">{error}</div> : null}
            <p className="text-sm text-muted-foreground">
              Search by name, SKU, or barcode. Variant products need a variant on each line.
              Use negative quantities to reduce stock.
            </p>

            {lines.map((line, index) => {
              const product = findProductById(catalogProducts, line.product_id);
              const needsVariant = Boolean(product?.has_variants);
              const variantOptions = (variantsByProduct[line.product_id] || []).map((v) => ({
                id: v.id,
                name: formatVariantStockOptionLabel(v),
              }));

              return (
                <div
                  key={index}
                  className="grid gap-2 rounded-md border border-border p-3 sm:grid-cols-[1fr_1fr_120px_1fr_auto]"
                >
                  <div className="form-group sm:col-span-1">
                    <label>Product *</label>
                    <SearchableSelect
                      value={line.product_id || ''}
                      onChange={(e) => handleProductChange(index, e.target.value)}
                      options={productOptions}
                      placeholder="Search product…"
                      name={`product_${index}`}
                      searchable
                      onSearchTermChange={setProductSearch}
                      noResultsHint="Keep typing — search looks up the full catalog."
                    />
                  </div>
                  <div className="form-group">
                    <label>{needsVariant ? 'Variant *' : 'Variant'}</label>
                    <SearchableSelect
                      value={line.variant_id || ''}
                      onChange={(e) =>
                        updateLine(index, {
                          variant_id: e.target.value ? parseInt(e.target.value, 10) : '',
                        })
                      }
                      options={variantOptions}
                      placeholder={needsVariant ? 'Select variant…' : 'N/A'}
                      name={`variant_${index}`}
                      searchable={needsVariant}
                      disabled={!needsVariant}
                    />
                  </div>
                  <div className="form-group">
                    <label>Qty *</label>
                    <input
                      type="number"
                      value={line.quantity}
                      onChange={(e) => updateLine(index, { quantity: e.target.value })}
                      placeholder="+/-"
                      required={!!line.product_id}
                    />
                  </div>
                  <div className="form-group">
                    <label>Notes</label>
                    <input
                      type="text"
                      value={line.notes}
                      onChange={(e) => updateLine(index, { notes: e.target.value })}
                      placeholder="Optional"
                    />
                  </div>
                  <div className="flex items-end">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeLine(index)}
                      disabled={lines.length <= 1}
                      aria-label="Remove line"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}

            <Button type="button" variant="outline" size="sm" onClick={addLine}>
              <Plus className="mr-1 h-4 w-4" />
              Add line
            </Button>

            {makerCheckerOn ? (
              <ChangeReasonField context="stock" value={changeReason} onChange={setChangeReason} />
            ) : null}
          </form>
        </div>

        <div className="slide-in-panel-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">
            Cancel
          </button>
          <button type="submit" onClick={handleSubmit} disabled={loading} className="btn btn-primary">
            {loading ? 'Submitting…' : makerCheckerOn ? 'Submit for approval' : 'Apply adjustments'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default StockBulkAdjustModal;
