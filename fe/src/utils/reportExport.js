/**
 * Report PDF / Excel / CSV download helpers.
 * Mirrors backend reports.export — format=pdf|xlsx|csv on each report endpoint.
 */

import { buildPdfFilename, downloadAuthenticatedFile } from './pdfDownload';

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
  'customer-outstanding': '/reports/customer_outstanding/',
  'sales-history': '/sales/export/',
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

export function salesHistoryExportParams(filters = {}) {
  return reportExportQuery({
    date_from: filters.date_from,
    date_to: filters.date_to,
    payment_method: filters.payment_method,
    search: filters.search,
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
  const filename = reportExportFilename(slug, fmt);
  await downloadAuthenticatedFile(apiClient, path, filename, {
    emptyMessage: `The ${fmt.toUpperCase()} file was empty`,
  });
  return filename;
}
