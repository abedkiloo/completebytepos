import {
  Package,
  ShoppingCart,
  Users,
  FileText,
  BarChart3,
  TrendingDown,
  TrendingUp,
  Calculator,
  Factory,
  Barcode,
  Settings,
  Receipt,
  Wallet,
  Building2,
  Layers,
} from 'lucide-react';

/** Icons for module cards — domain grouping comes from the API catalog. */
export const MODULE_ICONS = {
  products: Package,
  sales: ShoppingCart,
  customers: Users,
  invoicing: FileText,
  inventory: Package,
  stock: BarChart3,
  expenses: TrendingDown,
  income: TrendingUp,
  bank_accounts: Building2,
  money_transfer: Wallet,
  accounting: Calculator,
  balance_sheet: FileText,
  trial_balance: Calculator,
  cash_flow: Wallet,
  account_statement: Receipt,
  suppliers: Factory,
  barcodes: Barcode,
  reports: BarChart3,
  settings: Settings,
  employees: Users,
};

export function getFeatureTip(moduleName, featureKey) {
  const tips = {
    sales: {
      pos: 'Walk-in retail checkout.',
      billing_pos: 'Invoices, credit, and held carts.',
    },
    settings: {
      multi_branch_support: 'Shows branch selector in the header when on.',
      module_settings: 'This page.',
    },
    products: {
      product_variants: 'Size/color variants at POS when enabled.',
    },
  };
  return tips[moduleName]?.[featureKey] || 'Controls visibility in menus and workflows.';
}
