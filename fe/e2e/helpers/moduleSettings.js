// @ts-check
const { expect } = require('@playwright/test');

const HIGH_IMPACT_CONFIRM =
  /checkout, permissions, stock rules, or data access/i;

/**
 * Click a module-setting checkbox (controlled component — use click, not check/uncheck).
 * @param {import('@playwright/test').Page} page
 * @param {string} testId
 * @param {{ confirm?: 'accept' | 'dismiss' | 'none' }} [options]
 */
async function clickModuleSetting(page, testId, { confirm = 'none' } = {}) {
  const checkbox = page.getByTestId(testId);
  await checkbox.scrollIntoViewIfNeeded();

  if (confirm !== 'none') {
    page.once('dialog', async (dialog) => {
      if (confirm === 'accept') {
        await dialog.accept();
      } else {
        await dialog.dismiss();
      }
    });
  }

  let patchDone = null;
  if (confirm !== 'dismiss') {
    patchDone = page.waitForResponse(
      (res) =>
        res.url().includes('/settings/') &&
        res.request().method() === 'PATCH' &&
        res.status() >= 200 &&
        res.status() < 300
    );
  }

  await checkbox.click();
  if (patchDone) {
    await patchDone;
  }
}

/** Wait for a module settings toast after PATCH. */
async function expectSettingsToast(page, label) {
  await page.getByText(`${label} settings updated`, { exact: true }).last().waitFor({
    state: 'visible',
    timeout: 8000,
  });
}

/** Ensure a module setting checkbox ends up in the desired state. */
async function ensureModuleSetting(page, testId, enabled, { confirm = 'none' } = {}) {
  const checkbox = page.getByTestId(testId);
  await expect(checkbox).toBeVisible({ timeout: 10000 });
  const isOn = await checkbox.isChecked();
  if (isOn === enabled) return false;
  await clickModuleSetting(page, testId, { confirm });
  return true;
}

module.exports = {
  HIGH_IMPACT_CONFIRM,
  clickModuleSetting,
  expectSettingsToast,
  ensureModuleSetting,
};
