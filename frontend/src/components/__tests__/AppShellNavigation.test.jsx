import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Sidebar, { navigation } from '../Sidebar';
import { LEGACY_ROUTE_REDIRECTS } from '../../routes/appRoutes';
import { LanguageProvider } from '../../contexts/LanguageContext';

const renderSidebar = ({ open = true, setOpen = vi.fn(), route = '/dashboard' } = {}) => {
  render(
    <LanguageProvider>
      <MemoryRouter initialEntries={[route]}>
        <Sidebar open={open} setOpen={setOpen} />
      </MemoryRouter>
    </LanguageProvider>
  );
  return { setOpen };
};

describe('app shell navigation', () => {
  it('offers the reports page in the sidebar', () => {
    const hrefs = navigation.map((item) => item.href);
    expect(hrefs).toContain('/reports');
  });

  it('never links to a retired route', () => {
    const retired = Object.keys(LEGACY_ROUTE_REDIRECTS);
    const linked = navigation.map((item) => item.href);
    expect(linked.filter((href) => retired.includes(href))).toEqual([]);
  });

  it('renders no anchor pointing at a retired route', () => {
    renderSidebar();
    const retired = Object.keys(LEGACY_ROUTE_REDIRECTS);
    const hrefs = screen.getAllByRole('link').map((link) => link.getAttribute('href'));
    expect(hrefs.filter((href) => retired.includes(href))).toEqual([]);
  });
});

describe('mobile drawer', () => {
  it('closes when the user presses Escape', async () => {
    const user = userEvent.setup();
    const { setOpen } = renderSidebar({ open: true });

    await user.keyboard('{Escape}');

    expect(setOpen).toHaveBeenCalledWith(false);
  });

  it('closes after the user follows a navigation link', async () => {
    const user = userEvent.setup();
    const { setOpen } = renderSidebar({ open: true });

    await user.click(screen.getByRole('link', { name: /Báo cáo/i }));

    expect(setOpen).toHaveBeenCalledWith(false);
  });

  it('marks the active route for assistive technology', () => {
    renderSidebar({ route: '/reports' });

    expect(screen.getByRole('link', { name: /Báo cáo/i })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: /Bảng điều khiển/i })).not.toHaveAttribute('aria-current');
  });
});
