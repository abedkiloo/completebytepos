import { canDeleteExpenseCategory } from './expenseCategories';

describe('canDeleteExpenseCategory', () => {
  it('allows admin to delete unused categories only', () => {
    expect(
      canDeleteExpenseCategory({ id: 1, expense_count: 0 }, { isAdmin: true })
    ).toBe(true);
    expect(
      canDeleteExpenseCategory({ id: 2, expense_count: 3 }, { isAdmin: true })
    ).toBe(false);
  });

  it('never allows non-admin delete', () => {
    expect(
      canDeleteExpenseCategory({ id: 1, expense_count: 0 }, { isAdmin: false })
    ).toBe(false);
  });
});
