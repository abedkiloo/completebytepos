// @ts-check
const { test, expect } = require('@playwright/test');
const { login, gotoSystemSettings } = require('../helpers/auth');
const {
  openModuleSettingsCard,
  isModuleSettingOn,
  clickModuleSetting,
  expectSettingsToast,
  ensureModuleSetting,
} = require('../helpers/moduleSettings');

test.describe('High-impact module settings', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await gotoSystemSettings(page);
    await openModuleSettingsCard(page, 'sales');
    await expect(page.getByTestId('setting-sales-validate_stock_before_sale')).toBeVisible();
  });

  test('sensitive_badge_visible_on_risky_sales_toggle', async ({ page }) => {
    const row = page
      .locator('div')
      .filter({ has: page.getByTestId('setting-sales-validate_stock_before_sale') });
    await expect(row.getByText(/^Sensitive$/i)).toBeVisible();
  });

  test('sensitive_toggle_cancel_keeps_previous_value', async ({ page }) => {
    const testId = 'setting-sales-validate_stock_before_sale';
    const wasOn = await isModuleSettingOn(page, testId);

    await clickModuleSetting(page, testId, { module: 'sales', action: 'cancel' });

    await expect(page.getByTestId(testId)).toHaveAttribute(
      'aria-checked',
      wasOn ? 'true' : 'false'
    );
    await expect(page.getByText(/settings updated/i)).toHaveCount(0);
  });

  test('sensitive_toggle_confirm_applies_and_can_restore', async ({ page }) => {
    const testId = 'setting-sales-show_discount';
    const start = await isModuleSettingOn(page, testId);

    await clickModuleSetting(page, testId, { module: 'sales' });
    await expectSettingsToast(page, 'Sales');
    await expect(page.getByTestId(testId)).toHaveAttribute(
      'aria-checked',
      start ? 'false' : 'true'
    );

    await clickModuleSetting(page, testId, { module: 'sales' });
    await expectSettingsToast(page, 'Sales');
    await expect(page.getByTestId(testId)).toHaveAttribute(
      'aria-checked',
      start ? 'true' : 'false'
    );
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
