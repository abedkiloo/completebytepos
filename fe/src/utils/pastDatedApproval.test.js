import {
  businessDayKey,
  earliestBusinessDay,
  isPastDated,
  isPostedSaleCorrection,
  isSaleCancellationAction,
  pastDatedBlocksUser,
  postedCorrectionBlocksUser,
  userMayApprovePastItems,
  userMayApproveSaleCancellation,
} from './pastDatedApproval';

function dayOffset(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d;
}

const manager = { user: {}, profile: { role: 'manager', custom_role: { name: 'Manager' } } };
const admin = { user: {}, profile: { role: 'super_admin', custom_role: { name: 'Super Admin' } } };

describe('pastDatedApproval', () => {
  it('only admins may approve past items', () => {
    expect(userMayApprovePastItems(admin)).toBe(true);
    expect(userMayApprovePastItems({ user: { is_superuser: true }, profile: {} })).toBe(true);
    expect(userMayApprovePastItems(manager)).toBe(false);
  });

  it('only admins may approve sale voids and rollbacks', () => {
    expect(isSaleCancellationAction('sale_refund')).toBe(true);
    expect(isSaleCancellationAction('sale_rollback')).toBe(true);
    expect(isSaleCancellationAction('product_price')).toBe(false);
    expect(userMayApproveSaleCancellation(admin)).toBe(true);
    expect(userMayApproveSaleCancellation(manager)).toBe(false);
    expect(
      userMayApproveSaleCancellation({
        user: {},
        profile: { role: 'manager', custom_role: { name: 'Admin' } },
      })
    ).toBe(false);
  });

  it('keeps date-only strings as the business day', () => {
    expect(businessDayKey('2026-09-12')).toBe('2026-09-12');
    expect(businessDayKey('')).toBeNull();
    expect(earliestBusinessDay('2026-09-12', '2026-09-10', null)).toBe('2026-09-10');
  });

  it('flags anything before today as past-dated', () => {
    expect(isPastDated(dayOffset(0))).toBe(false);
    expect(isPastDated(dayOffset(0), dayOffset(-1))).toBe(true);
    expect(isPastDated(null)).toBe(false);
  });

  it('blocks managers on past items but not admins', () => {
    const yesterday = [dayOffset(-1).toISOString()];
    expect(pastDatedBlocksUser(yesterday, manager)).toBe(true);
    expect(pastDatedBlocksUser(yesterday, admin)).toBe(false);
    expect(pastDatedBlocksUser([dayOffset(0).toISOString()], manager)).toBe(false);
  });

  it('blocks managers from approving posted sale corrections', () => {
    const posted = {
      action_type: 'sale_complete',
      posted_correction: true,
      original_values: { returned_from_status: 'completed' },
    };
    const firstTime = {
      action_type: 'sale_complete',
      posted_correction: false,
      original_values: { returned_from_status: 'pending_approval' },
    };
    expect(isPostedSaleCorrection(posted)).toBe(true);
    expect(isPostedSaleCorrection(firstTime)).toBe(false);
    expect(postedCorrectionBlocksUser(posted, manager)).toBe(true);
    expect(postedCorrectionBlocksUser(posted, admin)).toBe(false);
    expect(postedCorrectionBlocksUser(firstTime, manager)).toBe(false);
  });
});
