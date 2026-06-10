// @ts-check
const { test, expect } = require('@playwright/test');
const { login, gotoSystemSettings } = require('../helpers/auth');
const {
  clickModuleSetting,
  expectSettingsToast,
  ensureModuleSetting,
} = require('../helpers/moduleSettings');

test.describe('Module settings immediate UI', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('reports_sales_tile_hides_when_sales_reports_disabled', async ({ page }) => {
    await gotoSystemSettings(page);
    const testId = 'setting-reports-enable_sales_reports';

    await ensureModuleSetting(page, testId, true);
    await clickModuleSetting(page, testId, { module: 'reports' });
    await expectSettingsToast(page, 'Report');

    await page.goto('/reports');
    await expect(page.getByText('Sales overview')).toHaveCount(0);

    await gotoSystemSettings(page);
    if (await ensureModuleSetting(page, testId, true)) {
      await expectSettingsToast(page, 'Report');
    }

    await page.goto('/reports');
    await expect(page.getByText('Sales overview')).toBeVisible({ timeout: 10000 });
  });
});
