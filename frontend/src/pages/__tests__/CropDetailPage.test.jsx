import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getCropDetail = vi.fn();
const getCurrentPrice = vi.fn();
const getPriceHistory = vi.fn();
const getPriceForecast = vi.fn();
const compareRegions = vi.fn();

vi.mock('../../services/cropsApi', () => ({
  cropsApi: { getCropDetail: (...args) => getCropDetail(...args) },
}));

vi.mock('../../services/pricingApi', () => ({
  pricingApi: {
    getCurrentPrice: (...args) => getCurrentPrice(...args),
    getPriceHistory: (...args) => getPriceHistory(...args),
    getPriceForecast: (...args) => getPriceForecast(...args),
    compareRegions: (...args) => compareRegions(...args),
  },
}));

vi.mock('react-chartjs-2', () => ({
  Bar: () => <div data-testid="chart-bar" />,
  Line: () => <div data-testid="chart-line" />,
}));

import CropDetailPage from '../CropDetailPage';

const renderCrop = () =>
  render(
    <MemoryRouter initialEntries={['/crop/ca-phe']}>
      <Routes>
        <Route path="/crop/:cropId" element={<CropDetailPage />} />
      </Routes>
    </MemoryRouter>
  );

const CROP = {
  crop_name: 'Cà phê',
  typical_price_min: 80000,
  typical_price_max: 120000,
};

describe('crop detail real-data contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCropDetail.mockResolvedValue(CROP);
    getCurrentPrice.mockResolvedValue(null);
    getPriceHistory.mockResolvedValue(null);
    getPriceForecast.mockResolvedValue(null);
    compareRegions.mockResolvedValue(null);
  });

  it('does not invent a regional price table from the crop price range', async () => {
    renderCrop();

    const regions = await screen.findByTestId('region-comparison');
    // 120.000 là typical_price_max, 80.000 là typical_price_min — không phải giá vùng.
    expect(regions).not.toHaveTextContent('120.000');
    expect(regions).not.toHaveTextContent('80.000');
    expect(regions).toHaveTextContent(/Chưa có dữ liệu so sánh theo vùng/i);
  });

  it('shows the regional prices the backend really returned', async () => {
    compareRegions.mockResolvedValue({
      regions: [
        { region: 'Dak Lak', price: 95000 },
        { region: 'Lam Dong', price: 93500 },
      ],
    });

    renderCrop();

    const regions = await screen.findByTestId('region-comparison');
    expect(regions).toHaveTextContent('95.000');
    expect(regions).toHaveTextContent('93.500');
  });

  it('does not present the typical minimum as the current market price', async () => {
    renderCrop();

    const price = await screen.findByTestId('crop-current-price');
    expect(price).toHaveTextContent('—');
    expect(price).not.toHaveTextContent('80.000');
  });

  it('does not claim a flat +0.0% move when no change was reported', async () => {
    renderCrop();

    const change = await screen.findByTestId('crop-price-change');
    expect(change).not.toHaveTextContent('+0.0%');
    expect(change).toHaveTextContent('—');
  });

  it('does not stamp "updated today" over an unknown harvest season', async () => {
    renderCrop();

    await screen.findByTestId('crop-current-price');
    expect(screen.queryByText(/CẬP NHẬT HÔM NAY/i)).not.toBeInTheDocument();
  });
});
