import React, { useState, useEffect } from 'react';
import { inventoryAPI } from '../../services/api';
import { formatCurrency, formatNumber, formatDateTime } from '../../utils/formatters';
import './Inventory.css';

const StockHistoryModal = ({ product, onClose }) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHistory();
  }, [product]);

  const loadHistory = async () => {
    if (!product?.id) return;
    
    setLoading(true);
    try {
      const response = await inventoryAPI.productHistory(product.id);
      setHistory(response.data);
    } catch (error) {
      console.error('Error loading history:', error);
    } finally {
      setLoading(false);
    }
  };

  const getMovementTypeColor = (type) => {
    const colors = {
      'sale': '#ef4444',
      'purchase': '#10b981',
      'adjustment': '#f59e0b',
      'return': '#3b82f6',
      'damage': '#dc2626',
      'transfer': '#8b5cf6',
      'waste': '#f97316',
      'expired': '#6b7280',
    };
    return colors[type] || '#6b7280';
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content history-modal">
        <div className="modal-header">
          <h2>Stock History - {product?.name}</h2>
          <button onClick={onClose} className="close-btn">×</button>
        </div>

        {loading ? (
          <div className="loading">Loading history...</div>
        ) : (
          <div className="history-content">
            {history.length === 0 ? (
              <div className="empty-state">No stock movements found</div>
            ) : (
              <table className="history-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Quantity</th>
                    <th>Unit Cost</th>
                    <th>Total Cost</th>
                    <th>Stock Before</th>
                    <th>Stock After</th>
                    <th>User</th>
                    <th>Reference</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(movement => (
                    <tr key={movement.id}>
                      <td>{formatDateTime(movement.created_at)}</td>
                      <td>
                        <span
                          className="movement-type-badge"
                          style={{ backgroundColor: getMovementTypeColor(movement.movement_type) }}
                        >
                          {movement.movement_type}
                        </span>
                      </td>
                      <td className={movement.quantity > 0 ? 'positive' : 'negative'}>
                        {movement.quantity > 0 ? '+' : ''}{formatNumber(movement.quantity)}
                      </td>
                      <td>{movement.unit_cost ? formatCurrency(movement.unit_cost) : '-'}</td>
                      <td>{movement.total_cost ? formatCurrency(movement.total_cost) : '-'}</td>
                      <td>{formatNumber(movement.stock_before || 0)}</td>
                      <td>{formatNumber(movement.stock_after || 0)}</td>
                      <td>{movement.user_name || '-'}</td>
                      <td>{movement.reference || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default StockHistoryModal;

