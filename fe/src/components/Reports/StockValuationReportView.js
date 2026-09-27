import React, { useCallback, useEffect, useState } from 'react';
import { Package } from 'lucide-react';

import { reportsAPI } from '../../services/api';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { reportsShowCostAndProfit } from '../../utils/reportDisplay';
import { resolveStoreName, DEFAULT_STORE_TAGLINE } from '../../utils/storeBranding';
import { formatCurrency, formatDateTime, formatNumber } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { EmptyState, PageLoading } from '../page';
import { R } from './reportUI';
import ReportExportButtons from './ReportExportButtons';
import BrandMark from '../Shared/BrandMark';

const NUM = '!text-right tabular-nums whitespace-nowrap';
const HEAD_NUM = `${NUM} font-medium`;

export default function StockValuationReportView() {
  const { settings } = useStoreSettings();
  const { settings: reportSettings } = useModuleSettings('reports');
  const showCost = reportsShowCostAndProfit(reportSettings);
  const storeName = resolveStoreName(settings);
  const [includeZero, setIncludeZero] = useState(false);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  const loadReport = useCallback(async () => {
    setLoading(true);
    try {
      const response = await reportsAPI.stockValuation({
        include_zero: includeZero ? '1' : undefined,
      });
      setData(response.data);
    } catch (error) {
      setData(null);
      toast.error('Could not load stock valuation');
    } finally {
      setLoading(false);
    }
  }, [includeZero]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const summary = data?.summary || {};
  const items = data?.items || data?.lines || [];
  const exportParams = includeZero ? { include_zero: '1' } : {};
  const asOf = data?.as_of || data?.generated_at;
  const itemCount = summary.item_count ?? summary.line_count ?? items.length;
  const inventoryValue = summary.inventory_value ?? summary.cost_value ?? 0;
  const sellingValue = summary.selling_value ?? summary.retail_value ?? 0;

  return (
    <div className="space-y-6 print:space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <BrandMark className="h-14 w-14" name={storeName} />
          <div>
            <p className="text-lg font-semibold leading-tight">{storeName}</p>
            <p className="text-sm font-medium">Stock valuation</p>
            <p className="text-xs text-muted-foreground">{DEFAULT_STORE_TAGLINE}</p>
            {data?.contact ? (
              <p className="text-xs text-muted-foreground">{data.contact}</p>
            ) : null}
            {asOf ? (
              <p className="text-xs text-muted-foreground">
                As of {formatDateTime(asOf)}
              </p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 print:hidden">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeZero}
              onChange={(e) => setIncludeZero(e.target.checked)}
            />
            Show zero quantity
          </label>
          <ReportExportButtons slug="stock-valuation" params={exportParams} disabled={loading} />
        </div>
      </div>

      {loading ? (
        <PageLoading rows={8} showStats />
      ) : !data ? (
        <EmptyState
          icon={Package}
          title="Could not load stock"
          description="Try again, or check that inventory reports are enabled."
        />
      ) : (
        <>
          <div className={R.summaryGrid}>
            <div className={R.summaryCard}>
              <h3>SKUs in stock</h3>
              <p className={`${R.summaryValue} text-right`}>{formatNumber(itemCount)}</p>
            </div>
            <div className={R.summaryCard}>
              <h3>Qty on hand</h3>
              <p className={`${R.summaryValue} text-right`}>
                {formatNumber(summary.units_on_hand || 0)}
              </p>
            </div>
            {showCost ? (
              <div className={R.summaryCard}>
                <h3>Inventory value</h3>
                <p className={`${R.summaryValue} text-right`}>
                  {formatCurrency(inventoryValue)}
                </p>
              </div>
            ) : null}
            <div className={R.summaryCard}>
              <h3>Selling value</h3>
              <p className={`${R.summaryValue} text-right`}>{formatCurrency(sellingValue)}</p>
            </div>
          </div>

          {items.length === 0 ? (
            <EmptyState
              icon={Package}
              title="Nothing in stock"
              description="Turn on Show zero quantity to see empty SKUs, or record a purchase first."
            />
          ) : (
            <div className={R.section}>
              <h3>Stock on hand</h3>
              <div className={R.tableWrap}>
                <table className={R.table}>
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Item</th>
                      <th>Category</th>
                      <th>Size / colour</th>
                      <th className={HEAD_NUM}>Qty</th>
                      {showCost ? (
                        <>
                          <th className={HEAD_NUM}>Unit cost</th>
                          <th className={HEAD_NUM}>Inventory value</th>
                        </>
                      ) : null}
                      <th className={HEAD_NUM}>Selling price</th>
                      <th className={HEAD_NUM}>Selling value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => (
                      <tr key={`${row.sku}-${row.variant || 'base'}`}>
                        <td className="whitespace-nowrap">{row.sku}</td>
                        <td>{row.item || row.product}</td>
                        <td className="text-muted-foreground">{row.category || '—'}</td>
                        <td>{row.variant || '—'}</td>
                        <td className={NUM}>{formatNumber(row.quantity)}</td>
                        {showCost ? (
                          <>
                            <td className={NUM}>{formatCurrency(row.unit_cost)}</td>
                            <td className={NUM}>
                              {formatCurrency(row.inventory_value ?? row.cost_value)}
                            </td>
                          </>
                        ) : null}
                        <td className={NUM}>
                          {formatCurrency(row.selling_price ?? row.unit_price)}
                        </td>
                        <td className={NUM}>
                          {formatCurrency(row.selling_value ?? row.retail_value)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-muted/40 font-semibold">
                      <td colSpan={4}>Total</td>
                      <td className={NUM}>{formatNumber(summary.units_on_hand || 0)}</td>
                      {showCost ? (
                        <>
                          <td className={NUM} />
                          <td className={NUM}>{formatCurrency(inventoryValue)}</td>
                        </>
                      ) : null}
                      <td className={NUM} />
                      <td className={NUM}>{formatCurrency(sellingValue)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
