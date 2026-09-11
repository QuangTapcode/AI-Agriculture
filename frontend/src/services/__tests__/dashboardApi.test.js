import { beforeEach, describe, expect, it, vi } from 'vitest';

const get = vi.fn();

vi.mock('../api', () => ({
  default: { get: (...args) => get(...args) },
  getApiErrorMessage: (error, fallback) => error?.message || fallback,
  settledValue: (result, fallback) => (result.status === 'fulfilled' ? result.value : fallback),
}));

import { dashboardApi } from '../dashboardApi';

describe('dashboard aggregate does not invent confidence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('leaves confidence absent when the backend supplied none', async () => {
    get.mockResolvedValue({
      status: 200,
      data: {
        success: true,
        region: 'Dak Lak',
        ai_recommendation: { title: 'Theo dõi giá', description: 'Giá đi ngang.' },
        weather_risk: { risk_level: 'low' },
      },
    });

    const result = await dashboardApi.getDashboardFullData('Dak Lak');

    expect(result.actionToday?.confidence ?? null).toBeNull();
    expect(result.riskSummary?.confidence ?? null).toBeNull();
  });

  it('passes through the confidence the backend actually reported', async () => {
    get.mockResolvedValue({
      status: 200,
      data: {
        success: true,
        region: 'Dak Lak',
        ai_recommendation: { title: 'Theo dõi giá', confidence: 0.91 },
        weather_risk: { risk_level: 'low', confidence: 0.88 },
      },
    });

    const result = await dashboardApi.getDashboardFullData('Dak Lak');

    expect(result.actionToday.confidence).toBe(0.91);
    expect(result.riskSummary.confidence).toBe(0.88);
  });
});
