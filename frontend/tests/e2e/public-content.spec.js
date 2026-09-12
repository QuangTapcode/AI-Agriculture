import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { expectNoHorizontalOverflow } from './helpers/session.js';

const routes = [
  { path: '/articles', name: 'Bài viết' },
  { path: '/pricing-plans', name: 'Gói dịch vụ' },
  { path: '/contact', name: 'Liên hệ' },
  { path: '/khong-ton-tai', name: 'Trang 404' },
];

/**
 * Nhóm nội dung công khai chưa có CMS và chưa có billing, nên không được phép
 * hiện bài viết mẫu hay bảng giá tự đặt. Các chuỗi dưới đây là dấu hiệu một
 * placeholder đã lọt lên giao diện.
 */
const FABRICATED_PATTERNS = [
  /5\+|24\/7|\+3\.2%/,
  /Lorem ipsum/i,
  /\d+\.\d{3}\s*đ\s*\/\s*tháng/i,
  /NaN/,
];

for (const route of routes) {
  test(`${route.name} renders without overflow or placeholder content`, async ({ page }) => {
    const consoleErrors = [];
    page.on('console', (message) => message.type() === 'error' && consoleErrors.push(message.text()));

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

test('public content pages have no serious accessibility violations', async ({ page }) => {
  for (const route of routes) {
    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({ page }).exclude('.field-tilt').analyze();
    const serious = results.violations.filter((item) => ['critical', 'serious'].includes(item.impact));
    expect(serious, `${route.path} → ${serious.map((v) => v.id).join(', ')}`).toEqual([]);
  }
});

test('articles and plans state plainly that nothing is published yet', async ({ page }) => {
  await page.goto('/articles');
  await expect(page.locator('body')).toContainText(/chưa|sắp/i);

  await page.goto('/pricing-plans');
  await expect(page.locator('body')).toContainText(/chưa|sắp/i);
});

test('the contact form reports success only after the API stores the request', async ({ page }) => {
  let posted = null;
  await page.route('**/api/public/contact-requests', async (route) => {
    posted = JSON.parse(route.request().postData() || '{}');
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      // Phong bì đúng như /api/public/contact-requests trả về.
      body: JSON.stringify({
        success: true,
        data: { id: 42, status: 'new', created_at: '2026-09-12T00:00:00Z' },
        source: 'database',
        source_name: 'SupportRequests DB',
        is_mock: false,
      }),
    });
  });

  await page.goto('/contact');
  await page.getByLabel(/Họ và tên/i).fill('Nông hộ thử nghiệm');
  await page.getByLabel(/^Email/i).fill('nonghothunghiem@example.com');
  await page.getByLabel(/Nội dung/i).fill('Tôi muốn hỏi về cảnh báo giá cà phê tại Đắk Lắk.');
  await page.getByRole('button', { name: /Gửi/i }).click();

  await expect(page.locator('body')).toContainText(/42/);
  expect(posted?.website ?? '').toBe('');
});

test('the contact form keeps the request visible when the API rejects it', async ({ page }) => {
  await page.route('**/api/public/contact-requests', (route) =>
    route.fulfill({
      status: 429,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau.' }),
    })
  );

  await page.goto('/contact');
  await page.getByLabel(/Họ và tên/i).fill('Nông hộ thử nghiệm');
  await page.getByLabel(/Số điện thoại/i).fill('0900000000');
  await page.getByLabel(/Nội dung/i).fill('Tôi muốn hỏi về cảnh báo giá cà phê tại Đắk Lắk.');
  await page.getByRole('button', { name: /Gửi/i }).click();

  // Khối xác nhận chỉ được hiện khi database trả về bản ghi; lỗi 429 thì không.
  await expect(page.getByText('Đã lưu vào hệ thống')).toHaveCount(0);
  await expect(page.getByRole('alert')).toContainText(/quá nhiều yêu cầu/i);
  // Nội dung đã nhập phải còn nguyên để người dùng gửi lại.
  await expect(page.getByLabel(/Nội dung/i)).toHaveValue(/cà phê/);
});
