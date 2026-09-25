import React, { useCallback, useEffect, useState } from 'react';
import { Package } from 'lucide-react';

import { reportsAPI } from '../../services/api';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { reportsShowCostAndProfit } from '../../utils/reportDisplay';
import { resolveStoreName, DEFAULT_STORE_TAGLINE } from '../../utils/storeBranding';
import { formatCurrency, formatNumber } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { EmptyState, PageLoading } from '../page';
import { R } from './reportUI';
import ReportExportButtons from './ReportExportButtons';
import BrandMark from '../Shared/BrandMark';

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
  const lines = data?.lines || [];
  const exportParams = includeZero ? { include_zero: '1' } : {};

  return (
    <div className="space-y-6 print:space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <BrandMark className="h-14 w-14" name={storeName} />
          <div>
            <p className="text-lg font-semibold leading-tight">{storeName}</p>
            <p className="text-xs text-muted-foreground">{DEFAULT_STORE_TAGLINE}</p>
            {data?.contact ? (
              <p className="text-xs text-muted-foreground">{data.contact}</p>
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
            Include zero stock
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
              <h3>Lines on hand</h3>
              <p className={R.summaryValue}>{formatNumber(summary.line_count || 0)}</p>
            </div>
            <div className={R.summaryCard}>
              <h3>Units on hand</h3>
              <p className={R.summaryValue}>{formatNumber(summary.units_on_hand || 0)}</p>
            </div>
            {showCost ? (
              <div className={R.summaryCard}>
                <h3>Cost value</h3>
                <p className={R.summaryValue}>{formatCurrency(summary.cost_value || 0)}</p>
              </div>
            ) : null}
            <div className={R.summaryCard}>
              <h3>Retail value</h3>
              <p className={R.summaryValue}>{formatCurrency(summary.retail_value || 0)}</p>
            </div>
          </div>

          {data.note ? <p className="text-xs text-muted-foreground">{data.note}</p> : null}

          {lines.length === 0 ? (
            <EmptyState
              icon={Package}
              title="Nothing in stock"
              description="Turn on Include zero stock to see empty SKUs, or record a purchase first."
            />
          ) : (
            <div className={R.section}>
              <h3>Stock on hand</h3>
              <div className={R.tableWrap}>
                <table className={R.table}>
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Product</th>
                      <th>Variant</th>
                      <th>Qty</th>
                      {showCost ? (
                        <>
                          <th>Unit cost</th>
                          <th>Cost value</th>
                        </>
                      ) : null}
                      <th>Unit price</th>
                      <th>Retail value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((row) => (
                      <tr key={`${row.sku}-${row.variant || 'base'}`}>
                        <td>{row.sku}</td>
                        <td>{row.product}</td>
                        <td>{row.variant || '—'}</td>
                        <td>{formatNumber(row.quantity)}</td>
                        {showCost ? (
                          <>
                            <td>{formatCurrency(row.unit_cost)}</td>
                            <td>{formatCurrency(row.cost_value)}</td>
                          </>
                        ) : null}
                        <td>{formatCurrency(row.unit_price)}</td>
                        <td>{formatCurrency(row.retail_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
