import {
  collectionAmount,
  collectionMethod,
  DEBT_COLLECTION_ACTION,
  isSalesDeskQueueAction,
  otherPendingApprovalRows,
  pendingApprovalsBadgeCount,
  pendingApprovalsExcludeParams,
  pendingDebtCollectionParams,
  SALE_COMPLETE_ACTION,
  saleApprovalsBadgeCount,
  saleApprovalsEmpty,
  userCanApproveDebtCollections,
  userCanOpenSaleApprovals,
} from './saleApprovalsQueue';

describe('saleApprovalsQueue', () => {
  test('debt collection approve is independently grantable', () => {
    expect(userCanApproveDebtCollections([{ module: 'debt_management', action: 'approve' }])).toBe(
      true
    );
    expect(userCanApproveDebtCollections([{ module: 'sales', action: 'approve' }])).toBe(false);
    expect(userCanApproveDebtCollections([])).toBe(false);
    expect(userCanApproveDebtCollections()).toBe(false);
  });

  test('Approve sales opens with sales.approve or debt_management.approve', () => {
    expect(userCanOpenSaleApprovals([{ module: 'sales', action: 'approve' }])).toBe(true);
    expect(userCanOpenSaleApprovals([{ module: 'debt_management', action: 'approve' }])).toBe(true);
    expect(userCanOpenSaleApprovals([{ module: 'sales', action: 'view' }])).toBe(false);
    expect(userCanOpenSaleApprovals()).toBe(false);
  });

  test('pending debt collection list params', () => {
    expect(pendingDebtCollectionParams()).toEqual({
      action_type: DEBT_COLLECTION_ACTION,
    });
  });

  test('Pending Approvals badge/list share the same sales-desk exclude CSV', () => {
    expect(pendingApprovalsExcludeParams()).toEqual({
      exclude_action_type: `${SALE_COMPLETE_ACTION},${DEBT_COLLECTION_ACTION}`,
    });
    expect(pendingApprovalsBadgeCount()).toBe(0);
    expect(
      pendingApprovalsBadgeCount({ otherChangesCount: 0, expensesCount: 0 })
    ).toBe(0);
    expect(
      pendingApprovalsBadgeCount({ otherChangesCount: 1, expensesCount: 2 })
    ).toBe(3);
    // A lone sale_complete must not inflate the generic Pending Approvals badge.
    expect(
      pendingApprovalsBadgeCount({ otherChangesCount: 0, expensesCount: 0 })
    ).toBe(0);
  });

  test('sales-desk actions stay off the generic approvals list', () => {
    expect(isSalesDeskQueueAction('sale_complete')).toBe(true);
    expect(isSalesDeskQueueAction('debt_collection')).toBe(true);
    expect(isSalesDeskQueueAction('product_price')).toBe(false);
    expect(isSalesDeskQueueAction()).toBe(false);
    expect(
      otherPendingApprovalRows([
        { id: 1, action_type: 'debt_collection' },
        { id: 2, action_type: 'sale_complete' },
        { id: 3, action_type: 'product_price' },
      ])
    ).toEqual([{ id: 3, action_type: 'product_price' }]);
    expect(otherPendingApprovalRows(null)).toEqual([]);
    expect(otherPendingApprovalRows()).toEqual([]);
  });

  test('reads collection amount and method from payload', () => {
    expect(
      collectionAmount({ apply_payload: { amount: '40.00' }, proposed_values: { amount: '1' } })
    ).toBe('40.00');
    expect(collectionAmount({ proposed_values: { amount: '12.50' } })).toBe('12.50');
    expect(collectionAmount({})).toBe('');
    expect(collectionMethod({ apply_payload: { payment_method: 'mpesa' } })).toBe('mpesa');
    expect(collectionMethod({ proposed_values: { payment_method: 'bank' } })).toBe('bank');
    expect(collectionMethod({})).toBe('cash');
  });

  test('empty state and badge count combine sales and collections', () => {
    expect(saleApprovalsEmpty()).toBe(true);
    expect(saleApprovalsEmpty({ sales: null, collections: null })).toBe(true);
    expect(saleApprovalsEmpty({ sales: [{ id: 1 }], collections: [] })).toBe(false);
    expect(saleApprovalsEmpty({ sales: [], collections: [{ id: 2 }] })).toBe(false);
    expect(saleApprovalsEmpty({ sales: [{ id: 1 }], collections: [{ id: 2 }] })).toBe(false);
    expect(saleApprovalsBadgeCount()).toBe(0);
    expect(saleApprovalsBadgeCount({ salesCount: 2, collectionsCount: 3 })).toBe(5);
    expect(saleApprovalsBadgeCount({ salesCount: '1', collectionsCount: null })).toBe(1);
  });
});
