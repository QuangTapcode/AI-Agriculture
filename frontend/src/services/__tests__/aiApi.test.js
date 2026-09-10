import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../api';
import { aiApi } from '../aiApi';

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
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

  it('encodes the selected conversation id and unwraps deletion response', async () => {
    api.delete.mockResolvedValue({ status: 200, data: { success: true, data: { deleted_count: 2 } } });
    expect(await aiApi.deleteConversation('a/b')).toEqual({ deleted_count: 2 });
    expect(api.delete).toHaveBeenCalledWith('/api/ai-chat/conversations/a%2Fb');
  });
});
