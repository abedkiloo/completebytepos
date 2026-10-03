/**
 * Access helpers for the Daily Sales page (sales of one chosen day).
 * Anyone with `sales.view` opens it and sees their own sales; admins and
 * `sales.view_all` see the whole store. `sales.daily_sales` still grants access.
 */
import { getStoredAuth, hasPermission } from './roleAccess';

function isSuperAdminFromAuth() {
  const { user, profile } = getStoredAuth();
  return Boolean(
    user?.is_superuser ||
      profile?.role === 'super_admin' ||
      profile?.is_super_admin ||
      profile?.custom_role?.name === 'Super Admin'
  );
}

export function canViewDailySales(permissions, { isSuperAdmin = false } = {}) {
  if (isSuperAdmin) return true;
  return (
    hasPermission(permissions, 'sales', 'view') ||
    hasPermission(permissions, 'sales', 'daily_sales')
  );
}

export function canViewDailySalesFromStorage() {
  const { permissions } = getStoredAuth();
  return canViewDailySales(permissions, {
    isSuperAdmin: isSuperAdminFromAuth(),
  });
}

export function dailySalesCustomerPath(customerId, date) {
  const id = encodeURIComponent(String(customerId));
  const base = `/sales/daily/customers/${id}`;
  if (!date) return base;
  return `${base}?date=${encodeURIComponent(date)}`;
}

export function dailySalesListPath(date) {
  if (!date) return '/sales/daily';
  return `/sales/daily?date=${encodeURIComponent(date)}`;
}

export function dayStandingLabel(standing) {
  switch (standing) {
    case 'good':
      return 'Good standing';
    case 'mixed':
      return 'Mixed — some debt';
    case 'debt':
      return 'Taken on debt';
    default:
      return 'Unknown';
  }
}
