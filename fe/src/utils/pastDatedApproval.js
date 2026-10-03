/**
 * Managers approve today's items; anything dated before today is admin-only.
 * Mirrors be/approvals/permissions.py (user_may_approve_past_items / is_past_dated).
 */
import { getStoredAuth } from './roleAccess';

export const PAST_DATED_ADMIN_ONLY_MESSAGE =
  'This item is dated before today. Only an admin can approve or return past-dated items.';

const PAST_APPROVER_ROLE_NAMES = ['Super Admin', 'Admin', 'Administrator'];

export function userMayApprovePastItems(auth = getStoredAuth()) {
  const { user, profile } = auth || {};
  if (user?.is_superuser) return true;
  if (profile?.is_super_admin) return true;
  const legacy = String(profile?.role || '');
  if (legacy === 'admin' || legacy === 'super_admin') return true;
  const roleName = String(profile?.custom_role?.name || '').trim();
  return PAST_APPROVER_ROLE_NAMES.includes(roleName);
}

function pad(n) {
  return String(n).padStart(2, '0');
}

function localDayKey(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** 'YYYY-MM-DD' for a date-only string, ISO datetime, or Date (local calendar day). */
export function businessDayKey(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return localDayKey(date);
}

export function earliestBusinessDay(...values) {
  const keys = values.map(businessDayKey).filter(Boolean).sort();
  return keys[0] || null;
}

export function isPastDated(...values) {
  const day = earliestBusinessDay(...values);
  return Boolean(day && day < localDayKey(new Date()));
}

/** True when this user must leave the item for an admin. */
export function pastDatedBlocksUser(dates, auth = getStoredAuth()) {
  return isPastDated(...(dates || [])) && !userMayApprovePastItems(auth);
}

/** Dates that place a queued pending change on a business day. */
export function pendingChangeDates(change) {
  return [change?.business_date, change?.made_at];
}
