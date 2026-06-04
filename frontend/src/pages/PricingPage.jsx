import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
} from 'chart.js';
import { Minus, RefreshCw, Search, TrendingDown, TrendingUp } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Line } from 'react-chartjs-2';
import DataSourceBadge from '../components/DataSourceBadge';
import { EmptyState, InlineLoading, PageError } from '../components/StatusState';
import { getApiErrorMessage } from '../services/api';
import { pricingApi } from '../services/pricingApi';
import { CROP_SUGGESTIONS, REGION_SUGGESTIONS, buildPriceQuery, normalizePriceInput } from '../utils/priceInputs';
import { sourceNameLabel, translateUiText } from '../utils/vietnameseText';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const trendMeta = {
  up: {
    label: 'Tăng',
    icon: <TrendingUp className="h-5 w-5 text-green-600" />,
  },
  down: {
    label: 'Giảm',
    icon: <TrendingDown className="h-5 w-5 text-red-600" />,
  },
  increasing: {
    label: 'Tăng',
    icon: <TrendingUp className="h-5 w-5 text-green-600" />,
  },
  decreasing: {
    label: 'Giảm',
    icon: <TrendingDown className="h-5 w-5 text-red-600" />,
  },
  stable: {
    label: 'Ổn định',
    icon: <Minus className="h-5 w-5 text-gray-600" />,
  },
};

const QUALITY_LABELS = {
  grade_1: 'Loại 1',
  grade_2: 'Loại 2',
  grade_3: 'Loại 3',
  'Loai 1': 'Loại 1',
  'Loai 2': 'Loại 2',
  'Loai 3': 'Loại 3',
};

