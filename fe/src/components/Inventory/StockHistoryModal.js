import React, { useState, useEffect } from 'react';
import { inventoryAPI } from '../../services/api';
import { formatCurrency, formatNumber, formatDateTime } from '../../utils/formatters';
import { PageLoading } from '../page';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/cn';

const StockHistoryModal = ({ product, onClose, showCost = true }) => {
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

  const movementTone = (type) => {
    const map = {
      sale: 'destructive',
      purchase: 'default',
      adjustment: 'secondary',
      return: 'secondary',
      damage: 'destructive',
      transfer: 'secondary',
      waste: 'secondary',
      expired: 'secondary',
    };
    return map[type] || 'secondary';
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Stock History — {product?.name}</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">×</button>
        </div>

        <div className="slide-in-panel-body">
          {loading ? (
            <PageLoading rows={5} />
          ) : history.length === 0 ? (
            <div className="rounded-lg border border-dashed px-6 py-10 text-center text-sm text-muted-foreground">
              No stock movements found
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40 text-left text-xs font-medium text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2">Qty</th>
                    {showCost ? <th className="px-3 py-2">Unit Cost</th> : null}
                    {showCost ? <th className="px-3 py-2">Total Cost</th> : null}
                    <th className="px-3 py-2">Before</th>
                    <th className="px-3 py-2">After</th>
                    <th className="px-3 py-2">User</th>
                    <th className="px-3 py-2">Reference</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((movement) => (
                    <tr key={movement.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="whitespace-nowrap px-3 py-2">{formatDateTime(movement.created_at)}</td>
                      <td className="px-3 py-2">
                        <Badge variant={movementTone(movement.movement_type)} className="capitalize">
                          {movement.movement_type}
                        </Badge>
                      </td>
                      <td
                        className={cn(
                          'px-3 py-2 tabular-nums',
                          movement.quantity > 0 ? 'text-emerald-700' : 'text-destructive'
                        )}
                      >
                        {movement.quantity > 0 ? '+' : ''}
                        {formatNumber(movement.quantity)}
                      </td>
                      {showCost ? (
                        <td className="px-3 py-2 tabular-nums">
                          {movement.unit_cost ? formatCurrency(movement.unit_cost) : '-'}
                        </td>
                      ) : null}
                      {showCost ? (
                        <td className="px-3 py-2 tabular-nums">
                          {movement.total_cost ? formatCurrency(movement.total_cost) : '-'}
                        </td>
                      ) : null}
                      <td className="px-3 py-2 tabular-nums">{formatNumber(movement.stock_before || 0)}</td>
                      <td className="px-3 py-2 tabular-nums">{formatNumber(movement.stock_after || 0)}</td>
                      <td className="px-3 py-2">{movement.user_name || '-'}</td>
                      <td className="px-3 py-2">{movement.reference || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StockHistoryModal;
