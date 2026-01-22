import React, { useState, useEffect } from 'react';
import { inventoryAPI, productsAPI, branchesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import SearchableSelect from '../Shared/SearchableSelect';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import './Inventory.css';

const StockTransferModal = ({ isOpen, onClose, onSuccess, product }) => {
  const [products, setProducts] = useState([]);
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [transferResult, setTransferResult] = useState(null);
  const [formData, setFormData] = useState({
    product_id: product?.id || '',
    to_branch_id: '',
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
      loadBranches();
      // Reset state when modal opens
      setTransferResult(null);
      setShowConfirm(false);
      setLoading(false);  // Reset loading state when modal opens
    }
  }, [isOpen, product]);

  const loadProducts = async () => {
    try {
      // Load all products that track stock - request large page size to get all
      const response = await productsAPI.list({ track_stock: true, is_active: true, page_size: 1000 });
      const productsData = response.data.results || response.data || [];
      setProducts(Array.isArray(productsData) ? productsData : []);
    } catch (error) {
      console.error('Error loading products:', error);
      toast.error('Failed to load products');
    }
  };

  const loadBranches = async () => {
    try {
      const response = await branchesAPI.list({ is_active: true, page_size: 1000 });
      const branchesData = response.data.results || response.data || [];
      setBranches(Array.isArray(branchesData) ? branchesData : []);
    } catch (error) {
      console.error('Error loading branches:', error);
      toast.error('Failed to load branches');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.product_id || !formData.to_branch_id || !formData.quantity) {
      toast.error('Please fill in all required fields');
      return;
    }
    
    // Show confirmation dialog
    setShowConfirm(true);
  };

  const confirmTransfer = async () => {
    setShowConfirm(false);
    setLoading(true);

    try {
      const transferData = {
        product_id: parseInt(formData.product_id),
        to_branch_id: parseInt(formData.to_branch_id),
        quantity: parseInt(formData.quantity),
        reference: formData.reference || '',
        notes: formData.notes || '',
      };

      const response = await inventoryAPI.transfer(transferData);
      const result = response.data;
      
      // Store transfer result for undo option
      setTransferResult({
        movements: result.movements || [result.movement] || [],
        message: result.message || 'Stock transferred successfully'
      });
      
      toast.success(result.message || 'Stock transferred successfully');
      setLoading(false);  // Reset loading state after successful transfer
      onSuccess();
      
      // Don't close modal yet - show undo option
    } catch (error) {
      toast.error('Failed to transfer stock: ' + (error.response?.data?.error || error.message));
      setLoading(false);
    }
  };

  const handleUndo = async (movementId) => {
    if (!window.confirm('Are you sure you want to undo this transfer? This action cannot be undone.')) {
      return;
    }

    try {
      await inventoryAPI.undo(movementId);
      toast.success('Transfer undone successfully');
      setTransferResult(null);
      onSuccess();
      onClose();
      // Reset form
      setFormData({
        product_id: product?.id || '',
        to_branch_id: '',
        quantity: '',
        reference: '',
        notes: '',
      });
    } catch (error) {
      toast.error('Failed to undo transfer: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleCloseAfterTransfer = () => {
    setTransferResult(null);
    onClose();
    // Reset form
    setFormData({
      product_id: product?.id || '',
      to_branch_id: '',
      quantity: '',
      reference: '',
      notes: '',
    });
  };

  const selectedProduct = product || products.find(p => p.id === parseInt(formData.product_id));

  // Transform products for SearchableSelect component
  const productOptions = products.map(prod => ({
    id: prod.id,
    name: `${prod.name}${prod.sku ? ` (${prod.sku})` : ''} - Stock: ${prod.stock_quantity || 0}`,
  }));

  const handleProductChange = (e) => {
    const productId = e.target.value;
    setFormData({ ...formData, product_id: productId });
  };

  const handleBranchChange = (e) => {
    const branchId = e.target.value;
    setFormData({ ...formData, to_branch_id: branchId });
  };

  // Transform branches for SearchableSelect component
  const branchOptions = branches.map(branch => ({
    id: branch.id,
    name: branch.name,
  }));

  if (!isOpen) return null;

  const handleClose = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    onClose();
  };

  return (
    <div className="slide-in-overlay" onClick={handleClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Stock Transfer</h2>
          <button onClick={handleClose} className="slide-in-panel-close" type="button">×</button>
        </div>
        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="modal-body">
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
            <label>Transfer To Branch *</label>
            <SearchableSelect
              value={formData.to_branch_id || ''}
              onChange={handleBranchChange}
              options={branchOptions}
              placeholder="Search and select destination branch..."
              name="to_branch_id"
              searchable={true}
            />
          </div>

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
          {transferResult ? (
            <>
              <div style={{ marginBottom: '1rem', padding: '1rem', background: '#d1fae5', borderRadius: '6px' }}>
                <p style={{ margin: 0, color: '#065f46', fontWeight: '600' }}>✓ {transferResult.message}</p>
                {transferResult.movements && transferResult.movements.length > 0 && (
                  <div style={{ marginTop: '0.5rem' }}>
                    {transferResult.movements.map((movement, idx) => (
                      <button
                        key={movement.id || idx}
                        type="button"
                        onClick={() => handleUndo(movement.id)}
                        className="btn btn-secondary"
                        style={{ marginRight: '0.5rem', marginTop: '0.5rem' }}
                      >
                        Undo Transfer
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <button type="button" onClick={handleCloseAfterTransfer} className="btn btn-primary">
                Close
              </button>
            </>
          ) : (
            <>
              <button type="button" onClick={handleClose} className="btn btn-secondary">Cancel</button>
              <button type="button" onClick={handleSubmit} disabled={loading || !formData.product_id || !formData.to_branch_id || !formData.quantity} className="btn btn-primary">
                {loading ? 'Transferring...' : 'Transfer Stock'}
              </button>
            </>
          )}
        </div>
      </div>

      <ConfirmDialog
        isOpen={showConfirm}
        title="Confirm Stock Transfer"
        message={`Do you want to transfer ${formData.quantity} units of ${selectedProduct?.name || 'the selected product'} to ${branches.find(b => b.id === parseInt(formData.to_branch_id))?.name || 'the selected branch'}?`}
        onConfirm={confirmTransfer}
        onCancel={() => setShowConfirm(false)}
        confirmText="Yes, Transfer"
        cancelText="Cancel"
        type="primary"
      />
    </div>
  );
};

export default StockTransferModal;
