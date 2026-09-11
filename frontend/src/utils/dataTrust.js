const FABRICATED_MARKERS = new Set(['mock', 'sample', 'demo']);
const CACHED_MARKERS = new Set(['cache', 'cached', 'hit', 'from_cache', 'fresh_cache', 'stale_cache', 'stale']);
const DATABASE_MARKERS = new Set(['database', 'db', 'from_db', 'market_db']);
const LIVE_MARKERS = new Set(['live', 'realtime', 'realtime_api', 'refreshed', 'open-meteo', 'rss']);

const lower = (value) => String(value || '').trim().toLowerCase();

export function normalizeDataMeta(payload = {}) {
  const nested = payload?.meta && typeof payload.meta === 'object' ? payload.meta : {};
  const source = lower(payload.source ?? nested.source);
  const cacheStatus = lower(payload.cache_status ?? nested.cache_status);
  const isMock = Boolean(payload.is_mock ?? nested.is_mock)
    || FABRICATED_MARKERS.has(source)
    || FABRICATED_MARKERS.has(cacheStatus);

  let status = 'database';
  if (isMock || cacheStatus === 'miss' || payload.success === false) {
    status = 'unavailable';
  } else if (Boolean(payload.is_realtime ?? nested.is_realtime) || LIVE_MARKERS.has(cacheStatus) || LIVE_MARKERS.has(source)) {
    status = 'live';
  } else if (Boolean(payload.is_cache ?? nested.is_cache) || CACHED_MARKERS.has(cacheStatus) || CACHED_MARKERS.has(source)) {
    status = 'cached';
  } else if (DATABASE_MARKERS.has(cacheStatus) || DATABASE_MARKERS.has(source) || !source) {
    status = 'database';
  }

  return {
    status,
    sourceName: payload.source_name ?? nested.source_name ?? payload.sourceName ?? '',
    sourceUrl: payload.source_url ?? nested.source_url ?? payload.sourceUrl ?? '',
    updatedAt: payload.updated_at ?? payload.last_updated ?? payload.fetched_at
      ?? nested.updated_at ?? nested.last_updated ?? nested.fetched_at ?? null,
    warning: payload.warning ?? nested.warning ?? payload.error?.message ?? null,
    isMock,
  };
}

export function getTrustedMetric(value, payload = {}) {
  const meta = normalizeDataMeta(payload);
  if (meta.isMock) {
    return {
      value: null,
      available: false,
      reason: 'Dữ liệu minh họa không được sử dụng.',
      meta: { ...meta, status: 'unavailable' },
    };
  }

  if (meta.status === 'unavailable' || value === null || value === undefined || value === '') {
    return {
      value: null,
      available: false,
      reason: meta.warning || 'Chưa có dữ liệu.',
      meta: { ...meta, status: 'unavailable' },
    };
  }

  return { value, available: true, reason: '', meta };
}

export function trustedValue(value, payload, formatter = (item) => String(item)) {
  const metric = getTrustedMetric(value, payload);
  return metric.available ? formatter(metric.value) : '—';
}
