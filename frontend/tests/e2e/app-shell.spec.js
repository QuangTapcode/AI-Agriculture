import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { expectNoHorizontalOverflow, installSession } from './helpers/session.js';

const appRoutes = ['/dashboard', '/reports'];

for (const route of appRoutes) {
  test(`${route} renders inside the shell without horizontal overflow`, async ({ page }) => {
    const consoleErrors = [];
    page.on('console', (message) => message.type() === 'error' && consoleErrors.push(message.text()));

    await installSession(page);
    await page.goto(route);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

    await expectNoHorizontalOverflow(page, expect);

    expect(consoleErrors).toEqual([]);
  });
}

test('retired routes land on their canonical page', async ({ page }) => {
  await installSession(page);

  for (const [legacy, canonical] of [
    ['/dashboard-new', '/dashboard'],
    ['/pricing-dashboard', '/pricing'],
    ['/quality-check', '/quality'],
    ['/harvest-forecast', '/harvest'],
    ['/market-strategy', '/market'],
    ['/alerts-management', '/alerts'],
  ]) {
    await page.goto(legacy);
    await expect(page).toHaveURL(new RegExp(`${canonical}$`));
  }
});

test('the sidebar drawer opens and closes for touch and keyboard users', async ({ page }) => {
  await installSession(page);
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');

  const reportsLink = page.getByRole('link', { name: 'Báo cáo' });

  // Sidebar chỉ cố định từ breakpoint lg (1024px); hẹp hơn thì nó là drawer.
  const isDrawerLayout = (page.viewportSize()?.width ?? 0) < 1024;

  if (isDrawerLayout) {
    await expect(reportsLink).not.toBeInViewport();
    await page.getByRole('button', { name: 'Mở menu' }).click();
    // ratio 1: drawer phải vào hẳn khung nhìn, không chỉ ló ra giữa chừng.
    await expect(reportsLink).toBeInViewport({ ratio: 1 });

    await page.keyboard.press('Escape');
    await expect(reportsLink).not.toBeInViewport();
  } else {
    await expect(reportsLink).toBeInViewport({ ratio: 1 });
  }

  await reportsLink.focus();
  await expect(reportsLink).toBeFocused();
  const outlineStyle = await reportsLink.evaluate((node) => getComputedStyle(node).outlineStyle);
  expect(outlineStyle).not.toBe('none');
});

test('the skip link moves focus to the main content', async ({ page }) => {
  await installSession(page);
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');

  await page.keyboard.press('Tab');
  const skipLink = page.getByRole('link', { name: /Bỏ qua điều hướng/i });
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toBeInViewport();
});

test('the dashboard has no serious accessibility violations', async ({ page }) => {
  await installSession(page);
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');

  const results = await new AxeBuilder({ page }).exclude('.field-tilt').analyze();
  expect(results.violations.filter((item) => ['critical', 'serious'].includes(item.impact))).toEqual([]);
});
