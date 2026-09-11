import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getOptions = vi.fn();

vi.mock('../../../services/alertApi', () => ({
  alertApi: {
    getOptions: (...a) => getOptions(...a),
    subscribe: vi.fn(),
    getSuggestions: vi.fn(),
    getWeatherAlerts: vi.fn(),
  },
}));

vi.mock('../../../services/pricingApi', () => ({
  pricingApi: { getCurrentPrice: vi.fn().mockResolvedValue(null) },
}));

vi.mock('../../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getApiErrorMessage: (error, fallback) => error?.message || fallback,
}));

import AlertSubscribe from '../AlertSubscribe';

describe('alert subscription form resilience', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('survives an options response that omits crops and regions', async () => {
    getOptions.mockResolvedValue({ default_region: 'Dak Lak' });

    render(<AlertSubscribe />);

    // Trước đây options.crops thành undefined và .find() làm sập cả trang.
    expect(await screen.findByRole('heading', { level: 2 })).toBeInTheDocument();
  });

  it('still lists the crops the backend did return', async () => {
    getOptions.mockResolvedValue({
      crops: [{ crop_id: 1, crop_name: 'Cà phê' }],
      regions: [{ region_key: 'dak-lak', display_name: 'Đắk Lắk' }],
      channels: [{ value: 'email', label: 'Email' }],
      rule_types: [],
    });

    render(<AlertSubscribe />);

    expect(await screen.findByRole('option', { name: /Cà phê/i })).toBeInTheDocument();
  });
});
