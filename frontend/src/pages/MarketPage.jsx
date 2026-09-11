import { Globe, RefreshCw, Search, ShoppingCart, Store, TrendingUp, AlertTriangle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { MISSING, formatConfidence, hasValue } from '../utils/format';
import DataSourceBadge from '../components/DataSourceBadge';
import { getApiErrorMessage } from '../services/api';
import { marketApi } from '../services/marketApi';
import { marketNewsApi } from '../services/marketNewsApi';
import { pricingApi } from '../services/pricingApi';
import { CROP_SUGGESTIONS, REGION_SUGGESTIONS, normalizePriceInput } from '../utils/priceInputs';
import { translateUiText } from '../utils/vietnameseText';

const fallbackChannels = [
  { id: 'wholesale', name: 'Chợ đầu mối', commission: '5-10%' },
  { id: 'retail', name: 'Chợ bán lẻ', commission: '0%' },
  { id: 'supermarket', name: 'Siêu thị/cửa hàng sạch', commission: '10-15%' },
];

const channelIcons = [ShoppingCart, TrendingUp, Globe];

const initialFormData = {
  cropName: 'Cà phê',
  region: 'Đắk Lắk',
  quantity: 1000,
  qualityGrade: 'grade_1',
};

const formatMoney = (value) =>
  hasValue(value) ? `${Number(value).toLocaleString('vi-VN')} đ/kg` : MISSING;

/** Chỉ gọi tên xu hướng khi backend thật sự trả direction. */
const TREND_LABELS = { up: 'Tăng', down: 'Giảm', stable: 'Ổn định', flat: 'Ổn định' };
const trendLabel = (direction) => TREND_LABELS[String(direction || '').toLowerCase()] || MISSING;

const MarketPage = () => {
  const [channels, setChannels] = useState([]);
  const [channelSource, setChannelSource] = useState({ is_mock: false, source: 'database' });
  const [formData, setFormData] = useState(initialFormData);
  const [analysis, setAnalysis] = useState(null);
  const [marketPrice, setMarketPrice] = useState(null);
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshingPrice, setRefreshingPrice] = useState(false);
  const [error, setError] = useState(null);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState(null);
  const [storePrices, setStorePrices] = useState(null);
  const [storePricesLoading, setStorePricesLoading] = useState(false);

  const normalizedInputs = useMemo(
    () => ({
      cropName: normalizePriceInput(formData.cropName),
      region: normalizePriceInput(formData.region),
      quantity: Number(formData.quantity || 0),
      qualityGrade: formData.qualityGrade || 'grade_1',
    }),
    [formData]
  );

  const canAnalyze = Boolean(normalizedInputs.cropName && normalizedInputs.region && normalizedInputs.quantity > 0);

  useEffect(() => {
    const loadChannels = async () => {
      try {
        const data = await marketApi.getChannels();
        if (data.channels?.length) {
          setChannels(data.channels);
          setChannelSource(data);
        }
      } catch (err) {
        setChannels([]);
        setChannelSource({
          is_mock: false,
          source: 'realtime_api',
          error: getApiErrorMessage(err, 'Không thể tải kênh bán hàng.'),
        });
      }
    };
    loadChannels();
  }, []);

  const loadMarketSnapshot = async () => {
    if (!canAnalyze) {
      setError('Vui lòng nhập đủ nông sản, khu vực và sản lượng.');
      return;
    }

    setLoading(true);
    setError(null);
    setNewsError(null);

    try {
      // Tải phân tích và giá song song — không bao gồm news để tránh block khi news chậm
      const [analysisResult, priceResult] = await Promise.allSettled([
        marketApi.analyzeMarket({
          cropName: normalizedInputs.cropName,
          region: normalizedInputs.region,
          quantity: normalizedInputs.quantity,
          qualityGrade: normalizedInputs.qualityGrade,
        }),
        pricingApi.getCurrentPrice({
          cropName: normalizedInputs.cropName,
          region: normalizedInputs.region,
          qualityGrade: normalizedInputs.qualityGrade,
        }),
      ]);

      if (analysisResult.status === 'fulfilled') {
        setAnalysis(analysisResult.value);
      } else {
        setError(getApiErrorMessage(analysisResult.reason, 'Không thể phân tích thị trường.'));
      }
      if (priceResult.status === 'fulfilled') {
        setMarketPrice(priceResult.value);
      }

      // Tải news riêng — lỗi ở đây không ảnh hưởng phần phân tích
      setNewsLoading(true);
      marketApi.getMarketNews({
        limit: 4,
        crop: normalizedInputs.cropName,
        region: normalizedInputs.region,
      }).then((newsData) => {
        setNews(newsData?.news || []);
        if (!newsData?.news?.length && newsData?.warning) {
          setNewsError(newsData.warning);
        }
      }).catch((err) => {
        setNewsError(getApiErrorMessage(err, 'Không thể tải tin tức thị trường.'));
      }).finally(() => setNewsLoading(false));

      // Fetch giá chuỗi cửa hàng song song sau khi có dữ liệu phân tích
      setStorePrices(null);
      setStorePricesLoading(true);
      marketApi.getStorePrices({
        cropName: normalizedInputs.cropName,
        region: normalizedInputs.region,
      }).then((d) => setStorePrices(d)).catch(() => setStorePrices({ stores: [], error: 'Không tải được giá chuỗi cửa hàng.' })).finally(() => setStorePricesLoading(false));
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể phân tích thị trường.'));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    await loadMarketSnapshot();
  };

  const handleRefreshPrice = async () => {
    if (!canAnalyze) {
      setError('Vui lòng nhập đủ nông sản, khu vực và sản lượng.');
      return;
    }
    setRefreshingPrice(true);
    setError(null);

    try {
      const refreshed = await pricingApi.refreshCurrentPrice({
        cropName: normalizedInputs.cropName,
        region: normalizedInputs.region,
        qualityGrade: normalizedInputs.qualityGrade,
      });
      setMarketPrice(refreshed);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể tải giá realtime.'));
    } finally {
      setRefreshingPrice(false);
    }
  };

  const currentTrend = analysis?.trend_7d || {};
  const longTrend = analysis?.trend_30d || {};
  const volatility = analysis?.volatility || {};
  const regionalComparison = analysis?.regional_comparison || [];
  const recommendation = analysis?.recommendation || {};
  const dataSources = analysis?.data_sources || [];

  return (
    <div className="space-y-6 px-4 py-6">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-bold text-gray-900">Phân tích thị trường</h1>
          <DataSourceBadge data={channelSource} />
        </div>
        <p className="mt-2 text-gray-600">
          Nhập nông sản, khu vực rồi bấm nút để xem giá hiện tại, xu hướng 7 ngày, xu hướng 30 ngày và khuyến nghị.
        </p>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {newsError && <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{newsError}</div>}

      <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-[1fr_1fr_180px_180px]">
          <div>
            <label htmlFor="market-crop" className="mb-2 block text-sm font-medium text-gray-700">
              Nông sản
            </label>
            <input
              id="market-crop"
              value={formData.cropName}
              onChange={(event) => setFormData({ ...formData, cropName: event.target.value })}
              placeholder="Nhập tên nông sản, ví dụ: Cà phê"
              list="market-crop-suggestions"
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            />
            <datalist id="market-crop-suggestions">
              {CROP_SUGGESTIONS.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </div>

          <div>
            <label htmlFor="market-region" className="mb-2 block text-sm font-medium text-gray-700">
              Khu vực
            </label>
            <input
              id="market-region"
              value={formData.region}
              onChange={(event) => setFormData({ ...formData, region: event.target.value })}
              placeholder="Nhập khu vực, ví dụ: Đắk Lắk"
              list="market-region-suggestions"
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            />
            <datalist id="market-region-suggestions">
              {REGION_SUGGESTIONS.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </div>

          <div>
            <label htmlFor="market-quantity" className="mb-2 block text-sm font-medium text-gray-700">
              Số lượng (kg)
            </label>
            <input
              id="market-quantity"
              type="number"
              min="1"
              value={formData.quantity}
              onChange={(event) => setFormData({ ...formData, quantity: event.target.value })}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
              required
            />
          </div>

          <div>
            <label htmlFor="market-quality" className="mb-2 block text-sm font-medium text-gray-700">
              Chất lượng
            </label>
            <select
              id="market-quality"
              value={formData.qualityGrade}
              onChange={(event) => setFormData({ ...formData, qualityGrade: event.target.value })}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            >
              <option value="grade_1">Loại 1</option>
              <option value="grade_2">Loại 2</option>
              <option value="grade_3">Loại 3</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading || !canAnalyze}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-green-700 px-4 py-2.5 font-semibold text-white hover:bg-green-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Search className="h-5 w-5" />
              {loading ? 'Đang phân tích...' : 'Phân tích thị trường'}
            </button>
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleRefreshPrice}
              disabled={refreshingPrice || !canAnalyze}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-700 bg-emerald-50 px-4 py-2.5 font-semibold text-emerald-800 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className="h-5 w-5" />
              {refreshingPrice ? 'Đang làm mới...' : 'Làm mới giá'}
            </button>
          </div>
        </form>
      </section>

      {(loading || newsLoading) && <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">Đang tải dữ liệu thị trường...</div>}

      {analysis && (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Giá hiện tại</p>
            <p className="mt-2 text-3xl font-bold text-gray-900">{formatMoney(analysis.current_price)}</p>
            <p className="mt-2 text-xs text-gray-500">{analysis.region}</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Xu hướng 7 ngày</p>
            <p className="mt-2 text-2xl font-bold text-gray-900">{currentTrend.direction === 'up' ? 'Tăng' : currentTrend.direction === 'down' ? 'Giảm' : 'Ổn định'}</p>
            <p className="mt-2 text-sm text-gray-600">{currentTrend.summary}</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Xu hướng 30 ngày</p>
            <p data-testid="market-trend-30d" className="mt-2 text-2xl font-bold text-gray-900">
              {trendLabel(longTrend.direction)}
            </p>
            <p className="mt-2 text-sm text-gray-600">{longTrend.summary}</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Độ tin cậy</p>
            <p data-testid="market-confidence" className="mt-2 text-2xl font-bold text-gray-900">
              {formatConfidence(analysis.confidence_score)}
            </p>
            <p className="mt-2 text-sm text-gray-600">{volatility.summary}</p>
          </div>
        </section>
      )}

      {analysis && (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Giá nội địa</p>
            <p className="mt-2 text-2xl font-bold text-gray-900">
              {formatMoney(analysis.local_price?.price ?? analysis.current_price)}
            </p>
            <p className="mt-1 text-xs text-gray-500">{analysis.local_price?.source_name || analysis.source_name || 'MarketPrices DB'}</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Giá quốc tế tham chiếu</p>
            {analysis.global_reference ? (
              <>
                <p className="mt-2 text-2xl font-bold text-gray-900">
                  {Number(analysis.global_reference.price || 0).toLocaleString('vi-VN')} {analysis.global_reference.unit || 'USD/ton'}
                </p>
                <p className="mt-1 text-xs text-gray-500">{analysis.global_reference.source_name || 'Nguồn tham chiếu quốc tế'}</p>
              </>
            ) : (
              <p className="mt-2 text-sm text-gray-500">Chưa có dữ liệu tham chiếu quốc tế.</p>
            )}
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-gray-600">Tin tức tác động</p>
            <p className="mt-2 text-xl font-bold text-gray-900">{translateUiText(analysis.news_impact?.level || 'neutral')}</p>
            <p className="mt-2 text-sm text-gray-600">{translateUiText(analysis.news_impact?.summary || 'Chưa có tin tác động phù hợp.')}</p>
          </div>
        </section>
      )}

      {marketPrice && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-700 shadow-sm">
          <DataSourceBadge data={marketPrice} />
          <span>Nguồn dữ liệu: {marketPrice.source_name || marketPrice.source || 'Database'}</span>
          <span>Loại nguồn: {marketPrice.source_type || marketPrice.source || 'database'}</span>
          {marketPrice.last_updated && <span>Cập nhật: {new Date(marketPrice.last_updated).toLocaleString('vi-VN')}</span>}
          {marketPrice._api_error ? (
            <span className="font-medium text-amber-700">Không thể tải dữ liệu thực tế hiện tại. Vui lòng thử lại sau.</span>
          ) : marketPrice.is_mock ? (
            <span className="font-medium text-amber-700">Không thể tải dữ liệu thực tế hiện tại. Vui lòng thử lại sau.</span>
          ) : null}
          <button
            type="button"
            onClick={handleRefreshPrice}
            disabled={refreshingPrice || !canAnalyze}
            className="ml-auto inline-flex items-center gap-2 rounded-lg border border-emerald-700 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw className="h-4 w-4" />
            {refreshingPrice ? 'Đang làm mới...' : 'Làm mới giá'}
          </button>
        </div>
      )}

      {analysis && (
        <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Khuyến nghị phân tích</h2>
              <p className="text-sm text-gray-500">Kết quả dựa trên giá hiện tại, xu hướng và biến động thị trường.</p>
            </div>
            {dataSources[0] && <DataSourceBadge data={dataSources[0]} />}
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg bg-green-50 p-4">
              <p className="text-sm text-green-700">{analysis.recommendation?.title || 'Khuyến nghị'}</p>
              <p className="mt-2 text-base font-semibold text-green-900">{translateUiText(analysis.recommendation?.reason || 'Đang tổng hợp khuyến nghị.')}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-700">Rủi ro thị trường</p>
              <p className="mt-2 text-base font-semibold text-slate-900">{translateUiText(analysis.volatility?.summary || 'Chưa đủ dữ liệu rủi ro')}</p>
            </div>
          </div>

          {analysis.history_notice && (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              {analysis.history_notice}
            </div>
          )}

          {analysis.history_notice_7d && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              {analysis.history_notice_7d}
            </div>
          )}

          {regionalComparison.length > 0 && (
            <div className="mt-5">
              <h3 className="text-sm font-semibold text-gray-900">So sánh vùng miền</h3>
              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {regionalComparison.map((item) => (
                  <div
                    key={item.region}
                    data-testid={`regional-row-${item.region}`}
                    className="rounded-lg border border-gray-200 p-4"
                  >
                    <div className="font-semibold text-gray-900">{item.region}</div>
                    <div data-testid="regional-price" className="mt-2 text-lg font-bold text-gray-900">
                      {formatMoney(item.price)}
                    </div>
                    <div data-testid="regional-difference" className="mt-1 text-sm text-gray-600">
                      {hasValue(item.difference_percent)
                        ? `${Number(item.difference_percent) > 0 ? '+' : ''}${Number(item.difference_percent).toFixed(2)}%`
                        : MISSING}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {channels.map((channel, index) => {
          const Icon = channelIcons[index % channelIcons.length];
          const channelId = channel.id || channel.channel_code;
          const channelName = channel.name || channel.channel_name;
          const commission =
            channel.commission ||
            (Number.isFinite(channel.commission_rate) ? `${Math.round(channel.commission_rate * 100)}%` : 'N/A');
          return (
            <div key={channelId || channelName} className="rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
              <div className="mb-4 flex items-center">
                <div className="rounded-lg bg-primary-100 p-3">
                  <Icon className="h-6 w-6 text-primary-600" />
                </div>
                <div className="ml-3">
                  <h3 className="text-lg font-semibold text-gray-900">{channelName}</h3>
                  <p className="text-sm text-gray-600">{channelId}</p>
                </div>
              </div>

              <div>
                <span className="text-sm font-medium text-gray-700">Phí hoa hồng:</span>
                <span className="ml-2 text-sm text-gray-900">{commission}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Store price comparison (realtime) ──────────────────────────── */}
      {(storePricesLoading || storePrices) && (
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <Store className="h-5 w-5 text-green-700" />
            <h2 className="text-lg font-semibold text-gray-900">Giá tại chuỗi cửa hàng lớn</h2>
            {/* Không bịa nguồn và độ tin cậy: chỉ chuyển tiếp đúng thứ backend trả. */}
            {storePrices && !storePricesLoading && (
              <DataSourceBadge
                data={{
                  source: storePrices.source,
                  source_name: storePrices.source_name,
                  confidence: storePrices.confidence ?? null,
                }}
              />
            )}
          </div>

          {storePricesLoading && (
            <div className="flex items-center gap-3 py-6 text-sm text-gray-500">
              <div className="h-4 w-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
              Đang tìm giá thực tế tại các chuỗi cửa hàng...
            </div>
          )}

          {!storePricesLoading && storePrices?.error && !storePrices?.stores?.length && (
            <div className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {storePrices.error}
            </div>
          )}

          {!storePricesLoading && storePrices?.stores?.length > 0 && (
            <>
              {storePrices.warning && (
                <div className="mb-3 flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  {storePrices.warning}
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-left">
                      <th className="pb-3 pr-4 font-semibold text-gray-700">Chuỗi cửa hàng</th>
                      <th className="pb-3 pr-4 font-semibold text-gray-700">Loại hình</th>
                      <th className="pb-3 pr-4 font-semibold text-gray-700 text-right">Giá (đ/kg)</th>
                      <th className="pb-3 font-semibold text-gray-700 text-right">So với sỉ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis?.current_price > 0 && (
                      <tr className="border-b border-gray-50 bg-gray-50">
                        <td className="py-3 pr-4 font-semibold text-gray-600">Chợ đầu mối / thương lái</td>
                        <td className="py-3 pr-4 text-gray-400">Sỉ</td>
                        <td className="py-3 pr-4 text-right font-bold text-gray-900">
                          {Number(analysis.current_price).toLocaleString('vi-VN')}
                        </td>
                        <td className="py-3 text-right text-xs text-gray-400">— cơ sở</td>
                      </tr>
                    )}
                    {(storePrices.stores || []).map((store) => {
                      const diffPct = analysis?.current_price > 0
                        ? (((store.price - analysis.current_price) / analysis.current_price) * 100).toFixed(0)
                        : null;
                      return (
                        <tr key={store.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                          <td className="py-3 pr-4 font-semibold text-gray-900">
                            {store.name}
                            {store.is_estimated && (
                              <span className="ml-2 text-xs font-normal text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">ước tính</span>
                            )}
                          </td>
                          <td className="py-3 pr-4 text-gray-500">{store.type}</td>
                          <td className="py-3 pr-4 text-right font-bold text-gray-900">
                            {Number(store.price).toLocaleString('vi-VN')}
                          </td>
                          <td className="py-3 text-right">
                            {diffPct !== null ? (
                              <span className={`text-xs font-semibold ${Number(diffPct) > 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                                {Number(diffPct) > 0 ? '+' : ''}{diffPct}%
                              </span>
                            ) : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-gray-400">
                {storePrices.is_estimated
                  ? `* Giá ước tính dựa trên giá sỉ + markup thông thường — ${storePrices.fetched_at}. Có thể dao động theo chuỗi và thời điểm.`
                  : `* Giá tìm kiếm realtime qua Gemini Google Search — ${storePrices.fetched_at}. Có thể dao động theo chi nhánh và thời điểm.`}
              </p>
            </>
          )}

          {!storePricesLoading && storePrices?.stores?.length === 0 && !storePrices?.error && (
            <p className="text-sm text-gray-500 py-4">
              Chưa tìm thấy giá tại các chuỗi cửa hàng cho <strong>{normalizedInputs.cropName}</strong> tại <strong>{normalizedInputs.region}</strong>.
            </p>
          )}
        </section>
      )}

      <section className="mt-8 rounded-lg border border-gray-200 bg-white p-6 shadow">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900">Tin thị trường</h2>
          <DataSourceBadge
            data={
              news[0] || {
                source: newsError ? 'legacy' : 'realtime_api',
                source_name: newsError ? 'Tin đã lưu' : 'Tin thị trường',
                confidence: newsError ? 0.45 : 0.7,
              }
            }
          />
        </div>

        {news.length ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {news.map((item) => (
              <a
                key={item.source_url || item.title}
                href={item.source_url || '#'}
                target="_blank"
                rel="noreferrer"
                className="rounded-lg border border-gray-200 p-4 hover:border-green-300 hover:bg-green-50"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold text-gray-900">{item.title}</p>
                  <DataSourceBadge data={item} />
                </div>
                <p className="mt-2 line-clamp-2 text-sm text-gray-600">{translateUiText(item.summary || item.ai_summary)}</p>
                <div className="mt-3 grid gap-2 text-xs text-gray-600">
                  <p><span className="font-semibold">Tóm tắt:</span> {translateUiText(item.ai_summary || item.recommendation || item.summary || 'Đang tổng hợp.')}</p>
                  <p><span className="font-semibold">Nông sản liên quan:</span> {(item.affected_crops || []).join(', ') || normalizedInputs.cropName}</p>
                  <p><span className="font-semibold">Khu vực liên quan:</span> {(item.affected_regions || []).join(', ') || normalizedInputs.region}</p>
                  <p>
                    <span className="font-semibold">Tác động:</span> {translateUiText(item.impact || 'neutral')}
                    {' · '}Điểm {item.impact_score ?? 'N/A'}
                    {' · '}Ảnh hưởng giá {translateUiText(item.price_effect || 'stable')}
                  </p>
                  <p><span className="font-semibold">Cập nhật:</span> {item.updated_at || item.published_at || 'N/A'}</p>
                </div>
              </a>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-gray-300 p-5 text-center text-sm text-gray-600">
            Chưa có tin thị trường phù hợp.
          </div>
        )}
      </section>
    </div>
  );
};

export default MarketPage;
