import React, { useState, useEffect } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { inventoryAPI, productsAPI } from '../../services/api';
import SearchableSelect from '../Shared/SearchableSelect';
import { Button } from '../ui/button';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import { toast } from '../../utils/toast';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  PENDING_APPROVAL_MESSAGE,
} from '../../utils/makerChecker';

const emptyLine = () => ({ product_id: '', quantity: '', notes: '' });

const StockBulkAdjustModal = ({ onClose, onSave }) => {
  const [lines, setLines] = useState([emptyLine(), emptyLine()]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  useEffect(() => {
    loadProducts();
  }, []);

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

  const productOptions = products.map((prod) => ({
    id: prod.id,
    name: `${prod.name}${prod.sku ? ` (${prod.sku})` : ''} — stock ${prod.stock_quantity ?? 0}`,
  }));

  const updateLine = (index, field, value) => {
    setLines((prev) =>
      prev.map((line, i) =>
        i === index
          ? {
              ...line,
              [field]: field === 'product_id' ? (value ? parseInt(value, 10) : '') : value,
            }
          : line
      )
    );
  };

  const addLine = () => setLines((prev) => [...prev, emptyLine()]);

  const removeLine = (index) => {
    setLines((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const adjustments = lines
      .filter((line) => line.product_id && line.quantity !== '' && line.quantity !== undefined)
      .map((line) => ({
        product_id: line.product_id,
        quantity: parseInt(line.quantity, 10) || 0,
        notes: line.notes || '',
      }));

    if (!adjustments.length) {
      setError('Add at least one product with a quantity.');
      return;
    }
    if (makerCheckerOn && !changeReason.trim()) {
      setError('A reason is required for bulk stock changes.');
      return;
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
              Submit several quantity changes in one request. Use negative quantities to reduce stock.
            </p>

            {lines.map((line, index) => (
              <div
                key={index}
                className="grid gap-2 rounded-md border border-border p-3 sm:grid-cols-[1fr_120px_1fr_auto]"
              >
                <div className="form-group sm:col-span-1">
                  <label>Product *</label>
                  <SearchableSelect
                    value={line.product_id || ''}
                    onChange={(e) => updateLine(index, 'product_id', e.target.value)}
                    options={productOptions}
                    placeholder="Select product…"
                    name={`product_${index}`}
                    searchable
                  />
                </div>
                <div className="form-group">
                  <label>Qty *</label>
                  <input
                    type="number"
                    value={line.quantity}
                    onChange={(e) => updateLine(index, 'quantity', e.target.value)}
                    placeholder="+/-"
                    required={!!line.product_id}
                  />
                </div>
                <div className="form-group">
                  <label>Notes</label>
                  <input
                    type="text"
                    value={line.notes}
                    onChange={(e) => updateLine(index, 'notes', e.target.value)}
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
            ))}

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
