// @ts-check
const { test, expect } = require('@playwright/test');
const { login, gotoSystemSettings } = require('../helpers/auth');
const {
  HIGH_IMPACT_CONFIRM,
  clickModuleSetting,
  expectSettingsToast,
  ensureModuleSetting,
} = require('../helpers/moduleSettings');

test.describe('High-impact module settings', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await gotoSystemSettings(page);
    await expect(page.getByRole('heading', { name: /sales \/ checkout/i })).toBeVisible();
  });

  test('high_impact_badge_visible_on_risky_sales_toggle', async ({ page }) => {
    const row = page.locator('label').filter({ hasText: /^Validate stock before sale/i });
    await expect(row.getByText(/High impact/i)).toBeVisible();
    await expect(page.getByTestId('setting-sales-validate_stock_before_sale')).toBeVisible();
  });

  test('high_impact_toggle_cancel_keeps_previous_value', async ({ page }) => {
    const testId = 'setting-sales-validate_stock_before_sale';
    const checkbox = page.getByTestId(testId);
    const wasChecked = await checkbox.isChecked();

    page.once('dialog', async (dialog) => {
      expect(dialog.message()).toMatch(HIGH_IMPACT_CONFIRM);
      await dialog.dismiss();
    });
    await checkbox.scrollIntoViewIfNeeded();
    await checkbox.click();

    await expect(checkbox).toBeChecked({ checked: wasChecked });
    await expect(page.getByText('Sales settings updated', { exact: true })).toHaveCount(0);
  });

  test('high_impact_toggle_confirm_applies_and_can_restore', async ({ page }) => {
    const testId = 'setting-sales-show_discount';
    const checkbox = page.getByTestId(testId);
    const start = await checkbox.isChecked();

    await clickModuleSetting(page, testId, { confirm: 'accept' });
    await expectSettingsToast(page, 'Sales');
    if (start) {
      await expect(checkbox).not.toBeChecked();
    } else {
      await expect(checkbox).toBeChecked();
    }

    await clickModuleSetting(page, testId, { confirm: 'accept' });
    await expectSettingsToast(page, 'Sales');
    if (start) {
      await expect(checkbox).toBeChecked();
    } else {
      await expect(checkbox).not.toBeChecked();
    }
  });

  test('disabling_sales_reports_hides_hub_tile', async ({ page }) => {
    const testId = 'setting-reports-enable_sales_reports';

    await ensureModuleSetting(page, testId, true);
    if (await ensureModuleSetting(page, testId, false)) {
      await expectSettingsToast(page, 'Report');
    }

    await page.goto('/reports');
    await expect(page.getByText('Sales overview')).toHaveCount(0);

    await gotoSystemSettings(page);
    if (await ensureModuleSetting(page, testId, true)) {
      await expectSettingsToast(page, 'Report');
    }
  });
});
