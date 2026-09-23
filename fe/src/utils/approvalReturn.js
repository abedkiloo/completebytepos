/**
 * Parse Daily notes rejection notices and map resubmit API calls.
 */

export const REJECTION_TITLE_PREFIX = 'Approval rejected';

export function isApprovalRejectionTask(task) {
  return String(task?.title || '').startsWith(REJECTION_TITLE_PREFIX);
}

export function isApprovalRejectionNote(note) {
  return String(note?.title || '').startsWith(REJECTION_TITLE_PREFIX);
}

export function parseApprovalRejectionNotice(text) {
  const raw = String(text || '');
  const sourceMatch = raw.match(/^source:\s*(\S+)/m);
  const idMatch = raw.match(/^id:\s*(\d+)/m);
  const source = sourceMatch ? sourceMatch[1] : '';
  const id = idMatch ? parseInt(idMatch[1], 10) : NaN;
  if (!source || !Number.isFinite(id)) return null;
  return { source, id };
}

export function rejectionReturnedMessage(actionType) {
  if (actionType === 'sale_backfill') {
    return 'Returned to the requester. They can fix it on Record past sale, and will see a Daily notes task.';
  }
  return 'Returned to the requester. They will see a Daily notes task with your reason and can send it back for approval.';
}

export function resubmitSuccessMessage() {
  return 'Sent back for approval.';
}

const RESUBMIT_SOURCES = new Set([
  'pending_change',
  'expense',
  'income',
  'transfer',
]);

export function canResubmitRejection(parsed) {
  return Boolean(parsed && RESUBMIT_SOURCES.has(parsed.source) && parsed.id);
}
