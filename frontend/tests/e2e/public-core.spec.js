import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const routes = ['/', '/features', '/login', '/register'];

for (const route of routes) {
  test(`${route} has no horizontal overflow or fabricated public metrics`, async ({ page }) => {
    const consoleErrors = [];
    page.on('console', (message) => message.type() === 'error' && consoleErrors.push(message.text()));
    await page.goto(route);
    await page.waitForLoadState('networkidle');

    const dimensions = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
    await expect(page.locator('body')).not.toContainText(/5\+|24\/7|\+3\.2%|100 người/);
    expect(consoleErrors).toEqual([]);
  });
}

test('public navigation works with keyboard and mobile menu', async ({ page, isMobile }) => {
  await page.goto('/');
  if (isMobile) {
    await page.getByRole('button', { name: 'Mở menu' }).click();
    await expect(page.getByRole('navigation', { name: 'Điều hướng trên điện thoại' })).toBeVisible();
  }
  // Chromium chỉ bật :focus-visible sau một tương tác bàn phím thật; nếu chỉ
  // gọi .focus() trên thiết bị cảm ứng thì vòng focus hợp lệ vẫn bị coi là ẩn.
  await page.keyboard.press('Tab');
  const homeLink = page.getByRole('link', { name: 'Về trang chủ AgriAI' });
  await homeLink.focus();
  await expect(homeLink).toBeFocused();
  const outlineStyle = await homeLink.evaluate((node) => getComputedStyle(node).outlineStyle);
  expect(outlineStyle).not.toBe('none');
});

test('landing page has no serious accessibility violations', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  const results = await new AxeBuilder({ page }).exclude('.field-tilt').analyze();
  expect(results.violations.filter((item) => ['critical', 'serious'].includes(item.impact))).toEqual([]);
});

test('reduced motion removes long animation durations', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto('/');
  const duration = await page.locator('.field-reveal').first().evaluate((node) => getComputedStyle(node).transitionDuration);
  expect(Number.parseFloat(duration)).toBeLessThanOrEqual(0.001);
  await context.close();
});

test('decorative cards stay inside the viewport at every width', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  /*
   * .field-tilt ghi đè thuộc tính transform, nên nếu nó dùng chung element với
   * một utility transform của Tailwind (ví dụ -translate-x-1/2) thì phần căn
   * chỉnh bị nuốt và thẻ trôi ra ngoài khung nhìn. overflow-hidden của section
   * che mất lỗi này khỏi phép đo tràn ngang, nên cần kiểm riêng.
   */
  const overflowing = await page.evaluate(() => {
    const viewport = window.innerWidth;
    return [...document.querySelectorAll('.field-tilt')]
      .map((node) => {
        const rect = node.getBoundingClientRect();
        return { right: Math.round(rect.right), left: Math.round(rect.left), viewport };
      })
      .filter((box) => box.right > box.viewport + 1 || box.left < -1);
  });

  expect(overflowing).toEqual([]);
});
