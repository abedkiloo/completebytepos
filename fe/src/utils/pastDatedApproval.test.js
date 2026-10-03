import {
  businessDayKey,
  earliestBusinessDay,
  isPastDated,
  pastDatedBlocksUser,
  userMayApprovePastItems,
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
});
