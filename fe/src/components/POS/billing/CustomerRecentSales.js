import React, { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, Receipt } from 'lucide-react';
import { salesAPI } from '../../../services/api';
import { formatCurrency, formatDateTime } from '../../../utils/formatters';
import { cartVariantLabel } from '../../../utils/variantCombinations';
import { refundStatusLabel } from '../../../utils/saleRefund';
import {
  saleDisplayTotal,
  saleHasRefundActivity,
  saleItemNetQuantity,
  saleItemNetSubtotal,
  saleNetItemCount,
} from '../../../utils/saleItemDisplay';
import { Badge } from '../../ui/badge';

/**
 * Recent completed sales for the selected customer (one batch per sale).
 */
export default function CustomerRecentSales({ customerId }) {
  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    if (!customerId) {
      setSales([]);
      setExpandedId(null);
      return;
    }
    let mounted = true;
    const load = async () => {
      setLoading(true);
      try {
        const res = await salesAPI.list({
          customer_id: customerId,
          status: 'completed',
          page_size: 10,
        });
        if (!mounted) return;
        const rows = res.data?.results || res.data || [];
        setSales(Array.isArray(rows) ? rows : []);
      } catch {
        if (mounted) setSales([]);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [customerId]);

  if (!customerId) return null;

  return (
    <div className="mt-3 border-t pt-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Receipt className="h-3.5 w-3.5" />
        Recent sales
      </div>
      {loading ? (
        <p className="text-xs text-muted-foreground">Loading sales…</p>
      ) : sales.length === 0 ? (
        <p className="text-xs text-muted-foreground">No completed sales for this customer yet.</p>
      ) : (
        <ul className="max-h-48 space-y-1 overflow-y-auto rounded-lg border bg-muted/20 p-1">
          {sales.map((sale) => {
            const expanded = expandedId === sale.id;
            const hasRefund = saleHasRefundActivity(sale);
            const itemCount = hasRefund
              ? saleNetItemCount(sale)
              : sale.item_count ??
                sale.items?.reduce((sum, row) => sum + (parseInt(row.quantity, 10) || 0), 0) ??
                0;
            const originalItemCount = hasRefund
              ? sale.item_count ??
                sale.items?.reduce((sum, row) => sum + (parseInt(row.quantity, 10) || 0), 0) ??
                0
              : itemCount;
            const refundLabel = refundStatusLabel(sale.refund_status);
            const displayTotal = saleDisplayTotal(sale);
            return (
              <li key={sale.id} className="rounded-md bg-background">
                <button
                  type="button"
                  className="flex w-full items-start gap-2 px-2 py-2 text-left text-sm hover:bg-accent/50"
                  onClick={() => setExpandedId(expanded ? null : sale.id)}
                >
                  {expanded ? (
                    <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="truncate font-medium">{sale.sale_number}</span>
                        {refundLabel ? (
                          <Badge variant="secondary" className="text-[10px]">
                            {refundLabel}
                          </Badge>
                        ) : null}
                      </div>
                      <span className="shrink-0 tabular-nums font-medium">
                        {formatCurrency(displayTotal)}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatDateTime(sale.created_at)} · {itemCount}
                      {hasRefund && itemCount !== originalItemCount
                        ? ` of ${originalItemCount}`
                        : ''}{' '}
                      {itemCount === 1 ? 'unit' : 'units'}
                      {hasRefund ? ` · was ${formatCurrency(sale.total)}` : ''}
                    </div>
                  </div>
                </button>
                {expanded && sale.items?.length ? (
                  <ul className="border-t px-3 py-2 text-xs text-muted-foreground">
                    {sale.items
                      .filter((item) => saleItemNetQuantity(item) > 0)
                      .map((item) => {
                      const label = cartVariantLabel({
                        variant_id: item.variant,
                        variant: item.variant
                          ? {
                              id: item.variant,
                              size_name: item.size_name,
                              color_name: item.color_name,
                            }
                          : null,
                        size_name: item.size_name,
                        color_name: item.color_name,
                      });
                      const netQty = saleItemNetQuantity(item);
                      const lineTotal = saleItemNetSubtotal(item);
                      return (
                        <li
                          key={item.id}
                          className="flex justify-between gap-2 border-b border-dashed border-border/60 py-1 last:border-0"
                        >
                          <span className="min-w-0">
                            <span className="text-foreground">
                              {item.product_name || item.product?.name || 'Item'}
                            </span>
                            {label ? (
                              <span className="block text-[11px]">{label}</span>
                            ) : null}
                            <span className="tabular-nums"> × {netQty}</span>
                          </span>
                          <span className="shrink-0 tabular-nums text-foreground">
                            {formatCurrency(lineTotal)}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
