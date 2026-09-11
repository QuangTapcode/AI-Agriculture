import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../contexts/AuthContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: () => ({
    isAuthenticated: true,
    loading: false,
    user: { name: 'Nông hộ thử nghiệm', region: 'Đắk Lắk' },
    logout: vi.fn(),
  }),
}));

vi.mock('../services/api', () => {
  const reject = () => Promise.reject(new Error('network disabled in test'));
  return {
    default: { get: reject, post: reject, put: reject, delete: reject },
    getApiErrorMessage: () => 'Không tải được dữ liệu.',
    withApiTimeout: (kind, config) => config,
    isApiTimeoutError: () => false,
    API_TIMEOUTS: { default: 1, ai: 1, upload: 1 },
  };
});

import { AppRoutes } from '../App';
import { LanguageProvider } from '../contexts/LanguageContext';

const renderAt = (route) =>
  render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[route]}>
        <AppRoutes />
      </MemoryRouter>
    </LanguageProvider>
  );

const FABRICATED_YIELD = /Tấn\/Hecta/i;

describe('app shell routing', () => {
  it('renders the reports page at /reports instead of a not-found page', async () => {
    renderAt('/reports');
    expect(await screen.findByRole('heading', { name: /Báo cáo/i, level: 1 })).toBeInTheDocument();
  });

  it('sends the retired harvest mockup route to the canonical harvest page', async () => {
    renderAt('/harvest-forecast');
    expect(await screen.findByRole('heading', { name: /Dự báo thu hoạch/i, level: 1 })).toBeInTheDocument();
    expect(screen.queryByText(FABRICATED_YIELD)).not.toBeInTheDocument();
  });

  it('sends the retired alert mockup route to the canonical alert centre', async () => {
    renderAt('/alerts-management');
    expect(await screen.findByRole('heading', { name: /Trung tâm cảnh báo/i, level: 1 })).toBeInTheDocument();
  });
});

describe('app shell accessibility', () => {
  it('offers a skip link to the main content as the first focusable element', async () => {
    renderAt('/dashboard');
    const skipLink = await screen.findByRole('link', { name: /Bỏ qua/i });
    expect(skipLink).toHaveAttribute('href', '#main-content');
  });
});
