/**
 * Helpers for the checker accountability trail ("My decisions").
 */

import { describeApprovalSummary } from './approvalDisplay';

export const DECISION_STATUS_APPROVED = 'approved';
export const DECISION_STATUS_REJECTED = 'rejected';

export function decisionStatusLabel(status) {
  if (status === DECISION_STATUS_APPROVED) return 'Approved';
  if (status === DECISION_STATUS_REJECTED) return 'Rejected';
  return status || 'Decided';
}

/**
 * Build a list row for a PendingChange the current user decided.
 */
export function formatMyDecisionRow(row) {
  const summary = describeApprovalSummary(row);
  const isRejected = row.status === DECISION_STATUS_REJECTED;
  const comment = isRejected
    ? (row.rejection_reason || '').trim()
    : (row.reason || '').trim();
  return {
    id: row.id,
    key: `decision-${row.id}`,
    status: row.status,
    statusLabel: decisionStatusLabel(row.status),
    badge: summary.action,
    title: summary.item,
    headline: summary.headline,
    requestedBy: row.made_by_username || 'a team member',
    decidedBy: row.checked_by_username || 'a checker',
    decidedAt: row.checked_at || null,
    requesterReason: (row.reason || '').trim(),
    checkerComment: isRejected ? (row.rejection_reason || '').trim() : '',
    comment,
    commentLabel: isRejected ? 'Checker comment' : 'Requester reason',
    data: row,
  };
}

export function formatExpenseDecisionRow(expense) {
  return {
    id: expense.id,
    key: `expense-decision-${expense.id}`,
    status: DECISION_STATUS_APPROVED,
    statusLabel: 'Approved',
    badge: 'Expense',
    title: expense.description || expense.expense_number || 'Expense',
    headline: expense.description || expense.expense_number || 'Expense',
    requestedBy: expense.created_by_name || 'a team member',
    decidedBy: expense.approved_by_name || expense.approved_by_username || 'a checker',
    decidedAt: expense.updated_at || expense.approved_at || expense.created_at || null,
    requesterReason: (expense.notes || expense.description || '').trim(),
    checkerComment: '',
    comment: (expense.notes || '').trim(),
    commentLabel: 'Notes',
    data: expense,
    kind: 'expense',
  };
}
