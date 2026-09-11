import { describe, expect, it } from 'vitest';

import { getTrustedMetric, normalizeDataMeta } from '../dataTrust';

describe('data trust contract', () => {
  it('keeps an exact real value and its provenance', () => {
    const metric = getTrustedMetric(1, {
      source: 'database',
      source_name: 'Users DB',
      updated_at: '2026-09-12T08:00:00Z',
    });

    expect(metric).toMatchObject({
      value: 1,
      available: true,
      meta: {
        status: 'database',
        sourceName: 'Users DB',
        isMock: false,
      },
    });
  });

  it.each([
    { is_mock: true, source: 'database' },
    { source: 'mock' },
    { source: 'sample' },
    { cache_status: 'demo' },
  ])('blocks fabricated metadata %#', (metadata) => {
    expect(getTrustedMetric(100, metadata)).toMatchObject({
      value: null,
      available: false,
      reason: 'Dữ liệu minh họa không được sử dụng.',
      meta: { status: 'unavailable', isMock: true },
    });
  });

  it('does not turn a missing value into zero', () => {
    expect(getTrustedMetric(null, { source: 'database' })).toMatchObject({
      value: null,
      available: false,
      reason: 'Chưa có dữ liệu.',
    });
  });

  it('maps live, cached and unavailable source states consistently', () => {
    expect(normalizeDataMeta({ is_realtime: true }).status).toBe('live');
    expect(normalizeDataMeta({ cache_status: 'stale_cache' }).status).toBe('cached');
    expect(normalizeDataMeta({ cache_status: 'miss' }).status).toBe('unavailable');
  });
});
