import {
  filterRoleDailyTargets,
  isAppraisalAdminRole,
  roleHasPersonalTarget,
} from './appraisalRoles';

describe('appraisalRoles', () => {
  it('treats admin roles as having no personal target', () => {
    expect(isAppraisalAdminRole('Super Admin')).toBe(true);
    expect(isAppraisalAdminRole('admin')).toBe(true);
    expect(isAppraisalAdminRole('Administrator')).toBe(true);
    expect(isAppraisalAdminRole('Manager')).toBe(false);
    expect(roleHasPersonalTarget('Sales Personnel')).toBe(true);
    expect(roleHasPersonalTarget('Super Admin')).toBe(false);
  });

  it('drops admin rows from daily target maps', () => {
    expect(
      filterRoleDailyTargets({
        'Super Admin': 20000,
        Admin: 15000,
        Manager: 35000,
        'Sales Personnel': 20000,
      })
    ).toEqual({
      Manager: 35000,
      'Sales Personnel': 20000,
    });
  });
});
