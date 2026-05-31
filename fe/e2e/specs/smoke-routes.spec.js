// @ts-check
const { test, expect } = require('@playwright/test');
const { login, dismissDevOverlay } = require('../helpers/auth');
const { SMOKE_ROUTES } = require('../helpers/routes');

test.describe('App route smoke (super admin)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  for (const route of SMOKE_ROUTES) {
    test(`loads_${route.path.replace(/\//g, '_') || 'dashboard'}`, async ({ page }) => {
      await page.goto(route.path);
      await dismissDevOverlay(page);

      if (route.text) {
        await expect(page.getByText(route.text).first()).toBeVisible({ timeout: 15000 });
      } else {
        await expect(page.getByRole('heading', { name: route.heading }).first()).toBeVisible({
          timeout: 15000,
        });
      }

      await expect(page.getByText(/something went wrong|404|not found/i)).toHaveCount(0);
    });
  }
});
