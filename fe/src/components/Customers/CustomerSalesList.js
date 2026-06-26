import React, { useCallback, useEffect, useState } from 'react';
import { Receipt } from 'lucide-react';
import { salesAPI } from '../../services/api';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { refundStatusLabel } from '../../utils/saleRefund';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { ListPaginationRail } from '../page';

/**
 * Paginated completed sales for a customer; row click opens sale detail.
 */
export default function CustomerSalesList({ customerId, onSelectSale }) {
  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    count: 0,
  });

  const loadSales = useCallback(async () => {
    if (!customerId) return;
    setLoading(true);
    try {
      const res = await salesAPI.list({
        customer_id: customerId,
        status: 'completed',
        page: pagination.page,
        page_size: pagination.page_size,
      });
      const rows = res.data?.results || res.data || [];
      setSales(Array.isArray(rows) ? rows : []);
      setPagination((prev) => ({
        ...prev,
        count: res.data?.count ?? (Array.isArray(rows) ? rows.length : 0),
      }));
    } catch {
      setSales([]);
    } finally {
      setLoading(false);
    }
  }, [customerId, pagination.page, pagination.page_size]);

  useEffect(() => {
    setPagination((prev) => ({ ...prev, page: 1 }));
  }, [customerId]);

  useEffect(() => {
    loadSales();
  }, [loadSales]);

  if (!customerId) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-1.5 text-sm font-semibold">
        <Receipt className="h-4 w-4 text-muted-foreground" />
        Sales history
      </div>

      <ListPaginationRail
        page={pagination.page}
        pageSize={pagination.page_size}
        totalCount={pagination.count}
        suffix="sales"
        onPageChange={(nextPage) =>
          setPagination((prev) => ({ ...prev, page: nextPage }))
        }
      >
        <div className="overflow-hidden rounded-lg border">
          {loading && sales.length === 0 ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : sales.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No completed sales for this customer yet.
            </p>
          ) : (
            <ul className="divide-y">
              {sales.map((sale) => {
                const itemCount =
                  sale.item_count ??
                  sale.items?.reduce(
                    (sum, row) => sum + (parseInt(row.quantity, 10) || 0),
                    0
                  ) ??
                  0;
                const refundLabel = refundStatusLabel(sale.refund_status);
                return (
                  <li key={sale.id}>
                    <button
                      type="button"
                      className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50"
                      onClick={() => onSelectSale?.(sale)}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{sale.sale_number}</span>
                          {refundLabel ? (
                            <Badge variant="secondary" className="text-xs">
                              {refundLabel}
                            </Badge>
                          ) : null}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {formatDateTime(sale.created_at)} · {itemCount}{' '}
                          {itemCount === 1 ? 'item' : 'items'} ·{' '}
                          {sale.payment_method || '—'}
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="font-semibold tabular-nums">
                          {formatCurrency(sale.total)}
                        </div>
                        {parseFloat(sale.amount_paid) <
                          parseFloat(sale.total) - 0.009 ? (
                          <div className="text-xs text-amber-700">
                            Paid {formatCurrency(sale.amount_paid)}
                          </div>
                        ) : null}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </ListPaginationRail>
    </div>
  );
}
