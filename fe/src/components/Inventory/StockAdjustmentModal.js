import React, { useState, useEffect } from 'react';
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

const StockAdjustmentModal = ({ product, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    quantity: 0,
    notes: '',
  });
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  useEffect(() => {
    if (!product) {
      loadProducts();
    } else {
      setFormData(prev => ({ ...prev, product_id: product.id }));
    }
  }, [product]);

  const loadProducts = async () => {
    try {
      const response = await productsAPI.list({ track_stock: 'true', is_active: 'true', page_size: 1000 });
      const productsData = response.data.results || response.data || [];
      setProducts(Array.isArray(productsData) ? productsData : []);
    } catch (error) {
      console.error('Error loading products:', error);
    }
  };

  const productOptions = products.map(prod => ({
    id: prod.id,
    name: `${prod.name}${prod.sku ? ` (${prod.sku})` : ''} - Stock: ${prod.stock_quantity || 0}`,
  }));

  const handleProductChange = (e) => {
    const productId = e.target.value;
    setFormData(prev => ({
      ...prev,
      product_id: productId ? parseInt(productId, 10) : '',
    }));
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'quantity' || name === 'product_id' ? parseInt(value, 10) || 0 : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const payload = { ...formData };
      if (makerCheckerOn) {
        if (!changeReason.trim()) {
          setError('A reason is required for stock changes.');
          setLoading(false);
          return;
        }
        payload.reason = changeReason.trim();
      }
      const res = await inventoryAPI.adjust(payload);
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      }
      onSave();
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to adjust stock');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Stock Adjustment</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">×</button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit}>
            {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}

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

            <div className="form-group">
              <label>Adjustment Quantity *</label>
              <input
                type="number"
                name="quantity"
                value={formData.quantity}
                onChange={handleChange}
                required
                placeholder="Positive to add, negative to remove"
              />
              <small className="form-text">Enter positive number to add stock, negative to remove</small>
            </div>

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
              <Button type="submit" disabled={loading}>
                {loading
                  ? 'Submitting…'
                  : makerCheckerOn
                    ? 'Submit for approval'
                    : 'Adjust Stock'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default StockAdjustmentModal;
