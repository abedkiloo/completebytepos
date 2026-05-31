// @ts-check
const { test, expect } = require('@playwright/test');
const { login, gotoSystemSettings } = require('../helpers/auth');
const {
  expectSettingsToast,
  ensureModuleSetting,
} = require('../helpers/moduleSettings');

test.describe('Products module', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('products_selling_price_has_green_computed_color', async ({ page }) => {
    await page.goto('/products');
    await expect(page.getByRole('heading', { name: /^products$/i })).toBeVisible({
      timeout: 10000,
    });
    const row = page.locator('tbody tr').first();
    await expect(row).toBeVisible({ timeout: 10000 });
    const selling = row.locator('td.text-success').first();
    await expect(selling).toBeVisible();
    const color = await selling.evaluate((el) => getComputedStyle(el).color);
    expect(color).not.toBe('rgb(107, 114, 128)');
    const [r, g] = color.match(/\d+/g).map(Number);
    expect(g).toBeGreaterThan(r);
  });

  test('products_status_toggle_off_hides_status_column', async ({ page }) => {
    await gotoSystemSettings(page);
    const testId = 'setting-products-show_status';
    if (await ensureModuleSetting(page, testId, false)) {
      await expectSettingsToast(page, 'Products');
    }

    await page.goto('/products');
    await expect(page.getByRole('columnheader', { name: 'Status' })).toHaveCount(0);
    await page.getByRole('button', { name: /add product/i }).click();
    await expect(page.getByLabel('Active')).toHaveCount(0);

    await gotoSystemSettings(page);
    if (await ensureModuleSetting(page, testId, true)) {
      await expectSettingsToast(page, 'Products');
    }
  });

  test('products_status_toggle_on_restores_status_column', async ({ page }) => {
    await gotoSystemSettings(page);
    const testId = 'setting-products-show_status';
    if (await ensureModuleSetting(page, testId, true)) {
      await expectSettingsToast(page, 'Products');
    }

    await page.goto('/products');
    await expect(page.getByRole('columnheader', { name: 'Status' })).toBeVisible({
      timeout: 10000,
    });
  });
});
