import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { installSession } from './helpers/session.js';

/**
 * Sinh ảnh và video nghiệm thu cho một nhóm page.
 *
 * Chạy:       npx playwright test tests/e2e/capture-evidence.spec.js
 * Chọn nhóm:  EVIDENCE_GROUP=group-4-market-data npx playwright test ...
 *
 * Kết quả nằm ngoài build, ở docs/redesign/evidence/<nhóm>/.
 */
const GROUPS = {
  'group-3-app-shell': [
    { path: '/dashboard', slug: 'dashboard' },
    { path: '/reports', slug: 'reports' },
  ],
  'group-4-market-data': [
    { path: '/weather', slug: 'weather' },
    { path: '/pricing', slug: 'pricing' },
    { path: '/crop/ca-phe', slug: 'crop-detail' },
    { path: '/market', slug: 'market' },
  ],
};

const GROUP = process.env.EVIDENCE_GROUP || 'group-3-app-shell';
const ROUTES = GROUPS[GROUP];
const OUTPUT_DIR = path.resolve(process.cwd(), '..', 'docs', 'redesign', 'evidence', GROUP);

if (!ROUTES) {
  throw new Error(
    `EVIDENCE_GROUP không hợp lệ: ${GROUP}. Chọn một trong ${Object.keys(GROUPS).join(', ')}`
  );
}

// Video chỉ bật cho file này để không làm chậm bộ e2e thường.
// Không ép size: để Playwright ghi đúng khung hình của từng project, nếu không
// video "mobile" lại là trang 390px bị phóng vào khung 1280x800.
test.use({ video: 'on' });

test.beforeAll(() => {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
});

for (const route of ROUTES) {
  test(`capture ${route.path}`, async ({ page }, testInfo) => {
    await installSession(page);
    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    const file = path.join(OUTPUT_DIR, `${route.slug}-${testInfo.project.name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    expect(fs.existsSync(file)).toBe(true);
  });
}

test('capture the mobile drawer open', async ({ page }, testInfo) => {
  test.skip((page.viewportSize()?.width ?? 0) >= 1024, 'drawer only exists below lg');

  await installSession(page);
  await page.goto(ROUTES[0].path);
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

test('record a scroll pass over the first page of the group', async ({ page }, testInfo) => {
  await installSession(page);
  await page.goto(ROUTES[0].path);
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

  // Playwright chỉ ghi xong video khi page đóng.
  const target = path.join(OUTPUT_DIR, `scroll-${testInfo.project.name}.webm`);
  const video = page.video();
  testInfo.annotations.push({ type: 'scroll-pass', description: `${height}px` });

  await page.close();
  if (video) {
    await video.saveAs(target);
    expect(fs.existsSync(target)).toBe(true);
  }
});
