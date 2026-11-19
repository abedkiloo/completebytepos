import {
  DECISION_STATUS_APPROVED,
  DECISION_STATUS_REJECTED,
  decisionStatusLabel,
  formatExpenseDecisionRow,
  formatMyDecisionRow,
  readExpenseNotes,
} from './approvalDecisions';

describe('approvalDecisions', () => {
  it('labels approved and rejected statuses', () => {
    expect(decisionStatusLabel(DECISION_STATUS_APPROVED)).toBe('Approved');
    expect(decisionStatusLabel(DECISION_STATUS_REJECTED)).toBe('Rejected');
  });

  it('formats an approved decision with requester reason and decided time', () => {
    const row = formatMyDecisionRow({
      id: 9,
      action_type: 'product_price',
      entity_type: 'products.Product',
      entity_repr: 'Zipper',
      status: 'approved',
      reason: 'New supplier list',
      rejection_reason: '',
      made_by_username: 'cashier1',
      checked_at: '2026-10-07T09:15:00Z',
    });

    expect(row.statusLabel).toBe('Approved');
    expect(row.title).toBe('Zipper');
    expect(row.requestedBy).toBe('cashier1');
    expect(row.decidedAt).toBe('2026-10-07T09:15:00Z');
    expect(row.commentLabel).toBe('Requester reason');
    expect(row.comment).toBe('New supplier list');
    expect(row.checkerComment).toBe('');
  });

  it('formats a rejected decision with checker comment', () => {
    const row = formatMyDecisionRow({
      id: 11,
      action_type: 'sale_refund',
      entity_type: 'sales.Sale',
      entity_repr: 'S-100',
      status: 'rejected',
      reason: 'Customer return',
      rejection_reason: 'Need receipt photo',
      made_by_username: 'cashier1',
      checked_at: '2026-10-07T10:00:00Z',
    });

    expect(row.statusLabel).toBe('Rejected');
    expect(row.commentLabel).toBe('Checker comment');
    expect(row.comment).toBe('Need receipt photo');
    expect(row.checkerComment).toBe('Need receipt photo');
    expect(row.requesterReason).toBe('Customer return');
  });

  it('formats approved expense decisions', () => {
    const row = formatExpenseDecisionRow({
      id: 3,
      status: 'approved',
      description: 'Office rent',
      expense_number: 'EXP-3',
      created_by_name: 'accountant',
      updated_at: '2026-10-06T12:00:00Z',
      notes: 'October invoice',
    });
    expect(row.statusLabel).toBe('Approved');
    expect(row.badge).toBe('Expense');
    expect(row.title).toBe('Office rent');
    expect(row.decidedAt).toBe('2026-10-06T12:00:00Z');
    expect(row.comment).toBe('October invoice');
  });

  it('formats a rejected expense as rejected, with the checker and the reason', () => {
    const row = formatExpenseDecisionRow({
      id: 8,
      status: 'rejected',
      description: 'From mpesa to bank =325',
      created_by_name: 'lawrence',
      notes: '[Maker-checker] Daily expenses\n[Rejected by admin] Redo this',
    });
    expect(row.status).toBe('rejected');
    expect(row.statusLabel).toBe('Rejected');
    expect(row.decidedBy).toBe('admin');
    expect(row.commentLabel).toBe('Checker comment');
    expect(row.comment).toBe('Redo this');
    expect(row.checkerComment).toBe('Redo this');
  });

  it('turns bracket notes into a clear rejection', () => {
    const note = readExpenseNotes({
      status: 'rejected',
      notes: '[Maker-checker] Daily expenses\n[Rejected by admin] Redo this',
    });
    expect(note.rejected).toBe(true);
    expect(note.checker).toBe('admin');
    expect(note.reason).toBe('Redo this');
    expect(note.submitted).toEqual(['Daily expenses']);
    expect(note.other).toEqual([]);
  });
});
