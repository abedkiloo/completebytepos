import React, { useState, useEffect } from 'react';
import { inventoryAPI } from '../../services/api';
import { formatCurrency, formatNumber, formatDateTime } from '../../utils/formatters';
import { movementSignedQuantity } from '../../utils/inventoryDisplay';
import {
  formatStockTrail,
  stockHistoryMovementTone,
} from '../../utils/stockHistory';
import { PageLoading } from '../page';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/cn';

const StockHistoryModal = ({ product, onClose, showCost = true, embedded = false }) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadHistory();
  }, [product?.id]);

  const loadHistory = async () => {
    if (!product?.id) return;

    setLoading(true);
    setError('');
    try {
      const response = await inventoryAPI.productHistory(product.id);
      setHistory(response.data || []);
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        'Could not load stock history. Admins only when enabled in settings.';
      setError(msg);
      setHistory([]);
    } finally {
      setLoading(false);
    }
  };

  const body = (
    <>
      {loading ? (
        <PageLoading rows={5} />
      ) : error ? (
        <div className="rounded-lg border border-dashed px-6 py-10 text-center text-sm text-destructive">
          {error}
        </div>
      ) : history.length === 0 ? (
        <div className="rounded-lg border border-dashed px-6 py-10 text-center text-sm text-muted-foreground">
          No stock movements yet. Opening stock, sales, purchases, and adjustments
          appear here — same idea as debt payments on a customer.
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Full ledger since this product was added. Each row shows previous stock,
            what changed, new stock, and who did it.
          </p>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm" data-testid="stock-history-table">
              <thead className="border-b bg-muted/40 text-left text-xs font-medium text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Stock flow</th>
                  <th className="px-3 py-2">Qty</th>
                  {showCost ? <th className="px-3 py-2">Unit Cost</th> : null}
                  <th className="px-3 py-2">Reference</th>
                </tr>
              </thead>
              <tbody>
                {history.map((movement) => {
                  const qty = movementSignedQuantity(movement);
                  return (
                    <tr
                      key={movement.id}
                      className="border-b last:border-0 hover:bg-muted/30"
                      data-testid={`stock-history-row-${movement.id}`}
                    >
                      <td className="whitespace-nowrap px-3 py-2">
                        {formatDateTime(movement.created_at)}
                      </td>
                      <td className="px-3 py-2">
                        <Badge
                          variant={stockHistoryMovementTone(movement.movement_type)}
                          className="capitalize"
                        >
                          {movement.movement_type}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-xs leading-snug">
                        {formatStockTrail(movement)}
                      </td>
                      <td
                        className={cn(
                          'px-3 py-2 tabular-nums',
                          qty > 0 ? 'text-emerald-700' : 'text-destructive'
                        )}
                      >
                        {qty > 0 ? '+' : ''}
                        {formatNumber(qty)}
                      </td>
                      {showCost ? (
                        <td className="px-3 py-2 tabular-nums">
                          {movement.unit_cost ? formatCurrency(movement.unit_cost) : '-'}
                        </td>
                      ) : null}
                      <td className="px-3 py-2">{movement.reference || '-'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );

  if (embedded) {
    return <div data-testid="stock-history-embedded">{body}</div>;
  }

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel max-w-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Stock History — {product?.name}</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">
            ×
          </button>
        </div>
        <div className="slide-in-panel-body">{body}</div>
      </div>
    </div>
  );
};

export default StockHistoryModal;
