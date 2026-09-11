import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getDashboardFullData = vi.fn();
const getCurrentWeather = vi.fn();
const getSeasonSummary = vi.fn();
const getFeaturedCrop = vi.fn();
const getPriceTrend = vi.fn();

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { name: 'Nông hộ thử nghiệm', region: 'Dak Lak' },
  }),
}));

vi.mock('../../services/dashboardApi', () => ({
  dashboardApi: {
    getDashboardFullData: (...args) => getDashboardFullData(...args),
    getFeaturedCrop: (...args) => getFeaturedCrop(...args),
    getPriceTrend: (...args) => getPriceTrend(...args),
  },
}));

vi.mock('../../services/weatherApi', () => ({
  weatherApi: { getCurrentWeather: (...args) => getCurrentWeather(...args) },
}));

vi.mock('../../services/seasonApi', () => ({
  seasonApi: { getSeasonSummary: (...args) => getSeasonSummary(...args) },
}));

import Dashboard from '../Dashboard';

const renderDashboard = () =>
  render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );

/** A successful response that simply carries no numbers yet. */
const emptyButHealthyResponse = {
  overview: { region: 'Dak Lak', crop_name: 'lua' },
  realtimeStatus: null,
  aiInsights: null,
  riskSummary: null,
  actionToday: null,
  errors: [],
};

describe('dashboard real-data contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getDashboardFullData.mockResolvedValue(emptyButHealthyResponse);
    getCurrentWeather.mockResolvedValue(null);
    getSeasonSummary.mockResolvedValue(null);
    getFeaturedCrop.mockResolvedValue(null);
    getPriceTrend.mockResolvedValue(null);
  });

  it('shows an em dash instead of zero when the season count is unknown', async () => {
    renderDashboard();

    const seasonPanel = await screen.findByTestId('metric-active-seasons');
    expect(within(seasonPanel).getByTestId('metric-value')).toHaveTextContent('—');
    expect(within(seasonPanel).getByTestId('metric-value')).not.toHaveTextContent('0');
  });
});

describe('dashboard AI confidence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getDashboardFullData.mockResolvedValue(emptyButHealthyResponse);
    getCurrentWeather.mockResolvedValue(null);
    getSeasonSummary.mockResolvedValue(null);
    getFeaturedCrop.mockResolvedValue(null);
    getPriceTrend.mockResolvedValue(null);
  });

  it('does not report zero confidence when the model returned none', async () => {
    getDashboardFullData.mockResolvedValue({
      ...emptyButHealthyResponse,
      aiInsights: { title: 'Theo dõi giá', description: 'Giá đang đi ngang.' },
    });

    renderDashboard();

    const confidence = await screen.findByTestId('ai-confidence');
    expect(confidence).toHaveTextContent('—');
    expect(confidence).not.toHaveTextContent('0%');
  });

  it('labels a forecast row as unknown confidence rather than assuming medium', async () => {
    getDashboardFullData.mockResolvedValue({
      ...emptyButHealthyResponse,
      overview: {
        ...emptyButHealthyResponse.overview,
        forecast: [{ date: '2026-09-20', forecast_price: 8200, trend: 'up' }],
      },
    });

    renderDashboard();

    const row = await screen.findByTestId('forecast-row-2026-09-20');
    expect(row).not.toHaveTextContent('Tin cậy trung bình');
    expect(row).toHaveTextContent(/Chưa có độ tin cậy/i);
  });
});

describe('dashboard risk badge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getDashboardFullData.mockResolvedValue(emptyButHealthyResponse);
    getCurrentWeather.mockResolvedValue(null);
    getSeasonSummary.mockResolvedValue(null);
    getFeaturedCrop.mockResolvedValue(null);
    getPriceTrend.mockResolvedValue(null);
  });

  it('never claims low risk when no risk level was returned', async () => {
    renderDashboard();

    await screen.findByTestId('metric-active-seasons');
    expect(screen.queryByText(/Rủi ro Thấp/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(/Chưa rõ rủi ro/i).length).toBeGreaterThan(0);
  });

  it('shows the risk level the backend reported', async () => {
    getDashboardFullData.mockResolvedValue({
      ...emptyButHealthyResponse,
      riskSummary: { risk_level: 'high', risk_score: 72 },
    });

    renderDashboard();

    expect(await screen.findAllByText(/Rủi ro Cao/i)).not.toHaveLength(0);
  });
});

describe('dashboard alert count', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentWeather.mockResolvedValue(null);
    getSeasonSummary.mockResolvedValue(null);
    getFeaturedCrop.mockResolvedValue(null);
    getPriceTrend.mockResolvedValue(null);
  });

  it('does not claim zero alerts when the alert centre was not returned', async () => {
    getDashboardFullData.mockResolvedValue(emptyButHealthyResponse);

    renderDashboard();

    await screen.findByTestId('metric-active-seasons');
    expect(screen.queryByText(/0 cảnh báo/i)).not.toBeInTheDocument();
  });

  it('reports a genuine empty alert list as zero', async () => {
    getDashboardFullData.mockResolvedValue({
      ...emptyButHealthyResponse,
      overview: { ...emptyButHealthyResponse.overview, alert_center: [] },
    });

    renderDashboard();

    expect(await screen.findByText(/0 cảnh báo/i)).toBeInTheDocument();
  });
});
