/**
 * Pure helpers for expense category admin UI.
 */

export function canDeleteExpenseCategory(category, { isAdmin = false } = {}) {
  if (!isAdmin || !category) return false;
  return Number(category.expense_count || 0) === 0;
}
