import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const optimizeHarvest = vi.fn();

vi.mock('../../services/harvestApi', () => ({
  harvestApi: { optimizeHarvest: (...args) => optimizeHarvest(...args) },
}));

vi.mock('../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getApiErrorMessage: (error, fallback) => error?.message || fallback,
}));

import HarvestPage from '../HarvestPage';

const renderHarvest = () =>
  render(
    <MemoryRouter>
      <HarvestPage />
    </MemoryRouter>
  );

const submit = async (user) => {
  await user.type(screen.getByLabelText('Ngày xuống giống'), '2026-03-01');
  await user.click(screen.getByRole('button', { name: /Dự báo thu hoạch/i }));
};

describe('harvest forecast confidence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('never renders NaN when the forecast carries no confidence', async () => {
    const user = userEvent.setup();
    optimizeHarvest.mockResolvedValue({
      expected_harvest_date: '2026-07-01',
      planting_date: '2026-03-01',
    });

    renderHarvest();
    await submit(user);

    const confidence = await screen.findByTestId('harvest-confidence');
    expect(confidence).not.toHaveTextContent(/NaN/);
    expect(confidence).toHaveTextContent('—');
  });

  it('shows the confidence the backend reported', async () => {
    const user = userEvent.setup();
    optimizeHarvest.mockResolvedValue({
      expected_harvest_date: '2026-07-01',
      planting_date: '2026-03-01',
      confidence: 0.84,
    });

    renderHarvest();
    await submit(user);

    expect(await screen.findByTestId('harvest-confidence')).toHaveTextContent('84%');
  });
});
