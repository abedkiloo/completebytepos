// @ts-check
const { test, expect } = require('@playwright/test');
const { login, gotoSystemSettings } = require('../helpers/auth');
const {
  clickModuleSetting,
  expectSettingsToast,
  isModuleSettingOn,
  openModuleSettingsCard,
} = require('../helpers/moduleSettings');

test.describe('POS checkout smoke', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('retail_pos_loads_product_grid_and_checkout', async ({ page }) => {
    await page.goto('/pos');
    await expect(page.getByText('POS').first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByPlaceholder(/search products|search/i)).toBeVisible({
      timeout: 10000,
    });
    await expect(
      page.getByRole('button', { name: /complete sale|pay|checkout/i }).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('pos_respects_sales_discount_module_toggle', async ({ page }) => {
    await gotoSystemSettings(page);
    const testId = 'setting-sales-show_discount';
    await openModuleSettingsCard(page, 'sales');
    await expect(page.getByTestId(testId)).toBeVisible({ timeout: 10000 });

    if (await isModuleSettingOn(page, testId)) {
      await clickModuleSetting(page, testId, { module: 'sales' });
      await expectSettingsToast(page, 'Sales');
    }

    await page.goto('/pos');
    await expect(page.getByRole('button', { name: /add discount/i })).toHaveCount(0);

    await gotoSystemSettings(page);
    if (!(await isModuleSettingOn(page, testId))) {
      await clickModuleSetting(page, testId, { module: 'sales' });
      await expectSettingsToast(page, 'Sales');
    }

    await page.goto('/pos');
    await expect(page.getByRole('button', { name: /add discount/i })).toBeVisible({
      timeout: 10000,
    });
  });
});
