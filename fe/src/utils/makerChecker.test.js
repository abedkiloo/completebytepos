import {
  isMakerCheckerEnabled,
  isSalesMakerCheckerActive,
  completedSaleDirectEditBlocked,
  isPendingApprovalResponse,
  productEditNeedsReason,
  pendingApprovalLabels,
  extractPendingChange,
  priceChangeExceedsFiftyPercent,
  needsExtremePriceConfirm,
  variantEditNeedsReason,
  categoryEditNeedsReason,
  categoryDeactivateNeedsReason,
  storeSettingsEditNeedsReason,
  moduleSettingsPatchNeedsReason,
  rolePermissionsChanged,
  formatPendingApprovalHint,
  handleWriteResponse,
  PENDING_APPROVAL_MESSAGE,
  canApproveFinancialRecord,
  financialSubmitSuccessMessage,
  financialRecordNeedsReason,
  getCurrentUserId,
  userMayApproveModule,
} from './makerChecker';

describe('makerChecker', () => {
  it('detects maker-checker enabled from store settings', () => {
    expect(isMakerCheckerEnabled({ maker_checker_enabled: true })).toBe(true);
    expect(isMakerCheckerEnabled({ maker_checker_enabled: false })).toBe(false);
    expect(isMakerCheckerEnabled(null)).toBe(false);
    expect(isMakerCheckerEnabled({})).toBe(false);
    expect(
      isSalesMakerCheckerActive({
        maker_checker_enabled: true,
        maker_checker_sales_controls: true,
      })
    ).toBe(true);
    expect(
      completedSaleDirectEditBlocked({
        maker_checker_enabled: true,
        maker_checker_sales_controls: false,
      })
    ).toBe(true);
  });

  it('userMayApproveModule checks permissions list', () => {
    const perms = [{ name: 'income.approve', module: 'income', action: 'approve' }];
    expect(userMayApproveModule('income', perms)).toBe(true);
    expect(userMayApproveModule('expenses', perms)).toBe(false);
  });

  it('detects 202 pending responses', () => {
    expect(isPendingApprovalResponse(202)).toBe(true);
    expect(isPendingApprovalResponse(200)).toBe(false);
  });

  it('extracts pending_change from response body', () => {
    const body = { pending_change: { id: 3, action_type: 'product_price' } };
    expect(extractPendingChange(body)?.id).toBe(3);
    expect(extractPendingChange({ pending_changes: [{ id: 9 }] })?.id).toBe(9);
    expect(extractPendingChange(null)).toBeNull();
  });

  it('flags price edits as needing reason', () => {
    expect(
      productEditNeedsReason({ price: '150' }, { price: '100' })
    ).toBe(true);
    expect(
      productEditNeedsReason({ name: 'X' }, { name: 'Y', price: '100' })
    ).toBe(false);
    expect(
      productEditNeedsReason({ price: '10' }, null)
    ).toBe(true);
    expect(
      productEditNeedsReason({ is_active: false }, null)
    ).toBe(true);
    expect(
      productEditNeedsReason({ price: '0' }, null)
    ).toBe(false);
    expect(
      productEditNeedsReason({ price: '5' }, { price: '5' }, { financialFieldsLocked: true })
    ).toBe(false);
    expect(
      productEditNeedsReason({ is_active: true }, { is_active: true })
    ).toBe(false);
  });

  it('builds pending approval labels', () => {
    expect(
      pendingApprovalLabels({ pending_price: true, pending_stock: true })
    ).toEqual(['Price', 'Stock']);
    expect(pendingApprovalLabels(null)).toEqual([]);
  });

  it('detects extreme price changes over 50%', () => {
    const row = {
      action_type: 'product_price',
      original_values: { price: '100' },
      proposed_values: { price: '200' },
    };
    expect(priceChangeExceedsFiftyPercent(row)).toBe(true);
    expect(needsExtremePriceConfirm(row)).toBe(true);
    expect(priceChangeExceedsFiftyPercent(null)).toBe(false);
    expect(
      priceChangeExceedsFiftyPercent({
        action_type: 'product_price',
        original_values: { price: '0' },
        proposed_values: { price: '200' },
      })
    ).toBe(false);
    expect(
      priceChangeExceedsFiftyPercent({
        action_type: 'product_stock',
        original_values: { price: '100' },
        proposed_values: { price: '200' },
      })
    ).toBe(false);
  });

  it('flags store settings and module patch edits', () => {
    expect(
      storeSettingsEditNeedsReason(
        { enabled_payment_methods: ['cash'], receipt_footer_text: 'x' },
        { enabled_payment_methods: ['cash', 'card'], receipt_footer_text: 'x' }
      )
    ).toBe(true);
    expect(
      storeSettingsEditNeedsReason(
        { receipt_auto_print: true },
        { receipt_auto_print: false }
      )
    ).toBe(true);
    expect(
      storeSettingsEditNeedsReason(
        { receipt_footer_text: 'same' },
        { receipt_footer_text: 'same' }
      )
    ).toBe(false);
    expect(storeSettingsEditNeedsReason(null, {})).toBe(false);
    expect(
      moduleSettingsPatchNeedsReason({ show_status: false }, { show_status: true })
    ).toBe(true);
    expect(moduleSettingsPatchNeedsReason({}, {})).toBe(false);
    expect(rolePermissionsChanged([2, 1], { permissions: [{ id: 1 }] })).toBe(true);
    expect(rolePermissionsChanged([1], { permissions: [{ id: 1 }] })).toBe(false);
  });

  it('formats pending hints and handles write responses', () => {
    expect(formatPendingApprovalHint({ pending_price: true })).toContain('Price');
    expect(formatPendingApprovalHint({})).toBe(PENDING_APPROVAL_MESSAGE);
    const onPending = jest.fn();
    const onApplied = jest.fn();
    expect(
      handleWriteResponse({ status: 202, data: { pending_change: { id: 1 } } }, {
        onPending,
        onApplied,
      })
    ).toBe('pending');
    expect(onPending).toHaveBeenCalled();
    handleWriteResponse({ status: 200, data: {} }, { onPending, onApplied });
    expect(onApplied).toHaveBeenCalled();
  });

  it('flags variant and category sensitive edits', () => {
    expect(
      variantEditNeedsReason({ price: '120' }, { price: '100' })
    ).toBe(true);
    expect(
      variantEditNeedsReason({ is_active: false }, { is_active: true })
    ).toBe(true);
    expect(variantEditNeedsReason({}, { price: '1' })).toBe(false);
    expect(
      categoryEditNeedsReason({ is_active: false }, { is_active: true })
    ).toBe(true);
    expect(
      categoryEditNeedsReason({ name: 'X' }, { is_active: true, name: 'Y' })
    ).toBe(false);
    expect(categoryDeactivateNeedsReason({ is_active: true })).toBe(true);
    expect(categoryDeactivateNeedsReason({ is_active: false })).toBe(false);
    expect(categoryEditNeedsReason(null, { is_active: true })).toBe(false);
  });

  it('covers pending labels for delete and deactivation', () => {
    expect(
      pendingApprovalLabels({ pending_deactivation: true, pending_delete: true })
    ).toEqual(['Deactivation', 'Delete']);
  });

  it('requires module approve permission on financial records', () => {
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ name: 'expenses.create', module: 'expenses', action: 'create' }]),
    );
    const settings = { maker_checker_enabled: true };
    expect(canApproveFinancialRecord({ created_by: 5 }, settings, 6, 'expenses')).toBe(false);
  });

  it('blocks self-approval for financial records when maker-checker on', () => {
    localStorage.setItem('user', JSON.stringify({ id: 5 }));
    localStorage.setItem(
      'permissions',
      JSON.stringify([{ name: 'expenses.approve', module: 'expenses', action: 'approve' }]),
    );
    const settings = { maker_checker_enabled: true };
    expect(canApproveFinancialRecord({ created_by: 5 }, settings, 5, 'expenses')).toBe(false);
    expect(canApproveFinancialRecord({ created_by: 5 }, settings, 6, 'expenses')).toBe(true);
    expect(canApproveFinancialRecord({ created_by: 5 }, { maker_checker_enabled: false }, 5, 'expenses')).toBe(
      true
    );
    expect(getCurrentUserId()).toBe(5);
  });

  it('financialSubmitSuccessMessage only when MC enabled', () => {
    expect(financialSubmitSuccessMessage({ maker_checker_enabled: true })).toContain('checker');
    expect(financialSubmitSuccessMessage({ maker_checker_enabled: false })).toBeNull();
  });

  it('getCurrentUserId resolves profile.user and profile.user_id', () => {
    localStorage.clear();
    localStorage.setItem('profile', JSON.stringify({ user: 12 }));
    expect(getCurrentUserId()).toBe(12);
    localStorage.setItem('profile', JSON.stringify({ user_id: 13 }));
    expect(getCurrentUserId()).toBe(13);
    expect(financialRecordNeedsReason()).toBe(true);
  });

  it('getCurrentUserId returns null on invalid storage', () => {
    localStorage.setItem('user', 'not-json');
    expect(getCurrentUserId()).toBeNull();
  });
});
