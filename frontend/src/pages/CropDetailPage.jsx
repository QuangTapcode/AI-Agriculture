import {
  Bell,
  ChevronLeft,
  Droplet,
  Leaf,
  MapPin,
  Share2,
  Thermometer,
  TrendingDown,
  TrendingUp,
  Wind
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Bar, Line } from 'react-chartjs-2';
import { useNavigate, useParams } from 'react-router-dom';
import { InlineLoading, PageError } from '../components/StatusState';
import { cropsApi } from '../services/cropsApi';
import { pricingApi } from '../services/pricingApi';
import { MISSING, formatNumber, hasValue } from '../utils/format';

const DEFAULT_REGION = 'Ha Noi';
const REGION_LABELS = {
  'Ha Noi': 'Hà Nội',
  'Da Nang': 'Đà Nẵng',
  'Can Tho': 'Cần Thơ',
  'Lam Dong': 'Lâm Đồng',
  'Dak Lak': 'Đắk Lắk',
  'Hai Phong': 'Hải Phòng',
};

const displayRegion = (value) => REGION_LABELS[value] || value;

const CropDetailPage = () => {
  const { cropId } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('30N');

  const [crop, setCrop] = useState(null);
  const [priceData, setPriceData] = useState(null);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [regionComparison, setRegionComparison] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!cropId) return;
    let active = true;
    setLoading(true);
    setError('');

    cropsApi.getCropDetail(cropId)
      .then(async (cropDetail) => {
        if (!active) return;
        setCrop(cropDetail);
        const name = cropDetail.crop_name;

        const [price, hist, fc, regions] = await Promise.allSettled([
          pricingApi.getCurrentPrice(name, DEFAULT_REGION),
          pricingApi.getPriceHistory(name, DEFAULT_REGION, 30),
          pricingApi.getPriceForecast(name, DEFAULT_REGION, 7),
          pricingApi.compareRegions(name),
        ]);

        if (!active) return;
        if (price.status === 'fulfilled') setPriceData(price.value);
        if (hist.status === 'fulfilled') setHistory(hist.value?.history || []);
        if (fc.status === 'fulfilled') setForecast(fc.value?.forecast_data || []);
        if (regions.status === 'fulfilled') setRegionComparison(regions.value?.regions || []);
      })
      .catch((err) => {
        if (active) setError(err?.response?.data?.detail || 'Không thể tải dữ liệu cây trồng');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [cropId]);

  const historyDays = history.slice(-30);
  const chartData = {
    labels: historyDays.map((h) => h.date?.slice(5) || ''),
    datasets: [
      {
        label: 'Giá trung bình',
        // null tạo khoảng trống trên biểu đồ; 0 vẽ thành cú sập giá không có thật.
        data: historyDays.map((h) => (hasValue(h.avg_price) ? Number(h.avg_price) : null)),
        borderColor: '#15803d',
        backgroundColor: 'rgba(21, 128, 61, 0.1)',
        borderWidth: 2,
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 5,
      },
    ],
  };
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
    scales: {
      x: { display: false },
      y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { callback: (v) => (v / 1000).toFixed(0) + 'k' } },
    },
  };

  const barChartData = {
    labels: historyDays.filter((_, i) => i % 10 === 0).map((h) => h.date?.slice(5) || ''),
    datasets: [
      {
        data: historyDays
          .filter((_, i) => i % 10 === 0)
          .map((h) => (hasValue(h.avg_price) ? Number(h.avg_price) : null)),
        backgroundColor: (ctx) => {
          const v = ctx.parsed?.y || 0;
          if (v < 15000) return 'rgba(34,197,94,0.3)';
          if (v < 25000) return 'rgba(34,197,94,0.6)';
          return 'rgba(21,128,61,1)';
        },
        borderRadius: 8,
        barThickness: 50,
      },
    ],
  };
  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => ctx.parsed.y.toLocaleString() + ' VNĐ/kg' } } },
    scales: { x: { grid: { display: false } }, y: { display: false } },
  };

  /*
   * Mức thay đổi chỉ có nghĩa khi có cả giá của dòng này lẫn giá mốc đầu kỳ.
   * Bản cũ lấy mốc `|| 0`, nên thiếu mốc thì chênh lệch bằng đúng giá dự báo.
   */
  const forecastBase = hasValue(forecast[0]?.predicted_price) ? Number(forecast[0].predicted_price) : null;
  const forecastRows = forecast.slice(0, 3).map((f) => {
    const price = hasValue(f.predicted_price) ? Number(f.predicted_price) : null;
    const comparable = price !== null && forecastBase !== null;
    const delta = comparable ? price - forecastBase : null;

    return {
      date: new Date(f.date).getDate(),
      price,
      change: comparable ? `${delta > 0 ? '+' : ''}${delta.toLocaleString('vi-VN')}` : MISSING,
      status: comparable ? (delta >= 0 ? 'up' : 'down') : 'unknown',
    };
  });

  /*
   * Chỉ hiển thị vùng nào backend thực sự trả về. Bản cũ khi thiếu dữ liệu thì
   * dựng sẵn hai dòng "Hà Nội" và "Cần Thơ", lấy typical_price_max/min của cây
   * trồng gán vào — tức là khoảng giá tham khảo chung bị trình bày thành giá
   * từng vùng, đủ để người bán ra quyết định sai.
   */
  const displayedRegions = regionComparison
    .filter((item) => hasValue(item?.price))
    .slice(0, 3)
    .map((item) => ({ region: item.region, subRegion: '', price: item.price, unit: 'VNĐ/kg' }));

  if (loading) return <InlineLoading text="Đang tải dữ liệu cây trồng..." />;
  if (error) return <PageError message={error} onRetry={() => window.location.reload()} />;
  if (!crop) return <PageError message="Không tìm thấy cây trồng" onRetry={() => navigate(-1)} />;

  // Giá hiện tại phải là giá đo được, không phải cận dưới của khoảng tham khảo.
  const currentPrice = hasValue(priceData?.current_price) ? Number(priceData.current_price) : null;
  const currentPriceText = formatNumber(currentPrice);

  const priceChangePct = priceData?.price_change_pct;
  const hasPriceChange = hasValue(priceChangePct);
  const priceChange = hasPriceChange
    ? `${Number(priceChangePct) > 0 ? '+' : ''}${Number(priceChangePct).toFixed(1)}%`
    : MISSING;

  return (
    <div className="space-y-6">
      <button onClick={() => navigate(-1)} className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 transition">
        <ChevronLeft className="w-5 h-5" />
        <span>Quay lại</span>
      </button>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <div className="flex justify-between items-start mb-6">
          <div>
            <div className="inline-block bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-medium mb-3">
              {crop.harvest_season || 'CHƯA RÕ MÙA VỤ'}
            </div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{crop.crop_name}</h1>
            <p className="text-gray-600 flex items-center space-x-2">
              <MapPin className="w-4 h-4" />
              <span>{crop.category || displayRegion(DEFAULT_REGION)}</span>
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <button className="p-3 border-2 border-gray-300 rounded-xl hover:border-green-700 hover:text-green-700 transition">
              <Share2 className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex items-end justify-between">
          <div>
            <div data-testid="crop-current-price" className="text-5xl font-bold text-gray-900 mb-2">
              {currentPriceText}
              <span className="text-2xl text-gray-500 ml-2">VNĐ/kg</span>
            </div>
            <div className="flex items-center space-x-3">
              <div
                data-testid="crop-price-change"
                className={`flex items-center space-x-1 ${
                  !hasPriceChange ? 'text-gray-500' : Number(priceChangePct) < 0 ? 'text-red-600' : 'text-green-600'
                }`}
              >
                {hasPriceChange &&
                  (Number(priceChangePct) < 0 ? (
                    <TrendingDown className="w-5 h-5" />
                  ) : (
                    <TrendingUp className="w-5 h-5" />
                  ))}
                <span className="font-semibold">{priceChange}</span>
              </div>
              <span className="text-gray-500">so sánh hôm qua</span>
            </div>
          </div>
          <button className="bg-green-700 text-white px-8 py-4 rounded-xl font-bold hover:bg-green-800 transition flex items-center space-x-2">
            <Bell className="w-5 h-5" />
            <span>Đặt Cảnh Báo Giá</span>
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* 7-Day Forecast */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Dự Báo 7 Ngày</h2>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="text-sm text-gray-500">Dữ liệu thực</span>
              </div>
            </div>
            {forecastRows.length > 0 ? (
              <div className="space-y-3">
                {forecastRows.map((day, index) => (
                  <div key={index} className="flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition">
                    <div className="flex items-center space-x-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-gray-900">{day.date}</div>
                        <div className="text-xs text-gray-500">tháng tới</div>
                      </div>
                      <div>
                        <div className="text-xl font-bold text-gray-900">{formatNumber(day.price)}</div>
                        <div className="text-sm text-gray-500">VNĐ/kg dự báo</div>
                      </div>
                    </div>
                    <div
                      className={`flex items-center space-x-2 ${
                        day.status === 'unknown'
                          ? 'text-gray-500'
                          : day.status === 'up'
                            ? 'text-green-600'
                            : 'text-red-600'
                      }`}
                    >
                      {day.status === 'up' && <TrendingUp className="w-5 h-5" />}
                      {day.status === 'down' && <TrendingDown className="w-5 h-5" />}
                      <span className="font-semibold">
                        {day.status === 'unknown' ? day.change : `${day.change} VNĐ`}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">Chưa có dữ liệu dự báo cho cây trồng này.</p>
            )}
          </div>

          {/* Price Trend Chart */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Biến Động Giá (30 ngày)</h2>
              <div className="flex items-center space-x-2 bg-gray-100 rounded-lg p-1">
                {['30N', '90N', '1N'].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === tab ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>
            {historyDays.length > 0 ? (
              <>
                <div className="h-64 mb-6"><Line data={chartData} options={chartOptions} /></div>
                <div className="h-48"><Bar data={barChartData} options={barChartOptions} /></div>
              </>
            ) : (
              <p className="text-gray-500 text-sm py-8 text-center">Chưa có lịch sử giá cho cây trồng này.</p>
            )}
          </div>

          {/* Regional Comparison */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-6">So Sánh Vùng Miền</h2>
            <div data-testid="region-comparison" className="space-y-3">
              {!displayedRegions.length && (
                <p className="rounded-xl border border-dashed border-gray-200 px-4 py-6 text-center text-sm text-gray-500">
                  Chưa có dữ liệu so sánh theo vùng cho cây trồng này.
                </p>
              )}
              {displayedRegions.map((region, index) => (
                <div key={index} className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                  <div className="flex items-center space-x-3">
                    <div className={`w-3 h-3 rounded-full ${index === 0 ? 'bg-green-500' : index === 1 ? 'bg-green-400' : 'bg-orange-500'}`} />
                    <div>
                      <div className="font-bold text-gray-900">{displayRegion(region.region)}</div>
                      {region.subRegion && <div className="text-sm text-gray-500">{region.subRegion}</div>}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-gray-900">{formatNumber(region.price)}</div>
                    <div className="text-sm text-gray-500">{region.unit}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-bold text-gray-900 mb-4">Thông tin cây trồng</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-blue-50 rounded-xl">
                <div className="flex items-center space-x-3">
                  <Droplet className="w-6 h-6 text-blue-600" />
                  <span className="text-gray-700">Chu kỳ sinh trưởng</span>
                </div>
                <span className="text-xl font-bold text-gray-900">
                  {crop.growth_duration_days ? `${crop.growth_duration_days} ngày` : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between p-4 bg-orange-50 rounded-xl">
                <div className="flex items-center space-x-3">
                  <Thermometer className="w-6 h-6 text-orange-600" />
                  <span className="text-gray-700">Mùa vụ</span>
                </div>
                <span className="font-bold text-gray-900">{crop.harvest_season || 'Quanh năm'}</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-bold text-gray-900 mb-4">Khoảng giá điển hình</h3>
            <div className="p-4 bg-gray-50 rounded-xl">
              <div className="flex items-center space-x-2 mb-2">
                <Wind className="w-5 h-5 text-gray-600" />
                <span className="text-sm text-gray-600">Theo dữ liệu lịch sử</span>
              </div>
              <p className="text-sm text-gray-700">
                {crop.typical_price_min && crop.typical_price_max
                  ? `${Number(crop.typical_price_min).toLocaleString()} – ${Number(crop.typical_price_max).toLocaleString()} VNĐ/kg`
                  : 'Chưa có dữ liệu'}
              </p>
            </div>
          </div>

          {crop.description && (
            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-2xl border border-green-200 p-6">
              <div className="flex items-center space-x-2 mb-4">
                <Leaf className="w-6 h-6 text-green-700" />
                <h3 className="font-bold text-gray-900">Mô tả</h3>
              </div>
              <p className="text-sm text-gray-700">{crop.description}</p>
            </div>
          )}

          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-bold text-gray-900 mb-4">Giá Hiện Tại</h3>
            <div className="text-center py-4">
              <div className="text-4xl font-bold text-green-700 mb-2">{currentPriceText}</div>
              <div className="text-gray-600">VNĐ/kg (loại 1)</div>
              {priceData?.weather_adjusted_price && (
                <div className="mt-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
                  Điều chỉnh thời tiết: {priceData.weather_adjusted_price.toLocaleString()} VNĐ/kg
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CropDetailPage;
