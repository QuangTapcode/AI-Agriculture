import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

/**
 * Sinh ảnh và video nghiệm thu cho nhóm đang hoàn thiện.
 * Chạy: npx playwright test tests/e2e/capture-evidence.spec.js --project=<viewport>
 * Kết quả nằm ở docs/redesign/evidence/<nhóm>/ ngoài repo build.
 */
const OUTPUT_DIR = path.resolve(process.cwd(), '..', 'docs', 'redesign', 'evidence', 'group-3-app-shell');

const envelope = (data) => ({
  success: true,
  ...data,
  data,
  source: 'database',
  source_name: 'Cơ sở dữ liệu AgriAI',
  is_mock: false,
  cache_status: 'from_db',
  confidence: null,
  warning: null,
  error: null,
});

const installSession = async (page) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user_id: 1,
        full_name: 'Nông hộ thử nghiệm',
        email: 'nonghothunghiem@example.com',
        region: 'Dak Lak',
        role: 'farmer',
      }),
    })
  );

  await page.route('**/api/**', async (route) => {
    if (route.request().url().includes('/api/auth/me')) return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({ region: 'Dak Lak', crop_name: 'lua' })),
    });
  });

  await page.addInitScript(() => {
    localStorage.setItem('token', 'evidence-token');
    localStorage.setItem(
      'agriai_user',
      JSON.stringify({ id: 1, name: 'Nông hộ thử nghiệm', region: 'Dak Lak', role: 'farmer' })
    );
  });
};

// Video chỉ bật cho file này để không làm chậm bộ e2e thường.
// Không ép size: để Playwright ghi đúng khung hình của từng project, nếu không
// video "mobile" lại là trang 390px bị phóng vào khung 1280x800.
test.use({ video: 'on' });

test.beforeAll(() => {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
});

for (const route of ['/dashboard', '/reports']) {
  test(`capture ${route}`, async ({ page }, testInfo) => {
    await installSession(page);
    await page.goto(route);
    await page.waitForLoadState('networkidle');

    const slug = route.replace(/\//g, '') || 'home';
    const file = path.join(OUTPUT_DIR, `${slug}-${testInfo.project.name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    expect(fs.existsSync(file)).toBe(true);
  });
}

test('capture the mobile drawer open', async ({ page }, testInfo) => {
  test.skip((page.viewportSize()?.width ?? 0) >= 1024, 'drawer only exists below lg');

  await installSession(page);
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'Mở menu' }).click();
  // Drawer trượt 300ms: chờ transform dừng hẳn rồi mới chụp.
  await page.locator('aside').evaluate((node) =>
    Promise.all(node.getAnimations({ subtree: true }).map((animation) => animation.finished))
  );
  await expect(page.getByRole('link', { name: 'Báo cáo' })).toBeInViewport({ ratio: 1 });

  const file = path.join(OUTPUT_DIR, `drawer-open-${testInfo.project.name}.png`);
  await page.screenshot({ path: file });
  expect(fs.existsSync(file)).toBe(true);
});

test('record a scroll pass over the dashboard', async ({ page }, testInfo) => {
  await installSession(page);
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');

  const height = await page.evaluate(() => document.body.scrollHeight);
  // Bước nhỏ và nghỉ lâu hơn để video đủ chậm cho người xem đọc được nội dung.
  const step = Math.max(Math.round((page.viewportSize()?.height ?? 800) / 6), 90);

  await page.waitForTimeout(900);
  for (let offset = 0; offset < height; offset += step) {
    await page.mouse.wheel(0, step);
    await page.waitForTimeout(160);
  }
  await page.waitForTimeout(900);

  // Playwright chỉ ghi xong video khi context đóng; copy ở teardown của testInfo.
  const target = path.join(OUTPUT_DIR, `scroll-${testInfo.project.name}.webm`);
  const video = page.video();
  testInfo.annotations.push({ type: 'scroll-pass', description: `${height}px` });

  await page.close();
  if (video) {
    await video.saveAs(target);
    expect(fs.existsSync(target)).toBe(true);
  }
});
