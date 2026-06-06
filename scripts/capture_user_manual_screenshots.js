#!/usr/bin/env node
/**
 * Capture UI screenshots for the user manual Excel workbook.
 *
 * Prerequisites:
 *   docker compose -f docker-compose.dev.yml up -d
 *   cd fe && npm run test:e2e:install   # once — installs Playwright chromium
 *
 * Usage:
 *   node scripts/capture_user_manual_screenshots.js
 *   PLAYWRIGHT_BASE_URL=http://192.168.1.10:3000 node scripts/capture_user_manual_screenshots.js
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'docs', 'user-manual', 'screenshots');
const BASE = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';

const managerUser = process.env.PLAYWRIGHT_MANAGER_USER || 'manager';
const managerPass = process.env.PLAYWRIGHT_MANAGER_PASSWORD || 'manager123';
const adminUser = process.env.PLAYWRIGHT_ADMIN_USER || 'admin';
const adminPass = process.env.PLAYWRIGHT_ADMIN_PASSWORD || 'admin123';

async function dismissOverlay(page) {
  await page.evaluate(() => {
    const el = document.getElementById('webpack-dev-server-client-overlay');
    if (el) el.remove();
  });
}

async function login(page, username, password) {
  await page.goto(`${BASE}/login`);
  await dismissOverlay(page);
  await page.getByLabel(/username/i).fill(username);
  await page.locator('#password').fill(password);
  await page.locator('form').evaluate((f) => f.requestSubmit());
  await page.waitForURL(
    (url) => {
      const p = new URL(url).pathname;
      return p === '/' || p.startsWith('/pos');
    },
    { timeout: 30000 }
  );
}

async function shot(page, file, url, opts = {}) {
  const dest = path.join(OUT, file);
  if (url) {
    await page.goto(`${BASE}${url}`);
    await dismissOverlay(page);
    await page.waitForTimeout(opts.wait || 1200);
  }
  if (opts.clickSidebar) {
    for (const label of opts.clickSidebar) {
      const btn = page.getByRole('button', { name: label });
      if (await btn.count()) {
        await btn.click();
        await page.waitForTimeout(400);
      }
    }
  }
  await page.screenshot({ path: dest, fullPage: opts.fullPage !== false });
  console.log('  ✓', file);
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  console.log(`Base URL: ${BASE}`);
  console.log(`Output: ${OUT}`);

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  // --- Manager shots ---
  const mgr = await ctx.newPage();
  await login(mgr, managerUser, managerPass);
  await shot(mgr, '01-login.png', '/login');
  await shot(mgr, '03-sidebar-manager.png', '/');
  await shot(mgr, '05-dashboard-manager.png', '/');
  await shot(mgr, '06-pos-retail.png', '/pos', { fullPage: false });
  await shot(mgr, '07-terminal-pos.png', '/pos/billing');
  await shot(mgr, '08-sales-history.png', '/sales');
  await shot(mgr, '09-normal-sale.png', '/normal-sale');
  await shot(mgr, '10-products-list.png', '/products');
  await shot(mgr, '12-categories.png', '/categories');
  await shot(mgr, '13-product-attributes.png', '/product-attributes');
  await shot(mgr, '14-barcodes.png', '/barcodes');
  await shot(mgr, '15-inventory-purchase.png', '/inventory');
  await shot(mgr, '17-inventory-alerts.png', '/inventory');
  await shot(mgr, '18-customers.png', '/customers');
  await shot(mgr, '19-invoices.png', '/invoices');
  await shot(mgr, '20-expenses.png', '/expenses');
  await shot(mgr, '21-income.png', '/income');
  await shot(mgr, '22-accounting.png', '/accounting');
  await shot(mgr, '23-reports-hub.png', '/reports');
  await shot(mgr, '24-pending-approvals.png', '/pending-approvals');
  await shot(mgr, '25-audit-log.png', '/audit-log');
  await mgr.close();

  // --- Admin shots ---
  const adm = await ctx.newPage();
  await login(adm, adminUser, adminPass);
  await shot(adm, '02-dashboard-admin.png', '/');
  await shot(adm, '26-users.png', '/users');
  await shot(adm, '27-roles.png', '/roles');
  await shot(adm, '28-module-settings.png', '/module-settings');
  await shot(adm, '29-system-settings.png', '/system-settings');
  await shot(adm, '30-branches.png', '/branches');
  await shot(adm, '31-financial-approve.png', '/expenses');
  await adm.close();

  // Placeholder composites for modals (reuse list pages if modal capture is flaky)
  for (const name of ['04-roles-reference.png', '11-stock-adjust-modal.png', '16-inventory-transfer.png']) {
    const src = path.join(OUT, name.includes('stock') ? '10-products-list.png' : '15-inventory-purchase.png');
    const dest = path.join(OUT, name);
    if (fs.existsSync(src) && !fs.existsSync(dest)) {
      fs.copyFileSync(src, dest);
      console.log('  ≈', name, '(copy placeholder)');
    }
  }

  await browser.close();
  console.log('\nDone. Run: python scripts/generate_user_manual.py');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
