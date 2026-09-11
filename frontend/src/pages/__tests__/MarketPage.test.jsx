import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const analyzeMarket = vi.fn();
const getChannels = vi.fn();
const getMarketNews = vi.fn();
const getStorePrices = vi.fn();
const getCurrentPrice = vi.fn();

vi.mock('../../services/marketApi', () => ({
  marketApi: {
    analyzeMarket: (...args) => analyzeMarket(...args),
    getChannels: (...args) => getChannels(...args),
    getMarketNews: (...args) => getMarketNews(...args),
    getStorePrices: (...args) => getStorePrices(...args),
  },
}));

vi.mock('../../services/pricingApi', () => ({
  pricingApi: { getCurrentPrice: (...args) => getCurrentPrice(...args) },
}));

vi.mock('../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getApiErrorMessage: (error, fallback) => error?.message || fallback,
  settledValue: (result, fallback) => (result.status === 'fulfilled' ? result.value : fallback),
}));

import MarketPage from '../MarketPage';

const renderMarket = () =>
  render(
    <MemoryRouter>
      <MarketPage />
    </MemoryRouter>
  );

const analyze = async (user) => {
  await user.clear(screen.getByLabelText('Nông sản'));
  await user.type(screen.getByLabelText('Nông sản'), 'Cà phê');
  await user.clear(screen.getByLabelText('Khu vực'));
  await user.type(screen.getByLabelText('Khu vực'), 'Đắk Lắk');
  await user.click(screen.getByRole('button', { name: /Phân tích thị trường/i }));
};

describe('market analysis real-data contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getChannels.mockResolvedValue([]);
    getMarketNews.mockResolvedValue({ articles: [] });
    getStorePrices.mockResolvedValue(null);
    getCurrentPrice.mockResolvedValue(null);
  });

  it('does not call the trend stable when no direction was reported', async () => {
    const user = userEvent.setup();
    analyzeMarket.mockResolvedValue({ crop_name: 'Cà phê', trend_30d: {} });

    renderMarket();
    await analyze(user);

    const trend = await screen.findByTestId('market-trend-30d');
    expect(trend).not.toHaveTextContent('Ổn định');
    expect(trend).toHaveTextContent('—');
  });

  it('does not report zero confidence when the analysis carried none', async () => {
    const user = userEvent.setup();
    analyzeMarket.mockResolvedValue({ crop_name: 'Cà phê' });

    renderMarket();
    await analyze(user);

    const confidence = await screen.findByTestId('market-confidence');
    expect(confidence).toHaveTextContent('—');
    expect(confidence).not.toHaveTextContent('0%');
  });

  it('shows the trend and confidence the backend reported', async () => {
    const user = userEvent.setup();
    analyzeMarket.mockResolvedValue({
      crop_name: 'Cà phê',
      confidence_score: 0.88,
      trend_30d: { direction: 'up', summary: 'Giá tăng đều.' },
    });

    renderMarket();
    await analyze(user);

    expect(await screen.findByTestId('market-trend-30d')).toHaveTextContent('Tăng');
    expect(screen.getByTestId('market-confidence')).toHaveTextContent('88%');
  });

  it('leaves a regional row blank rather than printing 0 đ/kg', async () => {
    const user = userEvent.setup();
    analyzeMarket.mockResolvedValue({
      crop_name: 'Cà phê',
      regional_comparison: [{ region: 'Đắk Lắk' }],
    });

    renderMarket();
    await analyze(user);

    const row = await screen.findByTestId('regional-row-Đắk Lắk');
    expect(within(row).getByTestId('regional-price')).toHaveTextContent('—');
    expect(within(row).getByTestId('regional-price')).not.toHaveTextContent('0 đ/kg');
    expect(within(row).getByTestId('regional-difference')).toHaveTextContent('—');
  });
});
