// @ts-check

const adminUser = process.env.PLAYWRIGHT_ADMIN_USER || 'admin';
const adminPass = process.env.PLAYWRIGHT_ADMIN_PASSWORD || 'admin123';
const managerUser = process.env.PLAYWRIGHT_MANAGER_USER || 'manager';
const managerPass = process.env.PLAYWRIGHT_MANAGER_PASSWORD || 'manager123';
const salesUser = process.env.PLAYWRIGHT_SALES_USER || 'sales';
const salesPass = process.env.PLAYWRIGHT_SALES_PASSWORD || 'sales123';

/** Remove webpack error overlay if present (dev server). */
async function dismissDevOverlay(page) {
  await page.evaluate(() => {
    const overlay = document.getElementById('webpack-dev-server-client-overlay');
    if (overlay) overlay.remove();
  });
}

/** Sign in and wait for post-login redirect. */
async function loginAs(page, username, password) {
  await page.goto('/login');
  await dismissDevOverlay(page);
  await page.getByLabel(/username/i).fill(username);
  await page.locator('#password').fill(password);
  await page.locator('form').evaluate((form) => form.requestSubmit());
  await page.waitForURL(
    (url) => {
      const path = new URL(url).pathname;
      return path === '/' || /^\/(dashboard|pos|products)/.test(path);
    },
    { timeout: 20000 }
  );
}

/** Sign in as super admin and wait for post-login redirect. */
async function login(page) {
  await loginAs(page, adminUser, adminPass);
}

/** Navigate to system settings and wait for module cards. */
async function gotoSystemSettings(page) {
  await page.goto('/system-settings');
  await dismissDevOverlay(page);
  await page.getByRole('heading', { name: /system settings/i }).waitFor({
    state: 'visible',
    timeout: 15000,
  });
}

module.exports = {
  login,
  loginAs,
  gotoSystemSettings,
  dismissDevOverlay,
  adminUser,
  adminPass,
  managerUser,
  managerPass,
  salesUser,
  salesPass,
};
