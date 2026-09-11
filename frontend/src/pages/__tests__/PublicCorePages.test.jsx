import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    login: vi.fn(),
    register: vi.fn(),
  }),
}));

import FeaturesPage from '../FeaturesPage';
import LandingPage from '../LandingPage';
import LoginPage from '../LoginPage';

const renderPage = (element) => renderToStaticMarkup(<MemoryRouter>{element}</MemoryRouter>);

describe('public core pages', () => {
  it('renders the landing page without fabricated marketing metrics', () => {
    const html = renderPage(<LandingPage />);
    expect(html).toContain('Hiểu mùa vụ');
    expect(html).toContain('Quyết định sớm');
    expect(html).not.toMatch(/5\+|24\/7|\+3\.2%|1\.000|100 người/);
    expect(html).not.toContain('Dữ liệu thời gian thực');
  });

  it('lists only implemented product workflows without internal roadmap copy', () => {
    const html = renderPage(<FeaturesPage />);
    expect(html).toContain('Theo dõi điều kiện canh tác');
    expect(html).toContain('Đối chiếu giá và thị trường');
    expect(html).toContain('Hỏi trợ lý có nguồn');
    expect(html).not.toContain('Nâng cấp nên làm tiếp');
    expect(html).not.toContain('Checklist chỉnh sửa');
  });

  it('opens the register route in register mode', () => {
    const html = renderPage(<LoginPage initialMode="register" />);
    expect(html).toContain('Tạo tài khoản');
    expect(html).toContain('Họ tên');
  });
});
