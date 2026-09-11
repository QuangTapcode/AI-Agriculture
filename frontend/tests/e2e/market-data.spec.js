import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { expectNoHorizontalOverflow, installSession } from './helpers/session.js';

const routes = [
  { path: '/weather', name: 'Thời tiết' },
  { path: '/pricing', name: 'Định giá' },
  { path: '/crop/ca-phe', name: 'Chi tiết cây trồng' },
  { path: '/market', name: 'Phân tích thị trường' },
];

/**
 * Những chuỗi chỉ xuất hiện khi trang tự bịa ra số liệu từ dữ liệu trống.
 * Nếu một trong số này quay lại, nghĩa là một nhánh mặc định đã lọt lưới.
 */
const FABRICATED_PATTERNS = [
  /Độ tin cậy:\s*0%/,
  /thích hợp phun thuốc, bón phân/,
  /CẬP NHẬT HÔM NAY/,
  /\+0\.0%/,
];

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

test('the weather page offers no farming advice for an hour it has no readings for', async ({ page }) => {
  await installSession(page, { payload: { region: 'Dak Lak', hourly: [], daily: [] } });
  await page.goto('/weather');
  await page.waitForLoadState('networkidle');

  await expect(page.locator('body')).not.toContainText(/Ít mưa — thích hợp phun thuốc/);
  await expect(page.locator('body')).not.toContainText(/Độ ẩm phù hợp canh tác/);
});

test('market data pages have no serious accessibility violations', async ({ page }) => {
  for (const route of routes) {
    await installSession(page);
    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({ page }).exclude('.field-tilt').analyze();
    const serious = results.violations.filter((item) => ['critical', 'serious'].includes(item.impact));
    expect(serious, `${route.path} → ${serious.map((v) => v.id).join(', ')}`).toEqual([]);
  }
});

test('the pricing search form is usable with the keyboard alone', async ({ page }) => {
  await installSession(page);
  await page.goto('/pricing');
  await page.waitForLoadState('networkidle');

  const crop = page.getByLabel('Nông sản');
  await page.keyboard.press('Tab');
  await crop.focus();
  await expect(crop).toBeFocused();

  const outlineStyle = await crop.evaluate((node) => getComputedStyle(node).outlineStyle);
  const borderColor = await crop.evaluate((node) => getComputedStyle(node).borderColor);
  expect(outlineStyle !== 'none' || borderColor !== 'rgb(209, 213, 219)').toBe(true);
});
