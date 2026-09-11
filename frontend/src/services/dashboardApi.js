import api, { getApiErrorMessage, settledValue } from './api';
import { normalizeApiError, unwrapApiResponse } from '../utils/apiResponse';

const unwrap = (response) => unwrapApiResponse(response);
const request = async (factory, fallback) => {
  try {
    return unwrap(await factory());
  } catch (error) {
    throw normalizeApiError({ ...error, message: getApiErrorMessage(error, fallback) });
  }
};

export const dashboardApi = {
  getOverview: async (region, { cropName = 'lua' } = {}) => {
    return request(() => api.get('/api/dashboard/overview', {
      params: {
        region: region || undefined,
        crop_name: cropName,
      },
    }), 'Không tải được tổng quan dashboard');
  },

  getRealtimeStatus: async (region, { cropName = 'lua' } = {}) => {
    return request(() => api.get('/api/dashboard/realtime-status', {
      params: {
        region: region || undefined,
        crop_name: cropName,
      },
    }), 'Không tải được trạng thái realtime');
  },

  getAiInsights: async (region, { cropName = 'lua' } = {}) => {
    return request(() => api.get('/api/dashboard/ai-insights', {
      params: {
        region: region || undefined,
        crop_name: cropName,
      },
    }), 'Không tải được gợi ý AI');
  },

  getRiskSummary: async (region, { cropName = 'lua' } = {}) => {
    return request(() => api.get('/api/dashboard/risk-summary', {
      params: {
        region: region || undefined,
        crop_name: cropName,
      },
    }), 'Không tải được tổng quan rủi ro');
  },

  getActionToday: async (region, { cropName = 'lua' } = {}) => {
    return request(() => api.get('/api/dashboard/action-today', {
      params: {
        region: region || undefined,
        crop_name: cropName,
      },
    }), 'Không tải được hành động hôm nay');
  },

  getSummary: async (region, { cropName = 'lua', forceRefresh = false } = {}) => {
    return request(() => api.get('/api/dashboard/summary', {
      params: {
        region: region || undefined,
        crop_name: cropName,
        force_refresh: forceRefresh,
      },
    }), 'Không tải được dữ liệu dashboard');
  },

  getFeaturedCrop: async (region, { cropName = 'lua', forceRefresh = false } = {}) => {
    return request(() => api.get('/api/dashboard/featured-crop', {
      params: {
        region: region || undefined,
        crop_name: cropName,
        force_refresh: forceRefresh,
      },
    }), 'Không tải được giá nông sản nổi bật');
  },

  getPriceTrend: async ({ cropName = 'lua', region, days = 7 } = {}) => {
    return request(() => api.get('/api/dashboard/price-trend', {
      params: {
        crop_name: cropName,
        region: region || undefined,
        days,
      },
    }), 'Không tải được xu hướng giá');
  },

  getWeatherOverview: async (region, { forceRefresh = false } = {}) => {
    return request(() => api.get('/api/dashboard/weather-overview', {
      params: {
        region: region || undefined,
        force_refresh: forceRefresh,
      },
    }), 'Không tải được thời tiết realtime');
  },

  getWeatherRisk: async ({ region, cropName = 'lua', growthStage, forceRefresh = false } = {}) => {
    return request(() => api.get('/api/dashboard/weather-risk', {
      params: {
        region: region || undefined,
        crop_name: cropName,
        growth_stage: growthStage || undefined,
        force_refresh: forceRefresh,
      },
    }), 'Không tải được rủi ro thời tiết');
  },

  getRegionalPrices: async ({ cropName = 'lua', regions, forceRefresh = false } = {}) => {
    return request(() => api.get('/api/dashboard/regional-prices', {
      params: {
        crop_name: cropName,
        regions,
        force_refresh: forceRefresh,
      },
      paramsSerializer: {
        indexes: null,
      },
    }), 'Không tải được giá theo khu vực');
  },

  getRealtimeMarket: async ({ cropName = 'lua', region, forceRefresh = false } = {}) => {
    return request(() => api.get('/api/dashboard/realtime-market', {
      params: {
        crop_name: cropName,
        region: region || undefined,
        force_refresh: forceRefresh,
      },
    }), 'Không tải được dữ liệu thị trường realtime');
  },

  getNews: async ({ limit = 6, cropName, region, forceRefresh = false } = {}) => {
    return request(() => api.get('/api/dashboard/news', {
      params: {
        limit,
        crop_name: cropName || undefined,
        region: region || undefined,
        force_refresh: forceRefresh,
      },
    }), 'Không tải được tin tức dashboard');
  },

  getDataHealth: async ({ cropName = 'lua', region } = {}) => {
    return request(() => api.get('/api/dashboard/data-health', {
      params: {
        crop_name: cropName,
        region: region || undefined,
      },
    }), 'Không tải được trạng thái dữ liệu');
  },

  refresh: async ({ source = 'all', cropName = 'lua', region } = {}) => {
    return request(() => api.post('/api/dashboard/refresh', null, {
      params: {
        source,
        crop_name: cropName,
        region: region || undefined,
      },
    }), 'Không làm mới được dashboard');
  },

  reset: async ({ cropName = 'lua', region } = {}) => {
    return request(() => api.post('/api/dashboard/reset', null, {
      params: {
        crop_name: cropName,
        region: region || undefined,
      },
    }), 'Không reset được dashboard');
  },

  getAiRecommendation: async ({ cropName = 'lua', region } = {}) => {
    return request(() => api.get('/api/dashboard/ai-recommendation', {
      params: {
        crop_name: cropName,
        region: region || undefined,
      },
    }), 'Không tải được khuyến nghị AI');
  },
};

