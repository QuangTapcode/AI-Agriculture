import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: false }),
}));

import ArticlesPage from '../ArticlesPage';
import ContactPage from '../ContactPage';
import NotFoundPage from '../NotFoundPage';
import SubscriptionPricingPage from '../SubscriptionPricingPage';
import { publicApi } from '../../services/publicApi';

vi.mock('../../services/publicApi', () => ({
  publicApi: {
    createContactRequest: vi.fn(),
  },
}));

const renderPage = (page) => render(<MemoryRouter>{page}</MemoryRouter>);

describe('public content pages', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it('shows a truthful empty state when no verified articles exist', () => {
    renderPage(<ArticlesPage />);

    expect(screen.getByRole('heading', { name: /chưa có bài viết đã xác minh/i })).toBeInTheDocument();
    expect(screen.queryByText(/5 phút đọc|24\/7|mới cập nhật/i)).not.toBeInTheDocument();
  });

  it('does not invent plans, prices or limits before billing exists', () => {
    renderPage(<SubscriptionPricingPage />);

    expect(screen.getByRole('heading', { name: /gói dịch vụ chưa được công bố/i })).toBeInTheDocument();
    expect(screen.queryByText(/99\.000|299\.000|5 lượt\/ngày/i)).not.toBeInTheDocument();
  });

  it('only confirms a contact request after the database returns an id', async () => {
    const user = userEvent.setup();
    publicApi.createContactRequest.mockResolvedValue({
      id: 42,
      status: 'new',
      created_at: '2026-09-12T08:00:00',
    });
    renderPage(<ContactPage />);

    await user.type(screen.getByLabelText(/họ và tên/i), 'Nguyễn An');
    await user.type(screen.getByLabelText(/^email/i), 'an@example.com');
    await user.type(screen.getByLabelText(/nội dung/i), 'Tôi cần hỗ trợ kết nối dữ liệu thời tiết.');
    await user.click(screen.getByRole('button', { name: /gửi yêu cầu/i }));

    await waitFor(() => expect(publicApi.createContactRequest).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Nguyễn An',
      email: 'an@example.com',
      website: '',
    })));
    expect(await screen.findByText(/mã yêu cầu #42/i)).toBeInTheDocument();
  });

  it('keeps an API failure visible and does not claim success', async () => {
    const user = userEvent.setup();
    publicApi.createContactRequest.mockRejectedValue(new Error('Không thể lưu yêu cầu'));
    renderPage(<ContactPage />);

    await user.type(screen.getByLabelText(/họ và tên/i), 'Nguyễn An');
    await user.type(screen.getByLabelText(/^email/i), 'an@example.com');
    await user.type(screen.getByLabelText(/nội dung/i), 'Tôi cần hỗ trợ kết nối dữ liệu thời tiết.');
    await user.click(screen.getByRole('button', { name: /gửi yêu cầu/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể lưu yêu cầu');
    expect(screen.queryByText(/mã yêu cầu/i)).not.toBeInTheDocument();
  });

  it('renders the 404 page with a working home destination', () => {
    renderPage(<NotFoundPage />);

    expect(screen.getByRole('heading', { name: /không tìm thấy trang/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Về trang chủ' })).toHaveAttribute('href', '/');
  });
});
