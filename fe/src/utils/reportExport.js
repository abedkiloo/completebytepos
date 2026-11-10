/**
 * Report PDF / Excel / CSV download helpers.
 * Mirrors backend reports.export — format=pdf|xlsx|csv on each report endpoint.
 */

import { buildPdfFilename, downloadAuthenticatedFile } from './pdfDownload';
import { toast } from './toast';

export const REPORT_EXPORT_PATHS = {
  sales: '/reports/sales/',
  purchase: '/reports/purchase/',
  inventory: '/reports/inventory/',
  invoice: '/reports/invoice/',
  supplier: '/reports/supplier/',
  customer: '/reports/customer/',
  products: '/reports/products/',
  expense: '/reports/expense/',
  income: '/reports/income/',
  tax: '/reports/tax/',
  'profit-loss': '/reports/profit_loss/',
  annual: '/reports/annual/',
  'sales-by-person': '/reports/sales_by_person/',
  'sales-overview': '/reports/sales_overview/',
  'top-products': '/reports/top_products/',
  'cash-and-payments': '/reports/cash_and_payments/',
  'inventory-health': '/reports/inventory_health/',
  'stock-valuation': '/reports/stock_valuation/',
  'customer-outstanding': '/reports/customer_outstanding/',
  'sales-history': '/sales/export/',
  'trading-profit': '/reports/trading_profit/',
  'trading-profit-cogs': '/reports/trading_profit/cogs/',
  'trading-profit-breakdown': '/reports/trading_profit/breakdown/',
};

export const EXPORT_FORMATS = [
  { id: 'pdf', label: 'PDF' },
  { id: 'xlsx', label: 'Excel' },
  { id: 'csv', label: 'CSV' },
];

export function reportExportPath(slug) {
  return REPORT_EXPORT_PATHS[slug] || null;
}

export function normalizeReportExportFormat(raw) {
  const text = String(raw || '').trim().toLowerCase();
  if (!text) return null;
  if (text === 'excel' || text === 'xls' || text === 'xlsx') return 'xlsx';
  if (text === 'pdf' || text === 'csv') return text;
  return null;
}

export function reportExportFilename(slug, format, when = new Date()) {
  const fmt = normalizeReportExportFormat(format) || 'pdf';
  const ext = fmt === 'xlsx' ? 'xlsx' : fmt;
  const stamp = when.toISOString().slice(0, 10);
  return buildPdfFilename(slug || 'report', stamp, ext);
}

const SALE_EXPORT_MONTHS = [
  'jan',
  'feb',
  'mar',
  'apr',
  'may',
  'jun',
  'jul',
  'aug',
  'sep',
  'oct',
  'nov',
  'dec',
];

/**
 * Turn YYYY-MM-DD into a short label like ``oct-9``.
 *
 * Args:
 *   isoDate: Date string from the sales history filters.
 *
 * Returns:
 *   Short date stem, or empty string when invalid.
 */
export function formatSaleExportDatePart(isoDate) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(isoDate || '').trim());
  if (!match) return '';
  const month = SALE_EXPORT_MONTHS[Number(match[2]) - 1];
  if (!month) return '';
  const day = String(Number(match[3]));
  if (!day || day === 'NaN') return '';
  return `${month}-${day}`;
}

/**
 * Sales history download name from selected dates.
 *
 * Examples:
 *   sale-oct-9-to-nov-20.xlsx
 *   sale-oct-9.xlsx
 *   sale.xlsx
 *
 * Args:
 *   params: Export query (expects optional ``date_from`` / ``date_to``).
 *   format: pdf | xlsx | csv (or excel alias).
 *
 * Returns:
 *   Filename string safe for ``<a download>``.
 */
export function salesExportFilename(params = {}, format = 'xlsx') {
  const fmt = normalizeReportExportFormat(format) || 'xlsx';
  const ext = fmt === 'xlsx' ? 'xlsx' : fmt;
  const from = formatSaleExportDatePart(params.date_from);
  const to = formatSaleExportDatePart(params.date_to);
  let stem = 'sale';
  if (from && to) {
    stem = from === to ? `sale-${from}` : `sale-${from}-to-${to}`;
  } else if (from) {
    stem = `sale-${from}`;
  } else if (to) {
    stem = `sale-to-${to}`;
  }
  return `${stem}.${ext}`;
}

export function salesHistoryExportParams(filters = {}) {
  return reportExportQuery({
    date_from: filters.date_from,
    date_to: filters.date_to,
    payment_method: filters.payment_method,
    search: filters.search,
    cashier_id: filters.cashier_id,
  });
}

export function reportExportQuery(params = {}, format) {
  const fmt = normalizeReportExportFormat(format);
  const query = { ...params };
  Object.keys(query).forEach((key) => {
    if (query[key] == null || query[key] === '') delete query[key];
  });
  if (fmt) query.format = fmt;
  return query;
}

export function reportExportRequestPath(slug, params = {}, format = 'pdf') {
  const path = reportExportPath(slug);
  if (!path) return null;
  const query = reportExportQuery(params, format);
  const qs = new URLSearchParams(query).toString();
  return qs ? `${path}?${qs}` : path;
}

export async function downloadReportExport(apiClient, { slug, params = {}, format = 'pdf' }) {
  const fmt = normalizeReportExportFormat(format);
  if (!fmt) {
    throw new Error('Choose PDF, Excel, or CSV.');
  }
  const path = reportExportRequestPath(slug, params, fmt);
  if (!path) {
    throw new Error('This report cannot be exported.');
  }
  const filename =
    slug === 'sales-history'
      ? salesExportFilename(params, fmt)
      : reportExportFilename(slug, fmt);
  await downloadAuthenticatedFile(apiClient, path, filename, {
    emptyMessage: `The ${fmt.toUpperCase()} file was empty`,
    onDownloaded: (response) => {
      if (slug !== 'sales-history') {
        return;
      }
      const truncated = response.headers?.['x-export-truncated'];
      if (truncated !== '1' && String(truncated || '').toLowerCase() !== 'true') {
        return;
      }
      const total = response.headers?.['x-export-total-count'];
      toast.warning(
        total
          ? `Export includes a subset of your sales (${total} match these filters). Download again with narrower dates if needed.`
          : 'Export includes a subset of your sales. Narrow filters to export everything.'
      );
    },
  });
  return filename;
}
