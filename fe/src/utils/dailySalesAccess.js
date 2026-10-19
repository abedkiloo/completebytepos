/**
 * Access helpers for the Daily Sales page (sales of one chosen day).
 *
 * - Module Settings → Sales → Daily sales tracker must be on (no app rebuild).
 * - Super Admin always allowed when the feature is on.
 * - Everyone else needs the explicit checkable permission `sales.daily_sales`
 *   (managers and sales staff do not get it from sales.view alone).
 */
import { isModuleFeatureEnabled } from './moduleFeatures';
import { getStoredAuth, hasPermission } from './roleAccess';

function isSuperAdminFromAuth(user, profile) {
  return Boolean(
    user?.is_superuser ||
      profile?.role === 'super_admin' ||
      profile?.is_super_admin ||
      profile?.custom_role?.name === 'Super Admin'
  );
}

export function canViewDailySales(
  permissions,
  {
    isSuperAdmin = false,
    featureEnabled = true,
  } = {}
) {
  if (!featureEnabled) return false;
  if (isSuperAdmin) return true;
  return hasPermission(permissions, 'sales', 'daily_sales');
}

export function canViewDailySalesFromStorage() {
  const { permissions, user, profile } = getStoredAuth();
  return canViewDailySales(permissions, {
    isSuperAdmin: isSuperAdminFromAuth(user, profile),
    featureEnabled: isModuleFeatureEnabled('sales', 'daily_sales'),
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
