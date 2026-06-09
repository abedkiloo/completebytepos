import { isModuleFlagEnabled } from './moduleSettingsCache';

export function reportsEnableDashboardSummary(settings) {
  return isModuleFlagEnabled(settings, 'enable_dashboard_summary', true);
}

export function reportsEnableSalesReports(settings) {
  return isModuleFlagEnabled(settings, 'enable_sales_reports', true);
}

export function reportsEnableProductReports(settings) {
  return isModuleFlagEnabled(settings, 'enable_product_reports', true);
}

export function reportsEnableInventoryReports(settings) {
  return isModuleFlagEnabled(settings, 'enable_inventory_reports', true);
}

export function reportsEnableFinancialReports(settings) {
  return isModuleFlagEnabled(settings, 'enable_financial_reports', true);
}

export function reportsEnableInvoiceReports(settings) {
  return isModuleFlagEnabled(settings, 'enable_invoice_reports', true);
}

export function reportsEnableSupplierReports(settings) {
  return isModuleFlagEnabled(settings, 'enable_supplier_reports', true);
}

export function reportsEnableCustomerReports(settings) {
  return isModuleFlagEnabled(settings, 'enable_customer_reports', true);
}

export function reportsEnableCashReports(settings) {
  return isModuleFlagEnabled(settings, 'enable_cash_reports', true);
}

export function reportsShowDiscount(settings) {
  return isModuleFlagEnabled(settings, 'show_discount_in_reports', true);
}

export function reportsShowTax(settings) {
  return isModuleFlagEnabled(settings, 'show_tax_in_reports', true);
}

export function reportsShowCostAndProfit(settings) {
  return isModuleFlagEnabled(settings, 'show_cost_and_profit', true);
}

/** Month revenue on the home dashboard (requires reports.view). */
export function userMayViewDashboardRevenue(permissions = []) {
  return permissions.some(
    (p) => p.module === 'reports' && p.action === 'view'
  );
}

/** Estimated profit on the home dashboard (reports.view + store toggle). */
export function userMayViewDashboardProfit(permissions = [], settings = {}) {
  return userMayViewDashboardRevenue(permissions) && reportsShowCostAndProfit(settings);
}

export function reportsShowLegacyCatalog(settings) {
  return isModuleFlagEnabled(settings, 'show_legacy_report_catalog', true);
}

/** Whether a legacy report id (?report=...) is enabled. */
export function reportsLegacyReportEnabled(settings, reportId) {
  switch (reportId) {
    case 'sales':
    case 'sales-by-person':
      return reportsEnableSalesReports(settings);
    case 'products':
      return reportsEnableProductReports(settings);
    case 'inventory':
    case 'purchase':
      return reportsEnableInventoryReports(settings);
    case 'invoice':
      return reportsEnableInvoiceReports(settings);
    case 'supplier':
      return reportsEnableSupplierReports(settings);
    case 'customer':
      return reportsEnableCustomerReports(settings);
    case 'expense':
    case 'income':
    case 'tax':
    case 'profit-loss':
    case 'annual':
      return reportsEnableFinancialReports(settings);
    default:
      return true;
  }
}
