import api, { API_URL, getApiErrorMessage, withApiTimeout } from './api';
import { normalizeApiError } from '../utils/apiResponse';

const request = async (factory, fallback) => {
  try {
    const response = await factory();
    const body = response.data;
    return body?.success === true ? body.data : body;
  } catch (error) {
    throw normalizeApiError({ ...error, message: getApiErrorMessage(error, fallback) });
  }
};

export const aiApi = {
  chat: async ({ question, crop, cropName, region, context, sessionId }) => {
    const selectedCrop = crop || cropName;
    const payload = {
      message: question,
      session_id: sessionId,
    };
    if (selectedCrop) {
      payload.crop = selectedCrop;
      payload.crop_name = selectedCrop;
    }
    if (region) payload.region = region;
    if (context) payload.context = context;
    return request(() => api.post('/api/ai-chat/message', payload, withApiTimeout('ai')), 'Không thể kết nối trợ lý AI. Vui lòng thử lại sau.');
  },

  getHistory: async (limit = 20) => {
    return request(() => api.get(`/api/ai-chat/history?limit=${limit}`), 'Không tải được lịch sử chat');
  },

  deleteMessage: async (convId) => {
    return request(() => api.delete(`/api/ai-chat/history/${convId}`), 'Không xóa được tin chat');
  },

  chatStream: async ({ question, crop, cropName, region, context, sessionId, onEvent, signal }) => {
    const selectedCrop = crop || cropName;
    const payload = { message: question, session_id: sessionId };
    if (selectedCrop) {
      payload.crop = selectedCrop;
      payload.crop_name = selectedCrop;
    }
    if (region) payload.region = region;
    if (context) payload.context = context;
    const token = localStorage.getItem('token');
    const fallbackToJson = () => request(
      () => api.post('/api/ai-chat/message', payload, withApiTimeout('ai')),
      'Không thể kết nối trợ lý AI. Vui lòng thử lại sau.',
    );
    // A root base "/" must stay same-origin, not become the hostname in "//api/...".
    let response;
    try {
      response = await fetch(`${API_URL.replace(/\/+$/, '')}/api/ai-chat/message/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/x-ndjson',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
        signal,
      });
    } catch (error) {
      // Tunnels and reverse proxies can expose the JSON route while the
      // streaming route is temporarily unavailable.
      if (signal?.aborted) throw error;
      return fallbackToJson();
    }
    const decoder = new TextDecoder();
    if (!response.ok || !response.body) {
      if ([502, 503, 504].includes(response.status)) return fallbackToJson();
      let message = 'Không thể kết nối trợ lý AI. Vui lòng thử lại sau.';
      try {
        const body = await response.json();
        message = body?.error?.message || body?.detail || message;
      } catch { /* keep friendly fallback */ }
      throw new Error(message);
    }
    const reader = response.body.getReader();
    let buffer = '';
    let completed;
    const consume = (line) => {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      onEvent?.(event);
      if (event.type === 'error') throw new Error(event.payload?.error?.message || 'Trợ lý AI chưa thể trả lời.');
      if (event.type === 'complete') completed = event.payload?.success === true ? event.payload.data : event.payload;
    };
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      lines.forEach(consume);
      if (done) break;
    }
    if (buffer.trim()) consume(buffer);
    if (completed === undefined) throw new Error('Trợ lý AI không trả về kết quả.');
    return completed;
  },

  getConversations: (q = '', offset = 0) => request(
    () => api.get('/api/ai-chat/conversations', { params: { q, offset, limit: 20 } }), 'Không tải được lịch sử chat'),
  getConversation: (id, offset = 0) => request(
    () => api.get(`/api/ai-chat/conversations/${encodeURIComponent(id)}`, { params: { offset, limit: 100 } }), 'Không mở được hội thoại'),
  deleteConversation: (id) => request(
    () => api.delete(`/api/ai-chat/conversations/${encodeURIComponent(id)}`), 'Không xóa được hội thoại'),
  getDocuments: () => request(() => api.get('/api/ai-chat/documents'), 'Không tải được kho tài liệu'),
  getKnowledgeStatus: () => request(
    () => api.get('/api/ai-chat/knowledge-status'), 'Không tải được trạng thái kho tri thức'),
  getKnowledgeDocuments: ({ status = 'approved', q = '' } = {}) => request(
    () => api.get('/api/ai-chat/knowledge-documents', { params: { status, q } }),
    'Không tải được danh sách tài liệu'),
  getKnowledgeSourceCandidates: ({ status = 'pending' } = {}) => request(
    () => api.get('/api/ai-chat/knowledge-source-candidates', { params: { status } }),
    'Không tải được danh sách nguồn mới'),
  approveKnowledgeSourceCandidate: (candidateId) => request(
    () => api.post(`/api/admin/knowledge/source-candidates/${encodeURIComponent(candidateId)}/approve`),
    'Không duyệt được nguồn. Tài khoản cần quyền quản trị.'),
  rejectKnowledgeSourceCandidate: (candidateId) => request(
    () => api.post(`/api/admin/knowledge/source-candidates/${encodeURIComponent(candidateId)}/reject`),
    'Không từ chối được nguồn. Tài khoản cần quyền quản trị.'),
  getKnowledgeDiscovery: (jobId) => request(
    () => api.get(`/api/ai-chat/knowledge-discovery/${encodeURIComponent(jobId)}`),
    'Không tải được trạng thái tìm nguồn'),
  startKnowledgeDiscovery: (payload) => request(
    () => api.post('/api/ai-chat/knowledge-discovery', payload),
    'Không thể bắt đầu tìm nguồn'),
  uploadDocument: (file) => {
    const form = new FormData();
    form.append('file', file);
    return request(() => api.post('/api/ai-chat/documents', form, {
      timeout: 600000, headers: { 'Content-Type': 'multipart/form-data' },
    }), 'Không nạp được tài liệu');
  },
  deleteDocument: (id) => request(() => api.delete(`/api/ai-chat/documents/${id}`), 'Không xóa được tài liệu'),

  clearHistory: async () => {
    return request(() => api.delete('/api/ai-chat/history'), 'Không xóa được lịch sử chat');
  },
};
