import { expect, test } from '@playwright/test';
import { installSession } from './helpers/session.js';

test('sending a question streams through the configured same-origin API', async ({ page }) => {
  await installSession(page);
  let requestUrl;
  await page.route('**/ai-chat/message/stream', async (route) => {
    requestUrl = route.request().url();
    await route.fulfill({
      contentType: 'application/x-ndjson',
      body: JSON.stringify({ type: 'complete', payload: { success: true, data: {
        reply: 'Kết quả kiểm thử đường truyền.', history_saved: false,
      } } }) + '\n',
    });
  });
  await page.goto('/ai-chat');
  await page.getByRole('textbox', { name: 'Câu hỏi cho trợ lý' }).fill('Kỹ thuật trồng nho');
  await page.getByRole('button', { name: 'Gửi câu hỏi', exact: true }).click();
  await expect(page.getByText('Kết quả kiểm thử đường truyền.', { exact: true })).toBeVisible();
  expect(requestUrl).toBe(new URL('/api/ai-chat/message/stream', page.url()).href);
  await expect(page.getByText('Failed to fetch', { exact: true })).toHaveCount(0);
});
