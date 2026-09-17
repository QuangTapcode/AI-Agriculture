import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../api';
import { aiApi } from '../aiApi';

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
  API_URL: '',
  withApiTimeout: () => ({ timeout: 240000 }),
  getApiErrorMessage: (error, fallback) => error.message || fallback,
}));

describe('assistant API contracts', () => {
  beforeEach(() => vi.clearAllMocks());

  it('unwraps chat once so reply, citations and persistence status reach the UI', async () => {
    const data = { reply: 'Theo tài liệu [TL1]', rag: { sources: [{ citation: 'TL1' }] }, history_saved: true };
    api.post.mockResolvedValue({ status: 200, data: { success: true, data } });
    expect(await aiApi.chat({ question: 'Câu hỏi', sessionId: 'session-a' })).toEqual(data);
    expect(api.post).toHaveBeenCalledWith('/api/ai-chat/message', { message: 'Câu hỏi', session_id: 'session-a' }, expect.any(Object));
  });

  it('reads NDJSON progress and completion events from the streaming endpoint', async () => {
    const originalFetch = global.fetch;
    const chunks = [
      '{"type":"status","stage":"retrieving"}\n',
      '{"type":"complete","payload":{"success":true,"data":{"reply":"Đã xong"}}}\n',
    ];
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => ({
        read: vi.fn()
          .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(chunks[0]) })
          .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(chunks[1]) })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      }) },
    });
    const seen = [];
    const result = await aiApi.chatStream({ question: 'Xin chào', sessionId: 's1', onEvent: (event) => seen.push(event) });
    expect(result).toEqual({ reply: 'Đã xong' });
    expect(seen.map((event) => event.type)).toEqual(['status', 'complete']);
    global.fetch = originalFetch;
  });

  it('falls back to the JSON endpoint when the stream route is unreachable', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    api.post.mockResolvedValue({
      status: 200,
      data: { success: true, data: { reply: 'Đã nhận câu hỏi' } },
    });

    await expect(aiApi.chatStream({ question: 'Nho', sessionId: 's2' }))
      .resolves.toEqual({ reply: 'Đã nhận câu hỏi' });
    expect(api.post).toHaveBeenCalledWith(
      '/api/ai-chat/message',
      { message: 'Nho', session_id: 's2' },
      expect.any(Object),
    );
  });

  it('keeps bare history and document responses instead of dropping them as unsuccessful', async () => {
    const history = { total: 1, history: [{ id: 'a' }], has_more: false };
    api.get.mockResolvedValue({ status: 200, data: history });
    expect(await aiApi.getConversations('lúa', 20)).toEqual(history);
    expect(api.get).toHaveBeenCalledWith('/api/ai-chat/conversations', { params: { q: 'lúa', offset: 20, limit: 20 } });
    api.get.mockResolvedValue({ status: 200, data: { documents: [{ id: 'doc' }] } });
    expect((await aiApi.getDocuments()).documents[0].id).toBe('doc');
    api.get.mockResolvedValue({ status: 200, data: { configured_sources: 11, index_status: 'ready' } });
    expect((await aiApi.getKnowledgeStatus()).configured_sources).toBe(11);
    expect(api.get).toHaveBeenCalledWith('/api/ai-chat/knowledge-status');
  });

  it('normalizes failures for a visible error message', async () => {
    api.get.mockRejectedValue(new Error('Kho tài liệu chưa sẵn sàng'));
    await expect(aiApi.getDocuments()).rejects.toMatchObject({ message: 'Kho tài liệu chưa sẵn sàng' });
  });

  it('loads the shared knowledge catalogue with filters', async () => {
    const catalogue = { documents: [{ id: 1, indexed: true }], summary: { indexed_documents: 1 } };
    api.get.mockResolvedValue({ status: 200, data: catalogue });

    expect(await aiApi.getKnowledgeDocuments({ status: 'approved', q: 'cà phê' })).toEqual(catalogue);
    expect(api.get).toHaveBeenCalledWith('/api/ai-chat/knowledge-documents', {
      params: { status: 'approved', q: 'cà phê' },
    });
  });

  it('loads query-triggered discovery progress by job id', async () => {
    const job = { job: { job_id: 9, status: 'indexed' } };
    api.get.mockResolvedValue({ status: 200, data: job });

    expect(await aiApi.getKnowledgeDiscovery(9)).toEqual(job);
    expect(api.get).toHaveBeenCalledWith('/api/ai-chat/knowledge-discovery/9');
  });

  it('starts query discovery immediately with the submitted topic', async () => {
    const job = { job_id: 10, status: 'queued', keywords: ['nho ngón tay', 'Đà Nẵng'] };
    api.post.mockResolvedValue({ status: 200, data: job });

    expect(await aiApi.startKnowledgeDiscovery({ question: 'Kỹ thuật trồng nho ngón tay tại Đà Nẵng' })).toEqual(job);
    expect(api.post).toHaveBeenCalledWith('/api/ai-chat/knowledge-discovery', {
      question: 'Kỹ thuật trồng nho ngón tay tại Đà Nẵng',
    });
  });

  it('encodes the selected conversation id and unwraps deletion response', async () => {
    api.delete.mockResolvedValue({ status: 200, data: { success: true, data: { deleted_count: 2 } } });
    expect(await aiApi.deleteConversation('a/b')).toEqual({ deleted_count: 2 });
    expect(api.delete).toHaveBeenCalledWith('/api/ai-chat/conversations/a%2Fb');
  });
});
