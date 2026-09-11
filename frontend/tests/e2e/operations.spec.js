import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { expectNoHorizontalOverflow, installSession } from './helpers/session.js';

const routes = [
  { path: '/quality', name: 'Kiểm định chất lượng' },
  { path: '/harvest', name: 'Dự báo thu hoạch' },
  { path: '/season-management', name: 'Quản lý mùa vụ' },
  { path: '/alerts', name: 'Cảnh báo' },
  { path: '/notifications', name: 'Thông báo' },
];

/** Dấu hiệu một nhánh mặc định đã lọt lưới và trang tự bịa số liệu. */
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

test('operations pages have no serious accessibility violations', async ({ page }) => {
  for (const route of routes) {
    await installSession(page);
    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({ page }).exclude('.field-tilt').analyze();
    const serious = results.violations.filter((item) => ['critical', 'serious'].includes(item.impact));
    expect(serious, `${route.path} → ${serious.map((v) => v.id).join(', ')}`).toEqual([]);
  }
});

test('notification counters read as unknown when the summary call fails', async ({ page }) => {
  await installSession(page);
  await page.route('**/api/notifications/summary**', (route) =>
    route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"loi"}' })
  );

  await page.goto('/notifications');
  await page.waitForLoadState('networkidle');

  // Không được hiển thị 0 như thể tài khoản thật sự không có thông báo nào.
  const total = page.getByTestId('summary-total');
  if (await total.count()) {
    await expect(total.getByTestId('summary-value')).toHaveText('—');
  }
});
