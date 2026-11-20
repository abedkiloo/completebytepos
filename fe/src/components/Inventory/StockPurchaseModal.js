import React, { useState, useEffect, useMemo } from 'react';
import { inventoryAPI, pendingChangesAPI, productsAPI, variantsAPI } from '../../services/api';
import { variantDisplayLabel } from '../../utils/variantCombinations';
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
import { getPersonaFromStorage, PERSONA } from '../../utils/roleAccess';

const StockPurchaseModal = ({ product, onClose, onSave }) => {
  const defaultQuantity = (product?.reorder_quantity != null && product.reorder_quantity > 0)
    ? product.reorder_quantity
    : 1;
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    quantity: defaultQuantity,
    unit_sell_price: '',
    unit_mrp: '',
    reference: '',
    notes: '',
  });
  /** New price until the person clicks Old price. */
  const [priceMode, setPriceMode] = useState('new');
  const [deliveries, setDeliveries] = useState([]);
  const [priceDrafts, setPriceDrafts] = useState({});
  const [costDrafts, setCostDrafts] = useState({});
  const isSuperAdmin = getPersonaFromStorage() === PERSONA.SUPER_ADMIN;
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const [pendingPayload, setPendingPayload] = useState(null);
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);
  const [variants, setVariants] = useState([]);
  const [variantId, setVariantId] = useState('');
  const [returnedPurchases, setReturnedPurchases] = useState([]);
  const [correctingId, setCorrectingId] = useState(null);
  const [returnedReason, setReturnedReason] = useState('');
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  const selectedProduct = useMemo(
    () =>
      product ||
      products.find((p) => Number(p.id) === Number(formData.product_id)),
    [product, products, formData.product_id]
  );
  const selectedVariant = variants.find((row) => Number(row.id) === Number(variantId));
  const catalogSell = Number(
    selectedVariant?.price ?? selectedProduct?.selling_price ?? selectedProduct?.price ?? 0
  );

  useEffect(() => {
    if (!product) {
      loadProducts();
    } else {
      const qty = (product.reorder_quantity != null && product.reorder_quantity > 0)
        ? product.reorder_quantity
        : 1;
      setFormData((prev) => ({
        ...prev,
        product_id: product.id,
        quantity: qty,
        unit_sell_price: '',
        unit_mrp: '',
      }));
      setPriceMode('new');
    }
  }, [product]);

  const loadProducts = async () => {
    try {
      const params = {
        track_stock: 'true',
        is_active: 'true',
        page_size: 1000,
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
    name: `${prod.name}${prod.sku ? ` (${prod.sku})` : ''} - Stock: ${prod.stock_quantity ?? 0}${prod.new_sale_price_unset ? ' · New sale price has not been set' : ''}`,
  }));

  const handleProductChange = (e) => {
    const productId = e.target.value;
    setFormData((prev) => ({
      ...prev,
      product_id: productId ? parseInt(productId, 10) : '',
      unit_sell_price: '',
      unit_mrp: '',
    }));
    setPriceMode('new');
    setVariantId('');
  };

  useEffect(() => {
    const productId = selectedProduct?.id;
    if (!productId || !selectedProduct?.has_variants) {
      setVariants([]);
      return;
    }
    let cancelled = false;
    const preferredId = selectedProduct.initial_variant_id;
    const seed = Array.isArray(selectedProduct.variants) ? selectedProduct.variants : [];
    variantsAPI.getByProduct(productId).then((response) => {
      if (cancelled) return;
      const rows = response.data.results || response.data || [];
      const listed = Array.isArray(rows) ? rows.filter((row) => row.is_active !== false) : [];
      const seen = new Set(listed.map((row) => Number(row.id)));
      seed.forEach((row) => {
        if (row?.id && row.is_active !== false && !seen.has(Number(row.id))) {
          listed.push(row);
        }
      });
      setVariants(listed);
      setVariantId((current) => {
        if (current && listed.some((row) => String(row.id) === String(current))) return current;
        if (preferredId && listed.some((row) => Number(row.id) === Number(preferredId))) {
          return String(preferredId);
        }
        return '';
      });
    }).catch(() => {
      if (cancelled) return;
      setVariants(seed.filter((row) => row?.id && row.is_active !== false));
      if (preferredId) setVariantId(String(preferredId));
    });
    return () => { cancelled = true; };
  }, [selectedProduct?.id, selectedProduct?.has_variants, selectedProduct?.initial_variant_id, selectedProduct?.variants]);

  const loadReturnedPurchases = () => {
    if (!makerCheckerOn) {
      setReturnedPurchases([]);
      return;
    }
    pendingChangesAPI.mySubmissions({
      status: 'rejected',
      action_type: 'stock_purchase',
      limit: 20,
    }).then((response) => {
      const rows = Array.isArray(response.data) ? response.data : response.data?.results || [];
      const mine = rows.filter((row) => row.status === 'rejected');
      const lockedId = product?.id;
      setReturnedPurchases(
        lockedId
          ? mine.filter((row) => Number(row.apply_payload?.product_id) === Number(lockedId))
          : mine
      );
    }).catch(() => setReturnedPurchases([]));
  };

  useEffect(() => {
    loadReturnedPurchases();
  }, [makerCheckerOn, product?.id]);

  const startCorrection = (row) => {
    const payload = row.apply_payload || {};
    const productId = payload.product_id || '';
    setCorrectingId(row.id);
    setReturnedReason(row.rejection_reason || 'Sent back for correction.');
    setPriceMode(payload.price_mode === 'old' ? 'old' : 'new');
    setVariantId(payload.variant_id ? String(payload.variant_id) : '');
    setChangeReason('');
    setFormData((prev) => ({
      ...prev,
      product_id: productId ? Number(productId) : prev.product_id,
      quantity: payload.quantity || 1,
      unit_sell_price: payload.unit_sell_price || '',
      unit_mrp: payload.unit_mrp || '',
      reference: payload.reference || '',
      notes: payload.notes || '',
    }));
  };

  useEffect(() => {
    const productId = formData.product_id || product?.id;
    if (!productId || (selectedProduct?.has_variants && !variantId)) {
      setDeliveries([]);
      return;
    }
    let cancelled = false;
    inventoryAPI.pendingPrices(productId, variantId || undefined).then((res) => {
      if (!cancelled) setDeliveries(Array.isArray(res.data) ? res.data : []);
    }).catch(() => {
      if (!cancelled) setDeliveries([]);
    });
    return () => { cancelled = true; };
  }, [formData.product_id, product?.id, selectedProduct?.has_variants, variantId]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'quantity'
        ? (value === '' ? '' : (parseInt(value, 10) || 0))
        : name === 'product_id'
        ? (value ? parseInt(value, 10) : '')
        : name === 'unit_sell_price' || name === 'unit_mrp'
        ? value
        : value,
    }));
  };

  const quantityNum = Number(formData.quantity);
  const newPriceMissing = priceMode === 'new' && String(formData.unit_sell_price).trim() === '';

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
    if (selectedProduct?.has_variants && !variantId) {
      setError('Choose a size and colour.');
      return;
    }

    const payload = {
      product_id: formData.product_id || product?.id,
      quantity: quantityNum,
      price_mode: priceMode,
      reference: formData.reference,
      notes: formData.notes,
    };
    if (priceMode === 'new' && formData.unit_sell_price !== '') {
      payload.unit_sell_price = formData.unit_sell_price;
    }
    if (priceMode === 'new' && formData.unit_mrp !== '') {
      payload.unit_mrp = formData.unit_mrp;
    }
    if (variantId) {
      payload.variant_id = Number(variantId);
    }
    if (correctingId) {
      payload.rejected_change_id = correctingId;
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
      setCorrectingId(null);
      setReturnedReason('');
      loadReturnedPurchases();
      onSave();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to record purchase');
      setShowCommitConfirm(false);
    } finally {
      setLoading(false);
    }
  };

  const commitRows = pendingPayload
    ? [
        { label: 'Product', value: selectedProduct?.name || `Product #${pendingPayload.product_id}` },
        selectedVariant
          ? { label: 'Size and colour', value: variantDisplayLabel(selectedVariant) }
          : null,
        { label: 'Quantity', value: `+${pendingPayload.quantity}`, tone: 'success', emphasis: true },
        selectedVariant
          ? {
              label: 'On the shelf now',
              value: String(Number(selectedVariant.stock_quantity ?? 0)),
            }
          : null,
        {
          label: 'Price choice',
          value: pendingPayload.price_mode === 'old' ? 'Old price' : 'New price',
        },
        {
          label: 'Selling price',
          value: pendingPayload.price_mode === 'old'
            ? formatCurrency(catalogSell)
            : pendingPayload.unit_sell_price
              ? formatCurrency(pendingPayload.unit_sell_price)
              : 'New sale price has not been set',
        },
        pendingPayload.unit_mrp
          ? { label: 'MRP', value: formatCurrency(pendingPayload.unit_mrp) }
          : null,
        pendingPayload.notes ? { label: 'Notes', value: pendingPayload.notes } : null,
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

          {returnedReason ? (
            <div className="mb-3 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm" data-testid="returned-purchase-reason">
              <p className="font-medium">Sent back for correction</p>
              <p className="mt-1">{returnedReason}</p>
            </div>
          ) : null}

          {!correctingId && returnedPurchases.length > 0 ? (
            <div className="mb-3 space-y-2 rounded-md border border-destructive/30 p-3" data-testid="returned-purchases">
              <p className="font-medium">Purchases sent back</p>
              {returnedPurchases.map((row) => (
                <div key={row.id} className="flex flex-wrap items-start justify-between gap-2 text-sm">
                  <div>
                    <p>{row.entity_repr || 'Stock purchase'}</p>
                    <p>{row.rejection_reason || 'Sent back for correction.'}</p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => startCorrection(row)}
                  >
                    Correct
                  </button>
                </div>
              ))}
            </div>
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
                searchable={true}
              />
            </div>
          )}

          {selectedProduct?.has_variants ? (
            <div className="form-group">
              <label htmlFor="purchase-variant">Size and colour *</label>
              <select
                id="purchase-variant"
                value={variantId}
                onChange={(event) => setVariantId(event.target.value)}
              >
                <option value="">Choose a size and colour</option>
                {variants.map((row) => (
                  <option key={row.id} value={row.id}>
                    {variantDisplayLabel(row)} — Stock: {row.stock_quantity ?? 0}
                  </option>
                ))}
              </select>
              <small>The new pieces are added to this size and colour only.</small>
            </div>
          ) : null}

          {product && (
            <div className="product-info-box">
              <h3>{product.name}</h3>
              <p>SKU: {product.sku} | Current Stock: {product.stock_quantity}</p>
              <p>The new pieces are added on top. Pieces already on the shelf stay.</p>
              {product.new_sale_price_unset ? (
                <p className="text-sm text-amber-700">New sale price has not been set</p>
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
            <label>Price for this delivery</label>
            <div className="mt-1 space-y-2">
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="price_mode"
                  checked={priceMode === 'new'}
                  onChange={() => setPriceMode('new')}
                />
                <span>New price</span>
              </label>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="price_mode"
                  checked={priceMode === 'old'}
                  onChange={() => setPriceMode('old')}
                />
                <span>
                  Old price
                  {catalogSell > 0 ? (
                    <span className="text-muted-foreground"> ({formatCurrency(catalogSell)})</span>
                  ) : null}
                </span>
              </label>
            </div>
            {priceMode === 'new' ? (
              <>
                <input
                  type="number"
                  name="unit_sell_price"
                  className="mt-2"
                  value={formData.unit_sell_price}
                  onChange={handleChange}
                  step="0.01"
                  min="0.01"
                  placeholder="New selling price (KES)"
                />
                <input
                  type="number"
                  name="unit_mrp"
                  className="mt-2"
                  value={formData.unit_mrp}
                  onChange={handleChange}
                  step="0.01"
                  min="0"
                  placeholder="New MRP (optional)"
                />
                {newPriceMissing ? (
                  <p className="mt-2 text-sm text-amber-700" data-testid="new-price-unset">
                    New sale price has not been set
                  </p>
                ) : null}
              </>
            ) : (
              <small>These pieces keep the current selling price and can be sold now.</small>
            )}
            <small>
              Pieces already on the shelf keep their price. Cost is set later by a Super Admin.
            </small>
          </div>

          {deliveries.length > 0 ? (
            <div className="form-group">
              <label>Selling price for pieces still in stock</label>
              {deliveries.map((row) => (
                <div key={row.layer_id} className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="text-sm">
                    {row.quantity} pieces
                    {row.sale_price_pending
                      ? ' · New sale price has not been set'
                      : ` · now ${formatCurrency(row.unit_sell_price)}`}
                  </span>
                  <input
                    type="number"
                    className="w-32"
                    min="0.01"
                    step="0.01"
                    placeholder="Selling price"
                    value={priceDrafts[row.layer_id] || ''}
                    onChange={(e) => setPriceDrafts((prev) => ({ ...prev, [row.layer_id]: e.target.value }))}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={async () => {
                      try {
                        const saved = await inventoryAPI.setSalePrice({
                          layer_id: row.layer_id,
                          unit_sell_price: priceDrafts[row.layer_id],
                        });
                        setDeliveries((prev) => prev.map((item) => (
                          item.layer_id === row.layer_id
                            ? {
                              ...item,
                              sale_price_pending: false,
                              unit_sell_price: saved.data.unit_sell_price,
                            }
                            : item
                        )));
                        toast.success('Selling price updated for the pieces still in stock.');
                      } catch (err) {
                        setError(err.response?.data?.error || 'Could not save the selling price.');
                      }
                    }}
                  >
                    {row.sale_price_pending ? 'Save price' : 'Update price'}
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          {isSuperAdmin && deliveries.length > 0 ? (
            <div className="form-group">
              <label>Cost for pieces still in stock</label>
              {deliveries.map((row) => (
                <div key={`cost-${row.layer_id}`} className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="text-sm">{row.quantity} pieces</span>
                  <input
                    type="number"
                    className="w-32"
                    min="0.01"
                    step="0.01"
                    placeholder={row.unit_cost ? `Current ${row.unit_cost}` : 'Cost'}
                    value={costDrafts[row.layer_id] || ''}
                    onChange={(e) => setCostDrafts((prev) => ({ ...prev, [row.layer_id]: e.target.value }))}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={async () => {
                      try {
                        await inventoryAPI.setLayerCost({
                          layer_id: row.layer_id,
                          unit_cost: costDrafts[row.layer_id],
                        });
                        toast.success('Cost saved for the pieces still in stock.');
                      } catch (err) {
                        setError(err.response?.data?.error || 'Could not save the cost.');
                      }
                    }}
                  >
                    Save cost
                  </button>
                </div>
              ))}
            </div>
          ) : null}

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
              : correctingId
                ? 'Send correction'
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
      description={
        selectedVariant && Number(selectedVariant.stock_quantity ?? 0) <= 0
          ? 'This size has no stock yet. Confirm to record these pieces as its first stock.'
          : 'Review the purchase details, then confirm to add stock.'
      }
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
