import api, { getApiErrorMessage } from './api';

export const publicApi = {
  async createContactRequest(payload) {
    try {
      const response = await api.post('/api/public/contact-requests', payload);
      return response.data?.data;
    } catch (error) {
      throw new Error(getApiErrorMessage(error, 'Không thể lưu yêu cầu. Vui lòng thử lại.'));
    }
  },
};
