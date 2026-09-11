import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getCurrentPrice = vi.fn();
const refreshCurrentPrice = vi.fn();
const getPriceForecast = vi.fn();
const getPriceHistory = vi.fn();
const getPricingEngine = vi.fn();

vi.mock('../../services/pricingApi', () => ({
  pricingApi: {
    getCurrentPrice: (...args) => getCurrentPrice(...args),
    refreshCurrentPrice: (...args) => refreshCurrentPrice(...args),
    getPriceForecast: (...args) => getPriceForecast(...args),
    getPriceHistory: (...args) => getPriceHistory(...args),
    getPricingEngine: (...args) => getPricingEngine(...args),
  },
}));

vi.mock('../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getApiErrorMessage: (error, fallback) => error?.message || fallback,
  settledValue: (result, fallback) => (result.status === 'fulfilled' ? result.value : fallback),
}));

import PricingPage from '../PricingPage';

const renderPricing = () =>
  render(
    <MemoryRouter>
      <PricingPage />
    </MemoryRouter>
  );

const search = async (user) => {
  await user.clear(screen.getByLabelText('Nông sản'));
  await user.type(screen.getByLabelText('Nông sản'), 'Cà phê');
  await user.clear(screen.getByLabelText('Khu vực'));
  await user.type(screen.getByLabelText('Khu vực'), 'Đắk Lắk');
  await user.click(screen.getByRole('button', { name: /Xem giá/i }));
};

describe('pricing page provenance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getPriceForecast.mockResolvedValue(null);
    getPriceHistory.mockResolvedValue(null);
    getPricingEngine.mockResolvedValue(null);
  });

  it('does not claim a database source or zero confidence when neither was reported', async () => {
    const user = userEvent.setup();
    getCurrentPrice.mockResolvedValue({
      crop_name: 'Cà phê',
      region: 'Đắk Lắk',
      current_price: 95000,
    });

    renderPricing();
    await search(user);

    const provenance = await screen.findByText(/Loại nguồn:/i);
    expect(provenance).toHaveTextContent(/chưa xác định/i);
    expect(provenance.parentElement).not.toHaveTextContent(/Độ tin cậy: 0%/);
    expect(provenance.parentElement).toHaveTextContent(/Độ tin cậy: —/);
  });

  it('shows the source and confidence the backend reported', async () => {
    const user = userEvent.setup();
    getCurrentPrice.mockResolvedValue({
      crop_name: 'Cà phê',
      region: 'Đắk Lắk',
      current_price: 95000,
      source: 'live',
      source_type: 'live',
      confidence_score: 0.91,
    });

    renderPricing();
    await search(user);

    const provenance = await screen.findByText(/Loại nguồn:/i);
    expect(provenance).toHaveTextContent(/live/i);
    expect(provenance.parentElement).toHaveTextContent(/Độ tin cậy: 91%/);
  });
});
