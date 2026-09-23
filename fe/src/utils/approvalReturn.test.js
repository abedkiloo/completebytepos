import {
  isApprovalRejectionNote,
  isApprovalRejectionTask,
  parseApprovalRejectionNotice,
  rejectionReturnedMessage,
  resubmitSuccessMessage,
} from './approvalReturn';

describe('approvalReturn', () => {
  it('detects rejection titles', () => {
    expect(isApprovalRejectionTask({ title: 'Approval rejected: sale rollback' })).toBe(true);
    expect(isApprovalRejectionNote({ title: 'Approval rejected: expense' })).toBe(true);
    expect(isApprovalRejectionNote({ title: 'Shift handover' })).toBe(false);
    expect(isApprovalRejectionTask({})).toBe(false);
  });

  it('parses source and id from notice footer', () => {
    const text = 'Bea returned your request.\n---\nsource: pending_change\nid: 42';
    expect(parseApprovalRejectionNotice(text)).toEqual({
      source: 'pending_change',
      id: 42,
    });
    expect(parseApprovalRejectionNotice('no footer')).toBeNull();
    expect(parseApprovalRejectionNotice('')).toBeNull();
  });

  it('describes returning a request to the maker', () => {
    expect(rejectionReturnedMessage('sale_backfill')).toMatch(/Record past sale/i);
    expect(rejectionReturnedMessage('product_price')).toMatch(/Daily notes/i);
    expect(resubmitSuccessMessage()).toMatch(/Sent back/i);
    expect(resubmitSuccessMessage('expense')).toMatch(/Sent back/i);
  });

  it('canResubmitRejection allows known sources', () => {
    const { canResubmitRejection } = require('./approvalReturn');
    expect(canResubmitRejection({ source: 'pending_change', id: 1 })).toBe(true);
    expect(canResubmitRejection({ source: 'expense', id: 2 })).toBe(true);
    expect(canResubmitRejection({ source: 'unknown', id: 1 })).toBe(false);
    expect(canResubmitRejection(null)).toBe(false);
  });
});
