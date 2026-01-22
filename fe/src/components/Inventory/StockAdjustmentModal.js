import React, { useState, useEffect } from 'react';
import { inventoryAPI, productsAPI } from '../../services/api';
import SearchableSelect from '../Shared/SearchableSelect';
import './Inventory.css';

const StockAdjustmentModal = ({ product, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    quantity: 0,
    notes: '',
  });
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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

  // Transform products for SearchableSelect component
  const productOptions = products.map(prod => ({
    id: prod.id,
    name: `${prod.name}${prod.sku ? ` (${prod.sku})` : ''} - Stock: ${prod.stock_quantity || 0}`,
  }));

  const handleProductChange = (e) => {
    const productId = e.target.value;
    setFormData(prev => ({
      ...prev,
      product_id: productId ? parseInt(productId) : ''
    }));
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'quantity' || name === 'product_id' ? parseInt(value) || 0 : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await inventoryAPI.adjust(formData);
      onSave();
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to adjust stock');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h2>Stock Adjustment</h2>
          <button onClick={onClose} className="close-btn">×</button>
        </div>

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
            <small>Enter positive number to add stock, negative to remove</small>
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

          <div className="form-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" disabled={loading}>
              {loading ? 'Adjusting...' : 'Adjust Stock'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default StockAdjustmentModal;