const formatCurrency = (value) => {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toLocaleString('vi-VN')} đ/kg`;
};

const hasItems = (value) => Array.isArray(value) && value.length > 0;
const toArray = (value) => (Array.isArray(value) ? value : []);
const unwrapData = (payload) => payload?.data ?? payload ?? null;
const hasRenderableData = (payload) => {
  const data = unwrapData(payload);
  if (!data || data._api_error) return false;
  if (Array.isArray(data)) return data.length > 0;
  return Object.keys(data).length > 0;
};

const initialSearch = {
  cropName: 'Cà phê',
  region: 'Đắk Lắk',
  days: 7,
  qualityGrade: 'grade_1',
};

const PricingPage = () => {
  const [search, setSearch] = useState(initialSearch);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [history, setHistory] = useState(null);
  const [engine, setEngine] = useState(null);
  const [error, setError] = useState(null);
  const [partialWarnings, setPartialWarnings] = useState([]);

  const normalizedSearch = useMemo(() => ({
    crop_name: normalizePriceInput(search.cropName),
    region: normalizePriceInput(search.region),
    quality_grade: search.qualityGrade,
    days: search.days,
  }), [search]);

  const canSearch = Boolean(normalizedSearch.crop_name && normalizedSearch.region);

  const loadPriceData = async ({ forceRefresh = false } = {}) => {
    if (!canSearch) {
      setError('Vui lòng nhập đủ nông sản và khu vực.');
      return;
    }

    if (forceRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    setPartialWarnings([]);

    try {
      const results = await Promise.allSettled([
        forceRefresh
          ? pricingApi.refreshCurrentPrice(buildPriceQuery({ cropName: normalizedSearch.crop_name, region: normalizedSearch.region, qualityGrade: normalizedSearch.quality_grade }))
          : pricingApi.getCurrentPrice({
              cropName: normalizedSearch.crop_name,
              region: normalizedSearch.region,
              qualityGrade: normalizedSearch.quality_grade,
            }),
        pricingApi.getPriceForecast(normalizedSearch.crop_name, normalizedSearch.region, normalizedSearch.days),
        pricingApi.getPriceHistory(normalizedSearch.crop_name, normalizedSearch.region, 30),
        pricingApi.getPricingEngine(
          normalizedSearch.crop_name,
          normalizedSearch.region,
          100,
          normalizedSearch.quality_grade,
          normalizedSearch.days
        ),
      ]);

      const currentResult = results[0];
      const forecastResult = results[1];
      const historyResult = results[2];
      const engineResult = results[3];

      const nextCurrent = currentResult.status === 'fulfilled' ? currentResult.value : null;
      const nextForecast = forecastResult.status === 'fulfilled' ? forecastResult.value : null;
      const nextHistory = historyResult.status === 'fulfilled' ? historyResult.value : null;
      const nextEngine = engineResult.status === 'fulfilled' ? engineResult.value : null;

      setCurrentPrice(nextCurrent);
      setForecast(nextForecast);
      setHistory(nextHistory);
      setEngine(nextEngine);

      const warnings = [];
      if (currentResult.status === 'rejected' || (nextCurrent && unwrapData(nextCurrent)?._api_error)) {
        warnings.push('Chưa tải được giá hiện tại.');
      }
      if (forecastResult.status === 'rejected' || (nextForecast && unwrapData(nextForecast)?._api_error)) {
        warnings.push('Chưa tải được dữ liệu dự báo giá.');
      }
      if (historyResult.status === 'rejected' || !hasRenderableData(nextHistory)) {
        warnings.push('Chưa tải được lịch sử giá.');
      }
      if (engineResult.status === 'rejected' || (nextEngine && unwrapData(nextEngine)?._api_error)) {
        warnings.push('Chưa tải được bộ phân tích giá AI.');
      }
      setPartialWarnings(warnings);

      const hasAnySuccessfulData = [nextCurrent, nextForecast, nextHistory, nextEngine].some(hasRenderableData);
      if (!hasAnySuccessfulData) {
        setError('Không thể tải dữ liệu giá. Vui lòng thử lại sau.');
      } else if (currentResult.status === 'rejected' && hasAnySuccessfulData) {
        setError(getApiErrorMessage(currentResult.reason, 'Không thể tải giá realtime hiện tại, nhưng vẫn hiển thị được dữ liệu còn lại.'));
      }
    } catch (err) {
      setCurrentPrice(null);
      setForecast(null);
      setHistory(null);
      setEngine(null);
      setPartialWarnings([]);
      setError(getApiErrorMessage(err, 'Không thể tải giá realtime.'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    await loadPriceData({ forceRefresh: false });
  };

  const handleRefresh = async () => {
    await loadPriceData({ forceRefresh: true });
  };

  const currentData = unwrapData(currentPrice);
  const forecastData = unwrapData(forecast);
  const historyData = unwrapData(history);
  const engineData = unwrapData(engine);

  const forecastRows = toArray(forecastData?.forecast_data);
  const historyRows = toArray(historyData?.history);
  const engineReasons = toArray(engineData?.reasons);

  const chartData = hasItems(forecastRows)
    ? {
        labels: forecastRows.map((item) =>
          new Date(item.date).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })
        ),
        datasets: [
          {
            label: 'Giá dự báo',
            data: forecastRows.map((item) => item.predicted_price ?? item.estimated_price ?? item.forecast_price),
            borderColor: 'rgb(22, 163, 74)',
            backgroundColor: 'rgba(22, 163, 74, 0.12)',
            fill: true,
            tension: 0.35,
          },
          {
            label: 'Cận trên',
            data: forecastRows.map((item) => item.confidence_upper ?? item.max_price),
            borderColor: 'rgba(22, 163, 74, 0.3)',
            borderDash: [5, 5],
            fill: false,
            pointRadius: 0,
          },
          {
            label: 'Cận dưới',
            data: forecastRows.map((item) => item.confidence_lower ?? item.min_price),
            borderColor: 'rgba(22, 163, 74, 0.3)',
            borderDash: [5, 5],
            fill: false,
            pointRadius: 0,
          },
        ],
      }
    : null;

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top' },
      title: { display: true, text: `Dự báo giá ${normalizedSearch.days} ngày tới` },
    },
    scales: {
      y: {
        beginAtZero: false,
        ticks: {
          callback: (value) => `${Number(value).toLocaleString('vi-VN')} đ`,
        },
      },
    },
  };

  const trendKey = currentData?.trend || currentData?.price_trend || forecastData?.trend || engineData?.trend;
  const trend = trendMeta[trendKey] || trendMeta.stable;
  const sourceNotice = currentData?._api_error
    ? 'Không thể tải dữ liệu thực tế hiện tại. Vui lòng thử lại sau.'
    : currentData?.is_mock
      ? 'Không thể tải dữ liệu thực tế hiện tại. Vui lòng thử lại sau.'
      : 'Dữ liệu giá lấy từ nguồn thực tế hoặc cơ sở dữ liệu nội bộ.';
  const hasAnyData = [currentPrice, forecast, history, engine].some(hasRenderableData);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-green-700">Dữ liệu giá</p>
        <h1 className="mt-2 text-3xl font-bold text-gray-900">Định giá nông sản</h1>
        <p className="mt-2 text-gray-600">Nhập tự do nông sản và khu vực, sau đó bấm nút để xem giá.</p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-[1fr_1fr_180px_180px]">
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">Nông sản</label>
            <input
              value={search.cropName}
              onChange={(event) => setSearch((current) => ({ ...current, cropName: event.target.value }))}
              placeholder="Nhập tên nông sản, ví dụ: Cà phê"
              list="crop-suggestions"
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            />
            <datalist id="crop-suggestions">
              {CROP_SUGGESTIONS.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">Khu vực</label>
            <input
              value={search.region}
              onChange={(event) => setSearch((current) => ({ ...current, region: event.target.value }))}
              placeholder="Nhập khu vực, ví dụ: Đắk Lắk"
              list="region-suggestions"
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            />
            <datalist id="region-suggestions">
              {REGION_SUGGESTIONS.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">Số ngày dự báo</label>
            <select
              value={search.days}
              onChange={(event) => setSearch((current) => ({ ...current, days: Number(event.target.value) }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            >
              <option value={7}>7 ngày</option>
              <option value={14}>14 ngày</option>
              <option value={30}>30 ngày</option>
            </select>
          </div>

          <div className="flex items-end gap-2">
            <button
              type="submit"
              disabled={loading || refreshing || !canSearch}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-green-700 px-4 py-2.5 font-semibold text-white hover:bg-green-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Search className="h-5 w-5" />
              {loading ? 'Đang tải...' : 'Xem giá'}
            </button>
          </div>

          <div className="md:col-span-2 xl:col-span-4">
            <button
              type="button"
              onClick={handleRefresh}
              disabled={loading || refreshing || !canSearch}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-700 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className="h-4 w-4" />
              {refreshing ? 'Đang làm mới...' : 'Làm mới từ nguồn thực tế'}
            </button>
          </div>
        </form>
      </section>

      {error && <PageError message={error} onRetry={() => loadPriceData({ forceRefresh: false })} />}
      {(loading || refreshing) && <InlineLoading text="Đang tải dữ liệu giá..." />}

      {!loading && !refreshing && !hasAnyData && !error && (
        <EmptyState
          title="Chưa có dữ liệu giá"
          description="Nhập nông sản, khu vực rồi bấm Xem giá để lấy dữ liệu từ hệ thống."
        />
      )}

      {hasItems(partialWarnings) && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 shadow-sm">
          <p className="font-semibold text-amber-900">Một phần dữ liệu chưa tải được</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {partialWarnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      )}

      {currentData && !currentData._api_error && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-700 shadow-sm">
          <DataSourceBadge source={currentData.source || currentData.source_type} />
          <span>Nguồn dữ liệu: {sourceNameLabel(currentData.source_name)}</span>
          <span>Loại nguồn: {currentData.source_type || currentData.source || 'database'}</span>
          {currentData.last_updated && <span>Cập nhật: {new Date(currentData.last_updated).toLocaleString('vi-VN')}</span>}
          <span>Độ tin cậy: {Math.round(Number(currentData.confidence_score ?? currentData.confidence ?? 0) * 100)}%</span>
          {currentData.is_mock && <span className="font-medium text-amber-700">{sourceNotice}</span>}
        </div>
      )}

      {currentData && !currentData._api_error && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Giá hiện tại</p>
            <p className="mt-2 text-3xl font-bold text-gray-900">{formatCurrency(currentData.current_price)}</p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Xu hướng</p>
            <div className="mt-2 flex items-center gap-2">
              {trend.icon}
              <span className="text-2xl font-bold text-gray-900">{trend.label}</span>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Phân loại</p>
            <p className="mt-2 text-2xl font-bold text-gray-900">{QUALITY_LABELS[currentData.quality_grade] || currentData.quality_grade || '—'}</p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Tham chiếu quốc tế</p>
            {currentData.global_reference ? (
              <>
                <p className="mt-2 text-2xl font-bold text-gray-900">
                  {Number(currentData.global_reference.price || 0).toLocaleString('vi-VN')} {currentData.global_reference.unit || 'USD/ton'}
                </p>
                <p className="mt-1 text-xs text-gray-500">{currentData.global_reference.source_name || 'Nguồn tham chiếu quốc tế'}</p>
              </>
            ) : (
              <p className="mt-2 text-sm text-gray-500">Chưa có tham chiếu quốc tế cho nông sản này.</p>
            )}
          </div>
        </div>
      )}

      {engineData && !engineData._api_error && (
        <section className="rounded-lg border border-violet-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Bộ phân tích giá AI</h2>
              <p className="text-sm text-gray-500">Kết hợp giá thị trường, dự báo, chất lượng và thời tiết.</p>
            </div>
            <DataSourceBadge source={engineData.source} />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded-lg bg-violet-50 p-4">
              <p className="text-sm text-violet-700">Giá AI đề xuất</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{formatCurrency(engineData.suggested_price || engineData.current_price)}</p>
            </div>
            <div className="rounded-lg bg-emerald-50 p-4">
              <p className="text-sm text-emerald-700">Dự báo 7 ngày</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{formatCurrency(engineData.forecast_price_7d)}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-700">Độ tin cậy</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{((engineData.confidence || 0) * 100).toFixed(0)}%</p>
            </div>
          </div>
          {hasItems(engineReasons) && (
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {engineReasons.map((reason) => (
                <div key={reason} className="rounded-lg border border-violet-100 bg-violet-50/60 p-3 text-sm text-violet-900">
                  {translateUiText(reason)}
                </div>
              ))}
            </div>
          )}
          {engineData.recommendation && (
            <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-blue-800">
              {translateUiText(engineData.recommendation)}
            </div>
          )}
        </section>
      )}

      {forecastData && !forecastData._api_error && chartData && (
        <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <div className="h-80 min-h-80">
            <Line data={chartData} options={chartOptions} />
          </div>

          {forecastData.recommendation && (
            <div className="mt-5 rounded-lg border border-blue-100 bg-blue-50 p-4">
              <p className="text-sm font-semibold text-blue-900">Khuyến nghị</p>
              <p className="mt-1 text-sm leading-6 text-blue-800">{translateUiText(forecastData.recommendation)}</p>
            </div>
          )}
        </section>
      )}

      {historyData && hasItems(historyRows) && (
        <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Lịch sử giá gần đây</h2>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {historyRows.slice(-6).map((item) => (
              <div key={item.date} className="rounded-lg border border-gray-200 p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm text-gray-500">{new Date(item.date).toLocaleDateString('vi-VN')}</p>
                  <DataSourceBadge source={item.source} compact />
                </div>
                <p className="mt-1 text-lg font-bold text-gray-900">{formatCurrency(item.avg_price)}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default PricingPage;
