import axios from 'axios';
import { normalizeApiError } from '../utils/apiResponse';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const API_TIMEOUTS = {
  default: Number(import.meta.env.VITE_API_TIMEOUT_MS || 18000),
  ai: Number(import.meta.env.VITE_AI_TIMEOUT_MS || 240000),
  upload: Number(import.meta.env.VITE_UPLOAD_TIMEOUT_MS || 60000),
};

const api = axios.create({
  baseURL: API_URL,
  timeout: API_TIMEOUTS.default,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const isApiTimeoutError = (error) => (
  error?.code === 'ECONNABORTED' ||
  error?.name === 'AbortError' ||
  String(error?.message || '').toLowerCase().includes('timeout')
);

export const withApiTimeout = (kind = 'default', config = {}) => ({
  ...config,
  timeout: config.timeout ?? API_TIMEOUTS[kind] ?? API_TIMEOUTS.default,
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => {
    if (response?.data?.success === false) {
      const normalized = normalizeApiError({ response });
      const error = new Error(normalized.error.message);
      error.normalized = normalized;
      error.response = response;
      return Promise.reject(error);
    }
    return response;
  },
  (error) => {
    if (isApiTimeoutError(error)) {
      error.isTimeout = true;
      error.friendlyMessage = 'Dữ liệu realtime đang chậm. Hệ thống sẽ hiển thị dữ liệu cache nếu có.';
    }
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      const current = window.location.pathname + window.location.search;
      if (current !== '/login') {
        sessionStorage.setItem('returnUrl', current);
      }
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

export const getApiErrorMessage = (error, fallback = 'Không thể kết nối API') => {
  if (error?.normalized?.error?.message) return error.normalized.error.message;
  if (error?.success === false && error?.error?.message) return error.error.message;
  if (error?.friendlyMessage) return error.friendlyMessage;
  if (isApiTimeoutError(error)) {
    return 'Dữ liệu realtime đang chậm. Hệ thống sẽ hiển thị dữ liệu cache nếu có.';
  }
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(', ');
  }
  return detail || error?.response?.data?.message || error?.response?.data?.meta?.error || error?.message || fallback;
};

export const settledValue = (result, fallback = null) => (
  result?.status === 'fulfilled' ? result.value : fallback
);

export const settledErrorMessage = (result, fallback) => (
  result?.status === 'rejected' ? getApiErrorMessage(result.reason, fallback) : null
);

export const fetchWithTimeout = async (url, options = {}, timeoutMs = API_TIMEOUTS.default) => {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      ...options,
      signal: options.signal || controller.signal,
    });
  } finally {
    window.clearTimeout(timer);
  }
};
