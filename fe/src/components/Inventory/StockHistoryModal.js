import React, { useState, useEffect, useMemo } from 'react';
import { inventoryAPI } from '../../services/api';
import { formatCurrency, formatNumber, formatDateTime } from '../../utils/formatters';
import { movementSignedQuantity } from '../../utils/inventoryDisplay';
import {
  formatStockTrail,
  stockHistoryMovementTone,
} from '../../utils/stockHistory';
import { variantDisplayLabel } from '../../utils/variantCombinations';
import { PageLoading } from '../page';
import { Badge } from '../ui/badge';
import { Label } from '../ui/label';
import { cn } from '../../lib/cn';

function productHasVariants(product) {
  return Boolean(product?.has_variants) && Array.isArray(product?.variants) && product.variants.length > 0;
}

const StockHistoryModal = ({ product, onClose, showCost = true, embedded = false }) => {
  const variants = useMemo(
    () => (Array.isArray(product?.variants) ? product.variants : []),
    [product?.variants],
  );
  const needsVariant = productHasVariants(product);
  const [variantId, setVariantId] = useState('');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setVariantId('');
    setHistory([]);
    setError('');
  }, [product?.id]);

  useEffect(() => {
    if (!product?.id) return;
    if (needsVariant && !variantId) {
      setHistory([]);
      setLoading(false);
      setError('');
      return;
    }
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when product or variant changes
  }, [product?.id, needsVariant, variantId]);

  const loadHistory = async () => {
    if (!product?.id) return;

    setLoading(true);
    setError('');
    try {
      const params = {};
      if (needsVariant && variantId) {
        params.variant_id = variantId;
      }
      const response = await inventoryAPI.productHistory(product.id, params);
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

  const selectedVariant = variants.find((v) => String(v.id) === String(variantId));

  const body = (
    <>
      {needsVariant ? (
        <div className="mb-4 space-y-1.5" data-testid="stock-history-variant-picker">
          <Label htmlFor="stock-history-variant">Variant</Label>
          <select
            id="stock-history-variant"
            className="h-10 w-full max-w-md rounded-md border bg-background px-3 text-sm"
            value={variantId}
            onChange={(e) => setVariantId(e.target.value)}
          >
            <option value="">Select a variant…</option>
            {variants.map((variant) => (
              <option key={variant.id} value={variant.id}>
                {variantDisplayLabel(variant)}
                {variant.sku ? ` · ${variant.sku}` : ''}
                {variant.stock_quantity != null ? ` (${variant.stock_quantity} on hand)` : ''}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted-foreground">
            Stock is tracked per variant — pick one to see its movement trail.
          </p>
        </div>
      ) : null}

      {needsVariant && !variantId ? (
        <div className="rounded-lg border border-dashed px-6 py-10 text-center text-sm text-muted-foreground">
          Choose a variant above to load its stock history.
        </div>
      ) : loading ? (
        <PageLoading rows={5} />
      ) : error ? (
        <div className="rounded-lg border border-dashed px-6 py-10 text-center text-sm text-destructive">
          {error}
        </div>
      ) : history.length === 0 ? (
        <div className="rounded-lg border border-dashed px-6 py-10 text-center text-sm text-muted-foreground">
          No stock movements yet
          {selectedVariant ? ` for ${variantDisplayLabel(selectedVariant)}` : ''}.
          Opening stock, sales, purchases, and adjustments appear here.
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            {selectedVariant
              ? `Ledger for ${variantDisplayLabel(selectedVariant)}. Each row shows previous stock, what changed, new stock, and who did it.`
              : 'Full ledger since this product was added. Each row shows previous stock, what changed, new stock, and who did it.'}
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
