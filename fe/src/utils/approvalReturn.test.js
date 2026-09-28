import {
  isApprovalRejectionNote,
  isApprovalRejectionTask,
  parseApprovalRejectionNotice,
  rejectedSaleFixPath,
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
    expect(
      parseApprovalRejectionNotice(
        'Returned.\n---\nsource: pending_change\nid: 42\nsale_id: 99\nref: reject/sale/99'
      )
    ).toEqual({
      source: 'pending_change',
      id: 42,
      saleId: 99,
    });
    expect(parseApprovalRejectionNotice('no footer')).toBeNull();
    expect(parseApprovalRejectionNotice('')).toBeNull();
  });

  it('routes a returned sale to POS or Record past sale', () => {
    expect(rejectedSaleFixPath({ source: 'pending_change', id: 42, saleId: 99 })).toBe('/pos');
    expect(
      rejectedSaleFixPath(
        { source: 'pending_change', id: 7 },
        'Approval rejected: past sale entry'
      )
    ).toBe('/sales/record-past?resubmit=7');
    expect(rejectedSaleFixPath({ source: 'expense', id: 3 })).toBeNull();
  });

  it('describes returning a request to the maker', () => {
    expect(rejectionReturnedMessage('sale_complete')).toMatch(/must-tick Daily note/i);
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
