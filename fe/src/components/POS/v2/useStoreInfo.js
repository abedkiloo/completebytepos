import { useMemo } from 'react';

/**
 * Resolve "store / branch / tenant" metadata for the receipt header.
 *
 * Precedence (so this works for both a fresh install and a logged-in user):
 *   1. fields the backend serialised onto the sale itself (branch + tenant)
 *   2. user.profile.branch / tenant in localStorage (set at login)
 *   3. last-resort defaults so the receipt never renders blank
 *
 * Returning a flat shape (storeName / branchName / address / phone / taxId)
 * keeps the receipt component dumb and printable.
 */
export function useStoreInfo(sale) {
  return useMemo(() => {
    const user = safeParseLocalStorage('user');
    const profile = user?.profile || {};
    const cachedBranch = safeParseLocalStorage('current_branch');

    const branch = sale?.branch || cachedBranch || profile.branch || {};
    const tenant = branch?.tenant || profile.tenant || {};

    const storeName = tenant.name || branch.name || 'CompleteByte POS';
    const branchName = branch.name && branch.name !== storeName ? branch.name : null;

    return {
      storeName,
      branchName,
      address:
        joinTruthy([branch.address, branch.city, branch.country], ', ') ||
        joinTruthy([tenant.address, tenant.city, tenant.country], ', '),
      phone: branch.phone || tenant.phone || '',
      email: branch.email || tenant.email || '',
      taxId: tenant.tax_id || tenant.kra_pin || '',
      receiptFooter: tenant.receipt_footer || 'Thank you for your business!',
    };
  }, [sale]);
}

function safeParseLocalStorage(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function joinTruthy(parts, sep) {
  return parts.filter(Boolean).join(sep);
}
