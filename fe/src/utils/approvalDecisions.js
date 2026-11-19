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

/**
 * Read stored expense notes as plain sentences.
 *
 * `[Maker-checker]` and `[Rejected by name]` are labels, not text for staff
 * to read. At most 20 lines are kept. Each line is at most 500 characters.
 *
 * @param {object} expense Expense with `status` and `notes`. Notes may be blank.
 * @returns {{rejected: boolean, checker: string, reason: string, submitted: string[], other: string[]}}
 */
export function readExpenseNotes(expense) {
  const lines = String(expense?.notes || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 20);
  let checker = '';
  let reason = '';
  const submitted = [];
  const other = [];
  lines.forEach((line) => {
    const rejected = line.match(/^\[Rejected by ([^\]]+)\]\s*(.*)$/i);
    if (rejected) {
      checker = checker || rejected[1].trim().slice(0, 150);
      if (rejected[2].trim()) reason = rejected[2].trim().slice(0, 500);
      return;
    }
    const maker = line.match(/^\[Maker-checker\]\s*(.*)$/i);
    if (maker) {
      if (maker[1].trim()) submitted.push(maker[1].trim().slice(0, 500));
      return;
    }
    other.push(line.slice(0, 500));
  });
  const status = String(expense?.status || '').toLowerCase();
  return {
    rejected: status === 'rejected' || Boolean(checker),
    checker,
    reason,
    submitted,
    other,
  };
}

/**
 * Name of the checker who sent an expense back, from its notes.
 *
 * @param {string} notes Expense notes, 0–2000 characters.
 * @returns {string} Username inside `[Rejected by …]`, or an empty string.
 */
function rejectedByFromNotes(notes) {
  const match = String(notes || '').match(/\[Rejected by ([^\]]+)\]/);
  return match ? match[1].trim().slice(0, 150) : '';
}

/**
 * The reason written after `[Rejected by …]`.
 *
 * @param {string} notes Expense notes, 0–2000 characters.
 * @returns {string} Reason, at most 500 characters, or empty.
 */
function rejectionReasonFromNotes(notes) {
  const match = String(notes || '').match(/\[Rejected by [^\]]+\]\s*([^\n]*)/);
  return match ? match[1].trim().slice(0, 500) : '';
}

/**
 * One expense row on the decisions trail.
 *
 * A rejected expense is labeled Rejected. Approved and paid expenses stay
 * Approved. The checker name comes from the rejection note when the expense
 * was sent back.
 *
 * @param {object} expense Expense list row. `status` is pending, approved,
 *   rejected, paid, or voided.
 * @returns {object} Trail row. No writes.
 */
export function formatExpenseDecisionRow(expense) {
  const notes = (expense.notes || '').trim();
  const rejected = String(expense.status || '').toLowerCase() === DECISION_STATUS_REJECTED;
  const reason = rejected ? rejectionReasonFromNotes(notes) : '';
  const decidedBy = rejected
    ? (rejectedByFromNotes(notes) || 'a checker')
    : (expense.approved_by_name || expense.approved_by_username || 'a checker');
  return {
    id: expense.id,
    key: `expense-decision-${expense.id}`,
    status: rejected ? DECISION_STATUS_REJECTED : DECISION_STATUS_APPROVED,
    statusLabel: rejected ? 'Rejected' : 'Approved',
    badge: 'Expense',
    title: expense.description || expense.expense_number || 'Expense',
    headline: expense.description || expense.expense_number || 'Expense',
    requestedBy: expense.created_by_name || 'a team member',
    decidedBy,
    decidedAt: expense.updated_at || expense.approved_at || expense.created_at || null,
    requesterReason: notes,
    checkerComment: reason,
    comment: reason || notes,
    commentLabel: rejected ? 'Checker comment' : 'Notes',
    data: expense,
    kind: 'expense',
  };
}
