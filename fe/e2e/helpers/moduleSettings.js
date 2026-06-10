// @ts-check
const { expect } = require('@playwright/test');

/**
 * Open Module features tab and expand a module card if needed.
 * @param {import('@playwright/test').Page} page
 * @param {string} moduleKey e.g. "products"
 */
async function openModuleSettingsCard(page, moduleKey) {
  await page.getByTestId('system-settings-tab-modules').click();
  const card = page.getByTestId(`module-settings-card-${moduleKey}`);
  await card.scrollIntoViewIfNeeded();
  const expanded = await card.getAttribute('aria-expanded');
  if (expanded !== 'true') {
    await card.click();
    await expect(card).toHaveAttribute('aria-expanded', 'true');
  }
}

/**
 * Read switch state from data-testid.
 * @param {import('@playwright/test').Page} page
 * @param {string} testId
 */
async function isModuleSettingOn(page, testId) {
  const toggle = page.getByTestId(testId);
  await toggle.scrollIntoViewIfNeeded();
  const checked = await toggle.getAttribute('aria-checked');
  return checked === 'true';
}

/**
 * Confirm in-app module setting dialog when it appears.
 * @param {import('@playwright/test').Page} page
 */
async function confirmModuleSettingDialog(page) {
  const dialog = page.getByRole('dialog');
  const visible = await dialog.isVisible().catch(() => false);
  if (!visible) return false;

  const apply = dialog.getByRole('button', { name: /apply change|submit for approval/i });
  if (await apply.isVisible().catch(() => false)) {
    await apply.click();
    return true;
  }
  return false;
}

/**
 * Click a module-setting switch. Opens confirm dialog when required.
 * @param {import('@playwright/test').Page} page
 * @param {string} testId
 * @param {{ module?: string }} [options]
 */
async function clickModuleSetting(page, testId, { module = 'products', action = 'apply' } = {}) {
  await openModuleSettingsCard(page, module);
  const toggle = page.getByTestId(testId);
  await toggle.scrollIntoViewIfNeeded();

  let patchDone = null;
  if (action !== 'cancel') {
    patchDone = page.waitForResponse(
      (res) =>
        res.url().includes('/settings/') &&
        res.request().method() === 'PATCH' &&
        res.status() >= 200 &&
        res.status() < 300
    );
  }

  await toggle.click();

  const dialog = page.getByRole('dialog');
  if (await dialog.isVisible({ timeout: 1500 }).catch(() => false)) {
    if (action === 'cancel') {
      await dialog.getByRole('button', { name: /^cancel$/i }).click();
      return;
    }
    const reason = dialog.getByLabel(/reason/i);
    if (await reason.isVisible().catch(() => false)) {
      await reason.fill('E2E automated test change');
    }
    await confirmModuleSettingDialog(page);
  }

  if (patchDone) {
    await patchDone;
  }
}

/** Wait for a module settings toast after PATCH. */
async function expectSettingsToast(page, label) {
  await page
    .getByText(new RegExp(`${label} settings updated|submitted for approval`, 'i'))
    .last()
    .waitFor({
      state: 'visible',
      timeout: 8000,
    });
}

/** Ensure a module setting switch ends up in the desired state. */
async function ensureModuleSetting(page, testId, enabled, options = {}) {
  const module = testId.replace(/^setting-([^-]+)-.*/, '$1');
  await openModuleSettingsCard(page, module);
  await expect(page.getByTestId(testId)).toBeVisible({ timeout: 10000 });
  const isOn = await isModuleSettingOn(page, testId);
  if (isOn === enabled) return false;
  await clickModuleSetting(page, testId, { module });
  return true;
}

module.exports = {
  openModuleSettingsCard,
  isModuleSettingOn,
  clickModuleSetting,
  expectSettingsToast,
  ensureModuleSetting,
};
