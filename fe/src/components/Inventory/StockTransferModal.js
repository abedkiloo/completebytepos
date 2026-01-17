import React, { useState, useEffect } from 'react';
import { inventoryAPI, productsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import './Inventory.css';

const StockTransferModal = ({ isOpen, onClose, onSuccess, product }) => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    quantity: '',
    reference: '',
    notes: '',
  });

  useEffect(() => {
    if (isOpen) {
      if (!product) {
        loadProducts();
      } else {
        setFormData(prev => ({ ...prev, product_id: product.id }));
      }
    }
  }, [isOpen, product]);

  const loadProducts = async () => {
    try {
      const response = await productsAPI.list({ track_stock: true, is_active: true });
      const productsData = response.data.results || response.data || [];
      setProducts(Array.isArray(productsData) ? productsData : []);
    } catch (error) {
      console.error('Error loading products:', error);
      toast.error('Failed to load products');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const transferData = {
        product_id: parseInt(formData.product_id),
        quantity: parseInt(formData.quantity),
        reference: formData.reference || '',
        notes: formData.notes || '',
      };

      await inventoryAPI.transfer(transferData);
      toast.success('Stock transferred successfully');
      onSuccess();
      onClose();
      // Reset form
      setFormData({
        product_id: product?.id || '',
        quantity: '',
        reference: '',
        notes: '',
      });
    } catch (error) {
      toast.error('Failed to transfer stock: ' + (error.response?.data?.error || error.message));
    } finally {
      setLoading(false);
    }
  };

  const selectedProduct = product || products.find(p => p.id === parseInt(formData.product_id));

  if (!isOpen) return null;

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Stock Transfer</h2>
          <button onClick={onClose} className="slide-in-panel-close">×</button>
        </div>
        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="modal-body">
          {!product && (
            <div className="form-group">
              <label>Product *</label>
              <select
                value={formData.product_id}
                onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
                required
              >
                <option value="">Select Product</option>
                {products.map(prod => (
                  <option key={prod.id} value={prod.id}>
                    {prod.name} {prod.sku ? `(${prod.sku})` : ''} - Stock: {prod.stock_quantity || 0}
                  </option>
                ))}
              </select>
            </div>
          )}

          {selectedProduct && (
            <div className="form-group">
              <label>Current Stock</label>
              <input
                type="text"
                value={`${selectedProduct.stock_quantity || 0} units`}
                disabled
                className="form-control"
              />
            </div>
          )}

          <div className="form-group">
            <label>Quantity to Transfer *</label>
            <input
              type="number"
              value={formData.quantity}
              onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
              min="1"
              max={selectedProduct?.stock_quantity || ''}
              required
              placeholder="Enter quantity"
            />
            {selectedProduct && (
              <small className="form-text text-muted">
                Available: {selectedProduct.stock_quantity || 0} units
              </small>
            )}
          </div>

          <div className="form-group">
            <label>Reference</label>
            <input
              type="text"
              value={formData.reference}
              onChange={(e) => setFormData({ ...formData, reference: e.target.value })}
              placeholder="e.g., TRF-001, Transfer to Branch B"
            />
          </div>

          <div className="form-group">
            <label>Notes</label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              rows="3"
              placeholder="Optional notes about this transfer"
            />
          </div>
          </form>
        </div>
        <div className="slide-in-panel-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button type="submit" onClick={handleSubmit} disabled={loading || !formData.product_id || !formData.quantity} className="btn btn-primary">
            {loading ? 'Transferring...' : 'Transfer Stock'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default StockTransferModal;
