import {
  BarChart3,
  Boxes,
  Briefcase,
  Factory,
  NotebookPen,
  Package,
  ShoppingCart,
  Users,
} from 'lucide-react';

/** Card metadata for System Settings module toggle sections. */
export const MODULE_SETTINGS_CARDS = [
  {
    module: 'products',
    title: 'Products module',
    description:
      'Optional catalog display and workflow toggles. Variant sizes/colors and product images are configured under Module Settings → Products features.',
    icon: Package,
    toastLabel: 'Products',
  },
  {
    module: 'sales',
    title: 'Sales / checkout',
    description:
      'Controls retail POS and billing checkout behaviour. Receipt auto-print and payment methods are configured under store settings.',
    icon: ShoppingCart,
    toastLabel: 'Sales',
  },
  {
    module: 'inventory',
    title: 'Inventory / stock',
    description:
      'Controls stock movements, adjustments, purchases, transfers, and alerts. Install-level stock module features are configured under Module Settings.',
    icon: Boxes,
    toastLabel: 'Inventory',
  },
  {
    module: 'customers',
    title: 'Customers',
    description:
      'Optional display and workflow for the customer directory. Wallet usage at checkout is also controlled under Sales settings.',
    icon: Users,
    toastLabel: 'Customer',
  },
  {
    module: 'daily_notes',
    title: 'Daily notes',
    description:
      'Staff day journal — who can write notes and who can read everyone’s entries. Install the module under Module Settings.',
    icon: NotebookPen,
    toastLabel: 'Daily notes',
  },
  {
    module: 'employees',
    title: 'Employees',
    description:
      'Optional fields and actions for staff records. Install the Employees module under Module Settings to use the directory.',
    icon: Briefcase,
    toastLabel: 'Employee',
  },
  {
    module: 'suppliers',
    title: 'Suppliers',
    description:
      'Optional display and workflow for vendor records. Credit management also depends on the Suppliers module feature flags.',
    icon: Factory,
    toastLabel: 'Supplier',
  },
  {
    module: 'reports',
    title: 'Reports & analytics',
    description:
      'Control which reports appear in the hub and on the dashboard. Legacy module install flags still apply for module access.',
    icon: BarChart3,
    toastLabel: 'Report',
  },
  {
    module: 'users',
    title: 'Users & permissions',
    description:
      'Optional display and workflow for team accounts and custom roles. Install-level module flags still control access to the Users and Roles pages.',
    icon: Users,
    toastLabel: 'User',
  },
];
