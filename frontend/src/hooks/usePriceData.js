import { useEffect, useState } from 'react';
import { getApiErrorMessage } from '../services/api';
import { pricingApi } from '../services/pricingApi';

export const usePriceData = (cropName, region, autoFetch = false) => {
  const [pendingRequests, setPendingRequests] = useState(0);
  const [error, setError] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [history, setHistory] = useState(null);
  const loading = pendingRequests > 0;

  const fetchCurrentPrice = async () => {
    setPendingRequests((count) => count + 1);
    setError(null);

    try {
      const data = await pricingApi.getCurrentPrice(cropName, region);
      setCurrentPrice(data);
      return data;
    } catch (err) {
      setError(getApiErrorMessage(err, 'Lỗi khi tải giá hiện tại'));
      throw err;
    } finally {
      setPendingRequests((count) => count - 1);
    }
  };

  const fetchForecast = async (days = 7) => {
    setPendingRequests((count) => count + 1);
    setError(null);

    try {
      const data = await pricingApi.getPriceForecast(cropName, region, days);
      setForecast(data);
      return data;
    } catch (err) {
      setError(getApiErrorMessage(err, 'Lỗi khi tải dự báo giá'));
      throw err;
    } finally {
      setPendingRequests((count) => count - 1);
    }
  };

  const fetchHistory = async (days = 30) => {
    setPendingRequests((count) => count + 1);
    setError(null);

    try {
      const data = await pricingApi.getPriceHistory(cropName, region, days);
      setHistory(data);
      return data;
    } catch (err) {
      setError(getApiErrorMessage(err, 'Lỗi khi tải lịch sử giá'));
      throw err;
    } finally {
      setPendingRequests((count) => count - 1);
    }
  };

  useEffect(() => {
    if (autoFetch && cropName && region) {
      Promise.all([fetchCurrentPrice(), fetchForecast(), fetchHistory()]).catch(() => {});
    }
  }, [cropName, region, autoFetch]);

  return {
    loading,
    error,
    currentPrice,
    forecast,
    history,
    fetchCurrentPrice,
    fetchForecast,
    fetchHistory,
  };
};
