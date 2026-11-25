import React, { useEffect, useMemo, useState } from 'react';
import { inventoryAPI, productsAPI, variantsAPI } from '../../services/api';
import { variantDisplayLabel } from '../../utils/variantCombinations';
import SearchableSelect from '../Shared/SearchableSelect';
import CommitConfirm from '../Shared/CommitConfirm';

/**
 * A manager sets the count of pieces already on the shelf.
 * The selling price and MRP stay as they are.
 */
const CorrectCountModal = ({ onClose, onSave }) => {
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState('');
  const [variants, setVariants] = useState([]);
  const [variantId, setVariantId] = useState('');
  const [count, setCount] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    let cancelled = false;
    productsAPI.list({
      track_stock: 'true',
      is_active: 'true',
      page_size: 200,
    }).then((response) => {
      if (cancelled) return;
      const rows = response.data.results || response.data || [];
      setProducts(Array.isArray(rows) ? rows : []);
    }).catch(() => {
      if (!cancelled) setProducts([]);
    });
    return () => { cancelled = true; };
  }, []);

  const selected = useMemo(
    () => products.find((row) => Number(row.id) === Number(productId)),
    [products, productId],
  );
  const selectedVariant = variants.find((row) => Number(row.id) === Number(variantId));
  const nextCount = Number(count);
  const current = Number(
    selectedVariant?.stock_quantity ?? selected?.stock_quantity ?? 0
  );

  useEffect(() => {
    if (!selected?.has_variants) {
      setVariants([]);
      setVariantId('');
      return;
    }
    let cancelled = false;
    variantsAPI.getByProduct(selected.id).then((response) => {
      if (cancelled) return;
      const rows = response.data.results || response.data || [];
      setVariants(Array.isArray(rows) ? rows.filter((row) => row.is_active !== false) : []);
    }).catch(() => {
      if (!cancelled) setVariants([]);
    });
    return () => { cancelled = true; };
  }, [selected?.id, selected?.has_variants]);

  const review = () => {
    setError('');
    if (!selected) {
      setError('Choose a product.');
      return;
    }
    if (selected.has_variants && !variantId) {
      setError('Choose a size and colour.');
      return;
    }
    if (!Number.isInteger(nextCount) || nextCount < 0 || nextCount > 1000000) {
      setError('Enter a whole count from 0 to 1000000.');
      return;
    }
    setConfirming(true);
  };

  const save = async () => {
    setLoading(true);
    try {
      await inventoryAPI.setOnHand({
        product_id: selected.id,
        quantity: nextCount,
        ...(variantId ? { variant_id: Number(variantId) } : {}),
      });
      setConfirming(false);
      onSave();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not update the count.');
      setConfirming(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="slide-in-overlay" onClick={onClose}>
        <div className="slide-in-panel" onClick={(event) => event.stopPropagation()}>
          <div className="slide-in-panel-header">
            <h2>Correct the count</h2>
            <button type="button" onClick={onClose} className="slide-in-panel-close">×</button>
          </div>
          <div className="slide-in-panel-body">
            {error ? <div className="error-message">{error}</div> : null}
            <div className="form-group">
              <label>Product</label>
              <SearchableSelect
                value={productId}
                onChange={(event) => setProductId(event.target.value)}
                options={products.map((row) => ({
                  id: row.id,
                  name: `${row.name}${row.sku ? ` (${row.sku})` : ''} - Stock: ${row.stock_quantity ?? 0}`,
                }))}
                placeholder="Search any product, including those already in stock"
                name="product_id"
                searchable
              />
            </div>
            {selected?.has_variants ? (
              <div className="form-group">
                <label>Size and colour</label>
                <select value={variantId} onChange={(event) => setVariantId(event.target.value)}>
                  <option value="">Choose a size and colour</option>
                  {variants.map((row) => (
                    <option key={row.id} value={row.id}>
                      {variantDisplayLabel(row)} — Stock: {row.stock_quantity ?? 0}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            {selected ? (
              <p className="text-sm">On the shelf now: {current}</p>
            ) : null}
            <div className="form-group">
              <label>Count on the shelf</label>
              <input
                type="number"
                min="0"
                max="1000000"
                value={count}
                onChange={(event) => setCount(event.target.value)}
              />
              <small>This changes the number of pieces only. Selling price and MRP stay as they are.</small>
            </div>
          </div>
          <div className="slide-in-panel-footer">
            <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
            <button type="button" onClick={review} className="btn btn-primary">Review</button>
          </div>
        </div>
      </div>
      <CommitConfirm
        open={confirming}
        onOpenChange={(open) => { if (!open) setConfirming(false); }}
        title="Update this count?"
        description="The pieces already on the shelf keep their selling price."
        rows={[
          { label: 'Product', value: selected?.name || '—' },
          ...(selectedVariant
            ? [{ label: 'Size and colour', value: variantDisplayLabel(selectedVariant) }]
            : []),
          { label: 'On the shelf now', value: String(current) },
          { label: 'Count after save', value: String(nextCount), emphasis: true },
        ]}
        submitting={loading}
        confirmText="Save count"
        onConfirm={save}
      />
    </>
  );
};

export default CorrectCountModal;
