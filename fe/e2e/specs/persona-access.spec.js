// @ts-check
const { test, expect } = require('@playwright/test');
const {
  loginAs,
  dismissDevOverlay,
  salesUser,
  salesPass,
  managerUser,
  managerPass,
} = require('../helpers/auth');

/** Sidebar `<aside aria-label="Primary navigation">` — not a `navigation` landmark. */
function primarySidebar(page) {
  return page.getByRole('complementary', { name: 'Primary navigation' });
}

test.describe('Sales persona', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, salesUser, salesPass);
    await page.goto('/');
    await dismissDevOverlay(page);
  });

  test('shows sales nav without admin links', async ({ page }) => {
    const sidebar = primarySidebar(page);

    // Starter preset may enable Terminal POS only; Retail POS route can still work.
    await expect(
      sidebar
        .getByRole('link', { name: 'POS', exact: true })
        .or(sidebar.getByRole('link', { name: 'Terminal POS', exact: true }))
    ).toBeVisible();
    await expect(page.getByRole('link', { name: 'User Management' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'System Settings' })).toHaveCount(0);
    await expect(sidebar.getByRole('link', { name: 'Accounting', exact: true })).toHaveCount(0);

    await sidebar.getByRole('button', { name: 'Customers' }).click();
    await expect(sidebar.getByRole('link', { name: 'Customers', exact: true })).toBeVisible();
  });

  test('redirects from admin routes', async ({ page }) => {
    for (const path of ['/system-settings', '/users', '/reports', '/accounting']) {
      await page.goto(path);
      await page.waitForURL((url) => new URL(url).pathname === '/', { timeout: 15000 });
    }
  });

  test('can open POS and customers', async ({ page }) => {
    await page.goto('/pos');
    await dismissDevOverlay(page);
    await expect(page.getByPlaceholder(/search products|search/i)).toBeVisible({
      timeout: 15000,
    });

    await page.goto('/customers');
    await dismissDevOverlay(page);
    await expect(page.getByRole('heading', { name: /customers/i }).first()).toBeVisible({
      timeout: 15000,
    });
  });
});

test.describe('Manager persona', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, managerUser, managerPass);
    await page.goto('/');
    await dismissDevOverlay(page);
  });

  test('hides super-admin settings nav', async ({ page }) => {
    const sidebar = primarySidebar(page);

    await expect(page.getByRole('link', { name: 'User Management' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'System Settings' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Module Settings' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Branch Management' })).toHaveCount(0);

    await sidebar.getByRole('button', { name: 'Finance & Accounts' }).click();
    await expect(sidebar.getByRole('link', { name: 'Accounting', exact: true })).toBeVisible();
  });

  test('redirects from super-admin routes', async ({ page }) => {
    for (const path of ['/system-settings', '/users', '/module-settings', '/branches']) {
      await page.goto(path);
      await page.waitForURL((url) => new URL(url).pathname === '/', { timeout: 15000 });
    }
  });

  test('can open manager routes', async ({ page }) => {
    await page.goto('/products');
    await dismissDevOverlay(page);
    await expect(page.getByRole('heading', { name: /products/i }).first()).toBeVisible({
      timeout: 15000,
    });

    await page.goto('/accounting');
    await dismissDevOverlay(page);
    await expect(page.getByRole('heading', { name: /accounting/i }).first()).toBeVisible({
      timeout: 15000,
    });

    await page.goto('/reports');
    await dismissDevOverlay(page);
    await expect(page.getByRole('heading', { name: /reports/i }).first()).toBeVisible({
      timeout: 15000,
    });
  });
});
