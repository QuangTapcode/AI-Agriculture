/**
 * Dựng phiên đăng nhập và chặn tầng mạng cho các route nằm sau ProtectedRoute.
 *
 * E2E của đợt redesign kiểm tra khung giao diện, điều hướng và cách trình bày
 * dữ liệu thiếu — không kiểm tra backend. Hợp đồng dữ liệu thật đã có test
 * riêng ở `backend/tests` và ở tầng service phía frontend.
 */

/** Phong bì giống `api_response`: payload phẳng, kèm metadata nguồn. */
export const envelope = (data = {}, overrides = {}) => ({
  success: true,
  ...data,
  data,
  source: 'database',
  source_name: 'Cơ sở dữ liệu AgriAI',
  is_realtime: false,
  is_cache: false,
  is_mock: false,
  cache_status: 'from_db',
  confidence: null,
  warning: null,
  error: null,
  ...overrides,
});

export const TEST_USER = {
  user_id: 1,
  full_name: 'Nông hộ thử nghiệm',
  email: 'nonghothunghiem@example.com',
  region: 'Dak Lak',
  role: 'farmer',
};

/**
 * @param {import('@playwright/test').Page} page
 * @param {{payload?: object}} [options] payload trả về cho mọi route /api/** còn lại
 */
export const installSession = async (page, { payload } = {}) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(TEST_USER) })
  );

  // SSE phải trả đúng text/event-stream, nếu không trình duyệt tự log lỗi MIME
  // và cổng "không có lỗi console" sẽ báo động vì chính cái stub của ta.
  await page.route('**/api/notifications/stream**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'cache-control': 'no-cache', connection: 'keep-alive' },
      body: ': connected\n\n',
    })
  );

  await page.route('**/api/**', async (route) => {
    const url = route.request().url();
    if (url.includes('/api/auth/me') || url.includes('/api/notifications/stream')) {
      return route.fallback();
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope(payload ?? { region: 'Dak Lak', crop_name: 'lua' })),
    });
  });

  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-test-token');
    localStorage.setItem(
      'agriai_user',
      JSON.stringify({ id: 1, name: 'Nông hộ thử nghiệm', region: 'Dak Lak', role: 'farmer' })
    );
  });
};

/** Trang không được tràn ngang ở bất kỳ khung hình nào. */
export const expectNoHorizontalOverflow = async (page, expect) => {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
};
