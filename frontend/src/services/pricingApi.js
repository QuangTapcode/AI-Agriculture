import api from './api';
import { unwrapApiResponse } from '../utils/apiResponse';
import { buildPriceQuery, normalizePriceInput } from '../utils/priceInputs';

const unwrap = (response) => unwrapApiResponse(response);

const request = async (factory) => unwrap(await factory());

const resolveQuery = (input, region, qualityGrade = 'grade_1', forceRefresh = false) => {
  if (typeof input === 'object' && input !== null) {
    return {
      crop_name: normalizePriceInput(input.cropName ?? input.crop_name),
      region: normalizePriceInput(input.region ?? region),
      quality_grade: input.qualityGrade ?? input.quality_grade ?? qualityGrade,
      force_refresh: Boolean(input.forceRefresh ?? input.force_refresh ?? forceRefresh),
    };
  }
  const query = buildPriceQuery({ cropName: input, region });
  return {
    ...query,
    quality_grade: qualityGrade,
    force_refresh: Boolean(forceRefresh),
  };
};

export const pricingApi = {
  getCurrentPrice: async (cropNameOrQuery, region, qualityGrade = 'grade_1', forceRefresh = false) => {
    const query = resolveQuery(cropNameOrQuery, region, qualityGrade, forceRefresh);
    const response = await api.get('/api/pricing/current', {
      params: query,
    });
    return unwrap(response);
  },

  refreshCurrentPrice: async (cropNameOrQuery, region, qualityGrade = 'grade_1', forceRefresh = false) => {
    const query = resolveQuery(cropNameOrQuery, region, qualityGrade, forceRefresh);
    const response = await api.post('/api/pricing/refresh', {
      crop_name: query.crop_name,
      region: query.region,
      quality_grade: query.quality_grade,
      force_refresh: query.force_refresh,
    });
    return unwrap(response);
  },

  getPriceForecast: async (cropName, region, days = 7) => {
    const response = await api.post('/api/pricing/forecast', {
      crop_name: normalizePriceInput(cropName),
      region: normalizePriceInput(region),
      days,
    });
    return unwrap(response);
  },

  getPriceHistory: async (cropName, region, days = 30) => {
    const response = await api.get(
      `/api/pricing/history/${encodeURIComponent(normalizePriceInput(cropName))}/${encodeURIComponent(normalizePriceInput(region))}`,
      { params: { days } }
    );
    return unwrap(response);
  },

  compareRegions: async (cropName, region) => {
    const response = await api.get(`/api/pricing/compare-regions/${encodeURIComponent(normalizePriceInput(cropName))}`, {
      params: region ? { region: normalizePriceInput(region) } : undefined,
    });
    return unwrap(response);
  },

  suggestPrice: async (cropName, region, quantity, qualityGrade = 'grade_1') => {
    const response = await api.post('/api/pricing/suggest', {
      crop_name: normalizePriceInput(cropName),
      region: normalizePriceInput(region),
      quantity,
      quality_grade: qualityGrade,
    });
    return unwrap(response);
  },

  getPricingEngine: async (cropName, region, quantity = 1, qualityGrade = 'grade_1', days = 7) => {
    const response = await api.post('/api/pricing/engine', {
      crop_name: normalizePriceInput(cropName),
      region: normalizePriceInput(region),
      quantity,
      quality_grade: qualityGrade,
      days,
    });
    return unwrap(response);
  },

  analyzeMarket: async (cropName, region, quantity, qualityGrade = 'grade_2') => {
    const response = await api.post('/api/market/analyze', {
      crop_name: normalizePriceInput(cropName),
      region: normalizePriceInput(region),
      quantity,
      quality_grade: qualityGrade,
    });
    return unwrap(response);
  },

  predictPrice: async (cropName, region, forecastDays = 7) => {
    const response = await api.post('/api/price-forecast/predict', {
      crop_name: normalizePriceInput(cropName),
      region: normalizePriceInput(region),
      forecast_days: forecastDays,
    });
    return unwrap(response);
  },
};

pricingApi.getCurrentPriceLegacy = pricingApi.getCurrentPrice;
pricingApi.refreshPrice = pricingApi.refreshCurrentPrice;
