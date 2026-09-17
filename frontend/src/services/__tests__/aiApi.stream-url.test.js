import { afterEach, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
  localStorage.clear();
});

it.each([
  ['/', 'https://agriai-demo.pages.dev/api/ai-chat/message/stream'],
  ['https://backend.example/', 'https://backend.example/api/ai-chat/message/stream'],
  ['http://127.0.0.1:8000', 'http://127.0.0.1:8000/api/ai-chat/message/stream'],
  ['/gateway/', 'https://agriai-demo.pages.dev/gateway/api/ai-chat/message/stream'],
])('streams chat to the configured API base %s', async (base, expectedUrl) => {
  vi.stubEnv('VITE_API_URL', base);
  vi.resetModules();
  // Import the real API configuration: mocking API_URL as empty hid the production bug.
  const { aiApi } = await import('../aiApi');
  const fetchMock = vi.fn(async (url) => {
    expect(new URL(url, 'https://agriai-demo.pages.dev/ai-chat').href).toBe(expectedUrl);
    return {
      ok: true,
      body: { getReader: () => ({ read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(
          JSON.stringify({ type: 'complete', payload: { success: true, data: { reply: 'Đã nhận' } } }) + '\n',
        ) })
        .mockResolvedValueOnce({ done: true }),
      }) },
    };
  });
  vi.stubGlobal('fetch', fetchMock);
  localStorage.setItem('token', 'test-token');

  expect(await aiApi.chatStream({ question: 'Cây nho', sessionId: 'session-test' })).toEqual({ reply: 'Đã nhận' });
  expect(fetchMock).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
    method: 'POST',
    headers: expect.objectContaining({ Authorization: 'Bearer test-token', Accept: 'application/x-ndjson' }),
    body: JSON.stringify({ message: 'Cây nho', session_id: 'session-test' }),
  }));
});
