import {
  employeesShowSalary,
  employeesShowStatus,
  employeesEnableCreate,
} from './employeeDisplay';

describe('employeeDisplay', () => {
  test('salary defaults off', () => {
    expect(employeesShowSalary({})).toBe(false);
  });

  test('create defaults on', () => {
    expect(employeesEnableCreate({})).toBe(true);
  });

  test('status respects hide_entity_status_toggles', () => {
    expect(
      employeesShowStatus({ show_employee_status: true }, { hide_entity_status_toggles: true })
    ).toBe(false);
  });
});
