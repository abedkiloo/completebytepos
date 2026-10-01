import {
  SALE_APPROVED_RECEIPT_MESSAGE,
  SALE_AWAITING_APPROVAL_MESSAGE,
  SALE_AWAITING_PAYMENT_MESSAGE,
  awaitingApprovalListParams,
  partitionSaleApprovalQueue,
  saleCanAdminReturnForCorrection,
  saleCheckoutSuccessToast,
  saleIsAwaitingApproval,
  saleIsAwaitingPayment,
  saleNeedsSalespersonAction,
  saleReceiptBlockedReason,
  saleRejectionReason,
  userCanApproveSales,
  userHasAdminSaleOverride,
} from './saleCompletionApproval';

describe('saleCompletionApproval', () => {
  test('detects pending_approval sales', () => {
    expect(saleIsAwaitingApproval({ status: 'pending_approval' })).toBe(true);
    expect(saleIsAwaitingApproval({ status: 'completed' })).toBe(false);
    expect(saleIsAwaitingApproval(null)).toBe(false);
    expect(saleIsAwaitingPayment({ status: 'awaiting_payment' })).toBe(true);
    expect(saleIsAwaitingPayment({ status: 'pending_approval' })).toBe(false);
  });

  test('rejected holdings need salesperson action', () => {
    expect(saleNeedsSalespersonAction({ needs_salesperson_action: true })).toBe(true);
    expect(saleNeedsSalespersonAction({ status: 'holding' })).toBe(false);
    expect(saleRejectionReason({ rejection_reason: ' Wrong prices ' })).toBe('Wrong prices');
    expect(
      partitionSaleApprovalQueue([
        { id: 1, status: 'pending_approval' },
        { id: 2, status: 'holding', needs_salesperson_action: true },
      ])
    ).toEqual({
      waiting: [{ id: 1, status: 'pending_approval' }],
      returned: [{ id: 2, status: 'holding', needs_salesperson_action: true }],
    });
  });

  test('blocks receipt until completed', () => {
    expect(saleReceiptBlockedReason({ status: 'pending_approval' })).toBe(
      SALE_AWAITING_APPROVAL_MESSAGE
    );
    expect(saleReceiptBlockedReason({ status: 'holding' })).toMatch(/after the sale is completed/i);
    expect(saleReceiptBlockedReason({ status: 'awaiting_payment' })).toBe(
      SALE_AWAITING_PAYMENT_MESSAGE
    );
    expect(saleReceiptBlockedReason({ status: 'completed' })).toBeNull();
    expect(saleReceiptBlockedReason(null)).toBeNull();
  });

  test('checkout toast prefers waiting copy', () => {
    expect(
      saleCheckoutSuccessToast({ status: 'pending_approval', message: 'Wait please' })
    ).toBe('Wait please');
    expect(saleCheckoutSuccessToast({ pending_change: { id: 1 } })).toBe(
      SALE_AWAITING_APPROVAL_MESSAGE
    );
    expect(saleCheckoutSuccessToast({ status: 'completed' })).toBe('Sale completed');
    expect(
      saleCheckoutSuccessToast({ status: 'completed' }, { completedMessage: 'Done' })
    ).toBe('Done');
    expect(saleCheckoutSuccessToast({ status: 'completed' })).toBe('Sale completed');
  });

  test('approve permission is sales.approve', () => {
    expect(userCanApproveSales([{ module: 'sales', action: 'approve' }])).toBe(true);
    expect(userCanApproveSales([{ module: 'sales', action: 'create' }])).toBe(false);
    expect(userCanApproveSales([])).toBe(false);
    expect(userCanApproveSales()).toBe(false);
  });

  test('awaiting list params set status', () => {
    expect(awaitingApprovalListParams({ search: 'S-1' })).toEqual({
      search: 'S-1',
      status: 'pending_approval',
    });
    expect(awaitingApprovalListParams()).toEqual({ status: 'pending_approval' });
  });

  test('approved copy is stable', () => {
    expect(SALE_APPROVED_RECEIPT_MESSAGE).toMatch(/print the receipt/i);
  });

  test('admin override can return approved and unrefunded completed sales', () => {
    expect(
      userHasAdminSaleOverride({
        user: { is_superuser: true },
        profile: { role: 'cashier' },
      })
    ).toBe(true);
    expect(
      userHasAdminSaleOverride({
        user: {},
        profile: { role: 'admin' },
      })
    ).toBe(true);
    expect(
      userHasAdminSaleOverride({
        user: {},
        profile: { role: 'manager' },
      })
    ).toBe(false);
    expect(saleCanAdminReturnForCorrection({ status: 'awaiting_payment' })).toBe(true);
    expect(
      saleCanAdminReturnForCorrection({ status: 'completed', refund_status: 'none' })
    ).toBe(true);
    expect(
      saleCanAdminReturnForCorrection({ status: 'completed', refund_status: 'partial' })
    ).toBe(false);
    expect(saleCanAdminReturnForCorrection({ status: 'pending_approval' })).toBe(false);
  });
});
