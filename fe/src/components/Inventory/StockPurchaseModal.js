import React, { useState, useEffect, useMemo } from 'react';
import { inventoryAPI, productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import SearchableSelect from '../Shared/SearchableSelect';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import { toast } from '../../utils/toast';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  PENDING_APPROVAL_MESSAGE,
  stockReasonValidationMessage,
} from '../../utils/makerChecker';
import CommitConfirm from '../Shared/CommitConfirm';

const catalogCostOf = (prod) => {
  const raw = prod?.cost;
  if (raw === null || raw === undefined || raw === '') return 0;
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
};

const StockPurchaseModal = ({ product, onClose, onSave }) => {
  const defaultQuantity = (product?.reorder_quantity != null && product.reorder_quantity > 0)
    ? product.reorder_quantity
    : 1;
  const initialCatalog = catalogCostOf(product);
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    quantity: defaultQuantity,
    unit_cost: initialCatalog > 0 ? initialCatalog : '',
    unit_sell_price: product?.selling_price ?? product?.price ?? '',
    reference: '',
    notes: '',
  });
  /** 'catalog' = keep existing cost for this batch; 'new' = enter a new batch cost */
  const [costMode, setCostMode] = useState(initialCatalog > 0 ? 'catalog' : 'new');
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const [pendingPayload, setPendingPayload] = useState(null);
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  const selectedProduct = useMemo(
    () =>
      product ||
      products.find((p) => Number(p.id) === Number(formData.product_id)),
    [product, products, formData.product_id]
  );
  const catalogCost = catalogCostOf(selectedProduct);
  const hasCatalogCost = catalogCost > 0;

  useEffect(() => {
    if (!product) {
      loadProducts();
    } else {
      const qty = (product.reorder_quantity != null && product.reorder_quantity > 0)
        ? product.reorder_quantity
        : 1;
      const cost = catalogCostOf(product);
      setFormData((prev) => ({
        ...prev,
        product_id: product.id,
        quantity: qty,
        unit_cost: cost > 0 ? cost : '',
        unit_sell_price: product.selling_price ?? product.price ?? '',
      }));
      setCostMode(cost > 0 ? 'catalog' : 'new');
    }
  }, [product]);

  const loadProducts = async () => {
    try {
      const params = {
        track_stock: 'true',
        is_active: 'true',
        page_size: 1000,
        needs_restock: 'true',
      };
      const response = await productsAPI.list(params);
      const productsData = response.data.results || response.data || [];
      setProducts(Array.isArray(productsData) ? productsData : []);
    } catch (err) {
      // Product picker stays empty; user can still open from a product context.
    }
  };

  const productOptions = products.map((prod) => ({
    id: prod.id,
    name: `${prod.name}${prod.sku ? ` (${prod.sku})` : ''} - Stock: ${prod.stock_quantity ?? 0}${prod.low_stock_threshold != null ? ` / threshold ${prod.low_stock_threshold}` : ''}${prod.cost_missing ? ' · cost missing' : ''}`,
  }));

  const handleProductChange = (e) => {
    const productId = e.target.value;
    const next = products.find((p) => Number(p.id) === Number(productId));
    const cost = catalogCostOf(next);
    setFormData((prev) => ({
      ...prev,
      product_id: productId ? parseInt(productId, 10) : '',
      unit_cost: cost > 0 ? cost : '',
      unit_sell_price: next?.selling_price ?? next?.price ?? prev.unit_sell_price,
    }));
    setCostMode(cost > 0 ? 'catalog' : 'new');
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'quantity'
        ? (value === '' ? '' : (parseInt(value, 10) || 0))
        : name === 'product_id'
        ? (value ? parseInt(value, 10) : '')
        : name === 'unit_cost' || name === 'unit_sell_price'
        ? value
        : value,
    }));
  };

  const quantityNum = Number(formData.quantity);
  const effectiveUnitCost =
    costMode === 'catalog' && hasCatalogCost
      ? catalogCost
      : Number(formData.unit_cost);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    if (formData.quantity === '' || formData.quantity === undefined || quantityNum < 1) {
      setError('Quantity must be at least 1 to record a purchase.');
      return;
    }
    if (!formData.product_id && !product?.id) {
      setError('Select a product.');
      return;
    }

    const useCatalog = costMode === 'catalog' && hasCatalogCost;
    if (!useCatalog) {
      const costNum = Number(formData.unit_cost);
      if (!Number.isFinite(costNum) || costNum <= 0) {
        setError(
          hasCatalogCost
            ? 'Enter a unit cost greater than zero for this new batch.'
            : 'Cost is missing on this product. Enter the unit cost for this stock before recording.'
        );
        return;
      }
    }

    const payload = {
      product_id: formData.product_id || product?.id,
      quantity: quantityNum,
      unit_sell_price: formData.unit_sell_price === '' ? undefined : formData.unit_sell_price,
      reference: formData.reference,
      notes: formData.notes,
    };
    if (useCatalog) {
      payload.use_catalog_cost = true;
    } else {
      payload.unit_cost = Number(formData.unit_cost);
      payload.use_catalog_cost = false;
    }

    if (makerCheckerOn) {
      const reasonError = stockReasonValidationMessage(changeReason);
      if (reasonError) {
        setError(
          reasonError === 'A reason is required for stock changes.'
            ? 'A reason is required for stock purchases.'
            : reasonError
        );
        return;
      }
      payload.reason = changeReason.trim();
    }
    setPendingPayload(payload);
    setShowCommitConfirm(true);
  };

  const confirmCommit = async () => {
    if (!pendingPayload || loading) return;
    setLoading(true);
    try {
      const res = await inventoryAPI.purchase(pendingPayload);
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      }
      setShowCommitConfirm(false);
      setPendingPayload(null);
      onSave();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to record purchase');
      setShowCommitConfirm(false);
    } finally {
      setLoading(false);
    }
  };

  const totalCost =
    (quantityNum >= 0 ? quantityNum : 0) *
    (Number.isFinite(effectiveUnitCost) ? effectiveUnitCost : 0);
  const commitRows = pendingPayload
    ? [
        { label: 'Product', value: selectedProduct?.name || `Product #${pendingPayload.product_id}` },
        { label: 'Quantity', value: `+${pendingPayload.quantity}`, tone: 'success', emphasis: true },
        {
          label: 'Unit cost',
          value: pendingPayload.use_catalog_cost
            ? `${formatCurrency(catalogCost)} (existing)`
            : formatCurrency(pendingPayload.unit_cost),
        },
        pendingPayload.unit_sell_price
          ? { label: 'Selling price (this batch)', value: formatCurrency(pendingPayload.unit_sell_price) }
          : null,
        totalCost > 0 ? { label: 'Total cost', value: formatCurrency(totalCost), emphasis: true } : null,
        pendingPayload.reference ? { label: 'Reference', value: pendingPayload.reference } : null,
      ].filter(Boolean)
    : [];

  return (
    <>
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Record Stock Purchase</h2>
          <button onClick={onClose} className="slide-in-panel-close">×</button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="stock-form">
          {error && <div className="error-message">{error}</div>}

          {!product && (
            <div className="form-group">
              <label>Product *</label>
              <SearchableSelect
                value={formData.product_id || ''}
                onChange={handleProductChange}
                options={productOptions}
                placeholder="Search and select product..."
                name="product_id"
                searchable={true}
              />
            </div>
          )}

          {product && (
            <div className="product-info-box">
              <h3>{product.name}</h3>
              <p>SKU: {product.sku} | Current Stock: {product.stock_quantity}</p>
              {catalogCostOf(product) <= 0 ? (
                <p className="text-sm text-amber-700">
                  Cost is zero — enter the cost for this delivery so reports and COGS stay correct.
                </p>
              ) : null}
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>Quantity *</label>
              <input
                type="number"
                name="quantity"
                value={formData.quantity}
                onChange={handleChange}
                required
                min="1"
              />
              <small>Must be at least 1 to record a purchase.</small>
            </div>
          </div>

          <div className="form-group">
            <label>Cost for this batch *</label>
            <div className="mt-1 space-y-2">
              <label className={`flex items-start gap-2 text-sm ${!hasCatalogCost ? 'opacity-50' : ''}`}>
                <input
                  type="radio"
                  name="cost_mode"
                  checked={costMode === 'catalog'}
                  disabled={!hasCatalogCost}
                  onChange={() => setCostMode('catalog')}
                />
                <span>
                  Keep existing cost
                  {hasCatalogCost ? (
                    <span className="text-muted-foreground"> ({formatCurrency(catalogCost)})</span>
                  ) : (
                    <span className="text-muted-foreground"> — none on file</span>
                  )}
                </span>
              </label>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="cost_mode"
                  checked={costMode === 'new'}
                  onChange={() => setCostMode('new')}
                />
                <span>New cost for this delivery (supplier / period change)</span>
              </label>
            </div>
            {costMode === 'new' ? (
              <input
                type="number"
                name="unit_cost"
                className="mt-2"
                value={formData.unit_cost}
                onChange={handleChange}
                step="0.01"
                min="0.01"
                required
                placeholder="Unit cost (KES)"
              />
            ) : null}
            <small>
              Each delivery can have its own cost. FIFO layers keep older stock at its original cost until sold.
            </small>
          </div>

          <div className="form-group">
            <label>Selling price for this batch (KES)</label>
            <input
              type="number"
              name="unit_sell_price"
              value={formData.unit_sell_price}
              onChange={handleChange}
              step="0.01"
              min="0"
              placeholder="Price while this stock remains"
            />
            <small>
              Old units keep their price until sold. New price applies after this batch is next in line.
            </small>
          </div>

          {totalCost > 0 && (
            <div className="total-cost-display">
              <strong>Total Cost: {formatCurrency(totalCost)}</strong>
            </div>
          )}

          <div className="form-group">
            <label>Reference (PO Number, Invoice, etc.)</label>
            <input
              type="text"
              name="reference"
              value={formData.reference}
              onChange={handleChange}
              placeholder="Optional"
            />
          </div>

          <div className="form-group">
            <label>Notes</label>
            <textarea
              name="notes"
              value={formData.notes}
              onChange={handleChange}
              rows="3"
              placeholder="Additional notes..."
            />
          </div>

          {makerCheckerOn ? (
            <ChangeReasonField context="stock" value={changeReason} onChange={setChangeReason} />
          ) : null}

          </form>
        </div>
        <div className="slide-in-panel-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button type="submit" onClick={handleSubmit} disabled={loading} className="btn btn-primary">
            {loading
              ? 'Submitting…'
              : makerCheckerOn
                ? 'Submit for approval'
                : 'Record Purchase'}
          </button>
        </div>
      </div>
    </div>
    <CommitConfirm
      open={showCommitConfirm}
      onOpenChange={(open) => {
        if (!open) {
          setShowCommitConfirm(false);
          setPendingPayload(null);
        }
      }}
      title="Confirm stock purchase?"
      description="Review the purchase details, then confirm to add stock."
      rows={commitRows}
      submitting={loading}
      confirmText={makerCheckerOn ? 'Submit for approval' : 'Confirm & record purchase'}
      onConfirm={confirmCommit}
      variant="warning"
    />
    </>
  );
};

export default StockPurchaseModal;
