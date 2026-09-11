import api, { getApiErrorMessage, withApiTimeout } from './api';
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