dashboardApi.getDashboardOverview = dashboardApi.getOverview;
dashboardApi.getDashboardRealtimeStatus = dashboardApi.getRealtimeStatus;
dashboardApi.getAIInsights = dashboardApi.getAiInsights;
dashboardApi.getDashboardAIInsights = dashboardApi.getAiInsights;
dashboardApi.getDashboardRiskSummary = dashboardApi.getRiskSummary;
dashboardApi.getDashboardActionToday = dashboardApi.getActionToday;

dashboardApi.getDashboardFullData = async (region, { cropName = 'lua' } = {}) => {
  const results = await Promise.allSettled([
    dashboardApi.getSummary(region, { cropName }),
    dashboardApi.getRealtimeStatus(region, { cropName }),
  ]);

  const summary = settledValue(results[0], null);
  const realtimeStatus = settledValue(results[1], null);

  let actionToday = null;
  if (summary) {
    const aiRec = summary.ai_recommendation || {};
    const actRecs = summary.weather_risk?.activity_recommendations || [];
    actionToday = {
      region: summary.region,
      crop_name: summary.crop_name,
      actions: [
        aiRec.description || aiRec.title,
        ...actRecs.slice(0, 3).map((r) => r.reason).filter(Boolean),
      ].filter(Boolean),
      priority: summary.weather_risk?.risk_level || 'medium',
      confidence: aiRec.confidence ?? null,
      is_mock: !!(aiRec.is_mock || summary.weather_risk?.is_mock),
      last_updated: aiRec.last_updated,
    };
  }

  const errors = results
    .map((result, index) => ({ result, key: ['overview', 'realtimeStatus'][index] }))
    .filter(({ result }) => result.status === 'rejected')
    .map(({ result, key }) => ({ key, message: getApiErrorMessage(result.reason, `Không tải được ${key}`) }));

  return {
    overview: summary,
    realtimeStatus,
    aiInsights: summary?.ai_recommendation || null,
    riskSummary: summary?.weather_risk
      ? {
          ...summary.weather_risk,
          confidence: summary.weather_risk.confidence ?? null,
          recommendations: summary.weather_risk.activity_recommendations || [],
        }
      : null,
    actionToday,
    errors,
  };
};
