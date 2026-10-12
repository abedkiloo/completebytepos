/**
 * Access helpers for the Daily Sales page (sales of one chosen day).
 *
 * - Module Settings → Sales → Daily sales tracker must be on (no app rebuild).
 * - Super Admin always allowed when the feature is on.
 * - Explicit `sales.daily_sales` grants access (including managers).
 * - Managers do **not** get the screen from `sales.view` alone.
 * - Cashiers / sales staff open their own day with `sales.view`.
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

function isStoreManagerProfile(profile) {
  if (!profile) return false;
  if (profile.is_super_admin || profile.is_admin) return false;
  if (profile.role === 'manager') return true;
  const name = (profile.custom_role?.name || profile.role_display || '').trim();
  return name === 'Manager';
}

export function canViewDailySales(
  permissions,
  {
    isSuperAdmin = false,
    profile = null,
    featureEnabled = true,
  } = {}
) {
  if (!featureEnabled) return false;
  if (isSuperAdmin) return true;
  if (hasPermission(permissions, 'sales', 'daily_sales')) return true;
  if (isStoreManagerProfile(profile)) return false;
  return hasPermission(permissions, 'sales', 'view');
}

export function canViewDailySalesFromStorage() {
  const { permissions, user, profile } = getStoredAuth();
  return canViewDailySales(permissions, {
    isSuperAdmin: isSuperAdminFromAuth(user, profile),
    profile,
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
