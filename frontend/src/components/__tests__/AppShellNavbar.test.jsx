import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { name: 'Nông hộ thử nghiệm' },
    logout: vi.fn(),
  }),
}));

import Navbar from '../Navbar';
import { LanguageProvider } from '../../contexts/LanguageContext';

const renderNavbar = (route = '/dashboard') =>
  render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[route]}>
        <Navbar setSidebarOpen={vi.fn()} />
      </MemoryRouter>
    </LanguageProvider>
  );

describe('app shell navbar', () => {
  it('shows no unread notification marker when no count has been loaded', () => {
    renderNavbar();
    const notificationsLink = screen.getByRole('link', { name: /Xem thông báo/i });
    expect(notificationsLink.querySelectorAll('span')).toHaveLength(0);
  });

  it('names the current page for the reports route', () => {
    renderNavbar('/reports');
    expect(screen.getByRole('heading', { level: 1, name: /Báo cáo/i })).toBeInTheDocument();
  });
});
