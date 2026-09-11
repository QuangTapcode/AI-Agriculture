import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const summaryFn = vi.fn();
const unreadCount = vi.fn();
const list = vi.fn();

vi.mock('../../services/notificationsApi', () => ({
  notificationsApi: {
    summary: (...a) => summaryFn(...a),
    unreadCount: (...a) => unreadCount(...a),
    list: (...a) => list(...a),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
    remove: vi.fn(),
  },
}));

vi.mock('../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getApiErrorMessage: (error, fallback) => error?.message || fallback,
}));

import NotificationsPage from '../NotificationsPage';

const renderNotifications = () =>
  render(
    <MemoryRouter>
      <NotificationsPage />
    </MemoryRouter>
  );

describe('notification counters', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    list.mockResolvedValue({ notifications: [] });
  });

  it('does not claim zero counts when the summary call failed', async () => {
    summaryFn.mockRejectedValue(new Error('offline'));
    unreadCount.mockRejectedValue(new Error('offline'));

    renderNotifications();

    const total = await screen.findByTestId('summary-total');
    expect(within(total).getByTestId('summary-value')).toHaveTextContent('—');
  });

  it('shows the counts the backend reported, including a real zero', async () => {
    summaryFn.mockResolvedValue({ total: 12, by_type: { price: 0 }, delivery_failed: 2 });
    unreadCount.mockResolvedValue({ unread_count: 5 });

    renderNotifications();

    const total = await screen.findByTestId('summary-total');
    expect(within(total).getByTestId('summary-value')).toHaveTextContent('12');
    expect(within(screen.getByTestId('summary-unread')).getByTestId('summary-value')).toHaveTextContent('5');
    expect(within(screen.getByTestId('summary-price')).getByTestId('summary-value')).toHaveTextContent('0');
  });

  it('does not stamp a fabricated confidence onto the summary', async () => {
    summaryFn.mockResolvedValue({ total: 3 });
    unreadCount.mockResolvedValue({ unread_count: 1 });

    renderNotifications();

    await screen.findByTestId('summary-total');
    expect(screen.queryByText(/70%/)).not.toBeInTheDocument();
  });
});
