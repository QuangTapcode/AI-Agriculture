import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getSummary = vi.fn();

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { id: 1, name: 'Nông hộ thử nghiệm', region: 'Dak Lak' },
  }),
}));

vi.mock('../../services/reportsApi', () => ({
  reportsApi: { getSummary: (...args) => getSummary(...args) },
}));

vi.mock('../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getApiErrorMessage: (error, fallback) => error?.message || fallback,
}));

import ReportsPage from '../ReportsPage';

const renderReports = () =>
  render(
    <MemoryRouter>
      <ReportsPage />
    </MemoryRouter>
  );

describe('reports real-data contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not report zero revenue or yield when the account has no records yet', async () => {
    getSummary.mockResolvedValue({ region: 'Dak Lak' });

    renderReports();

    const revenue = await screen.findByTestId('report-total-revenue');
    expect(revenue).toHaveTextContent('—');
    expect(revenue).not.toHaveTextContent('0 đ');

    const quantity = screen.getByTestId('report-total-quantity');
    expect(quantity).toHaveTextContent('—');
    expect(quantity).not.toHaveTextContent('0 kg');
  });

  it('shows the totals the backend actually reported', async () => {
    getSummary.mockResolvedValue({
      region: 'Dak Lak',
      total_revenue: 12500000,
      total_quantity: 4200,
      market: [{ id: 1 }],
      harvest: [{ id: 1 }],
      quality: [],
    });

    renderReports();

    expect(await screen.findByTestId('report-total-revenue')).toHaveTextContent('12.500.000');
    expect(screen.getByTestId('report-total-quantity')).toHaveTextContent('4.200');
  });

  it('surfaces a failed request instead of rendering an empty report', async () => {
    getSummary.mockRejectedValue(new Error('Không thể tải báo cáo của tài khoản'));

    renderReports();

    expect(await screen.findByText(/Không thể tải báo cáo/i)).toBeInTheDocument();
  });
});
