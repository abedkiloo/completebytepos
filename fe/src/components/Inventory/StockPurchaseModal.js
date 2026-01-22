import React, { useState, useEffect } from 'react';
import { inventoryAPI, productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import SearchableSelect from '../Shared/SearchableSelect';
import '../../styles/slide-in-panel.css';
import './Inventory.css';

const StockPurchaseModal = ({ product, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    quantity: product?.reorder_quantity || 0,
    unit_cost: product?.cost || '',
    reference: '',
    notes: '',
  });
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!product) {
      loadProducts();
    } else {
      setFormData(prev => ({
        ...prev,
        product_id: product.id,
        quantity: product.reorder_quantity || 0,
        unit_cost: product.cost || '',
      }));
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
    name: `${prod.name}${prod.sku ? ` (${prod.sku})` : ''} - Current: ${prod.stock_quantity || 0}`,
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
      [name]: name === 'quantity' || name === 'product_id' 
        ? parseInt(value) || 0 
        : name === 'unit_cost'
        ? parseFloat(value) || 0
        : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await inventoryAPI.purchase(formData);
      onSave();
    } catch (error) {
      setError(error.response?.data?.error || 'Failed to record purchase');
    } finally {
      setLoading(false);
    }
  };

  const totalCost = formData.quantity * (formData.unit_cost || 0);

  return (
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
            </div>

            <div className="form-group">
              <label>Unit Cost (KES)</label>
              <input
                type="number"
                name="unit_cost"
                value={formData.unit_cost}
                onChange={handleChange}
                step="0.01"
                min="0"
                placeholder="Auto from product cost"
              />
            </div>
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

          </form>
        </div>
        <div className="slide-in-panel-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button type="submit" onClick={handleSubmit} disabled={loading} className="btn btn-primary">
            {loading ? 'Recording...' : 'Record Purchase'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default StockPurchaseModal;

