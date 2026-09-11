import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { expectNoHorizontalOverflow, installSession } from './helpers/session.js';

const routes = [
  { path: '/ai-chat', name: 'Trợ lý AI' },
  { path: '/knowledge-documents', name: 'Kho tài liệu' },
  { path: '/settings', name: 'Cài đặt' },
  { path: '/profile', name: 'Hồ sơ' },
];

const FABRICATED_PATTERNS = [/NaN/, /Độ tin cậy 0%/, /Độ tin cậy: 0%/];

for (const route of routes) {
  test(`${route.name} renders without overflow or fabricated figures`, async ({ page }) => {
    const consoleErrors = [];
    page.on('console', (message) => message.type() === 'error' && consoleErrors.push(message.text()));

    await installSession(page);
    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expectNoHorizontalOverflow(page, expect);

    const body = page.locator('body');
    for (const pattern of FABRICATED_PATTERNS) {
      await expect(body).not.toContainText(pattern);
    }

    expect(consoleErrors).toEqual([]);
  });
}

test('AI and account pages have no serious accessibility violations', async ({ page }) => {
  for (const route of routes) {
    await installSession(page);
    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({ page }).exclude('.field-tilt').analyze();
    const serious = results.violations.filter((item) => ['critical', 'serious'].includes(item.impact));
    expect(serious, `${route.path} → ${serious.map((v) => v.id).join(', ')}`).toEqual([]);
  }
});
