import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip
} from 'chart.js';
import {
  AlertCircle,
  ChevronRight,
  Filter,
  Globe,
  Loader2,
  MapPin,
  TrendingDown,
  TrendingUp
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Line } from 'react-chartjs-2';
import { pricingApi } from '../services/pricingApi';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const CROPS = [
  'ca phe', 'lua', 'sau rieng', 'ho tieu', 'ca chua', 'xoai', 'thanh long',
];
const CROP_LABELS = {
  'ca phe': 'Cà phê',
  'lua': 'Lúa',
  'sau rieng': 'Sầu riêng',
  'ho tieu': 'Hồ tiêu',
  'ca chua': 'Cà chua',
  'xoai': 'Xoài',
  'thanh long': 'Thanh long',
};
const DEFAULT_REGION = 'Dak Lak';
const DEFAULT_REGION_LABEL = 'Đắk Lắk';
const TREND_LABELS = {
  increasing: 'Tăng',
  decreasing: 'Giảm',
  stable: 'Ổn định',
};
const REGION_LABELS = {
  'Ha Noi': 'Hà Nội',
  'Da Nang': 'Đà Nẵng',
  'Can Tho': 'Cần Thơ',
  'Lam Dong': 'Lâm Đồng',
  'Dak Lak': 'Đắk Lắk',
  'Hai Phong': 'Hải Phòng',
};

const displayRegion = (value) => REGION_LABELS[value] || value;

const internationalPrices = [
  { market: 'London Robusta (LCE)', price: '$2,450/tấn', change: '(+2%)', flag: '🇬🇧' },
  { market: 'New York Arabica (ICE)', price: '$3,100/tấn', change: '(+1.5%)', flag: '🇺🇸' },
  { market: 'Brazilian Conillon', price: '$2,100/tấn', change: '(-1%)', flag: '🇧🇷' },
];

const PricingDashboard = () => {
  const [selectedCrop, setSelectedCrop] = useState('ca phe');
  const [currentPrice, setCurrentPrice] = useState(null);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [regionData, setRegionData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    setCurrentPrice(null);
    setHistory([]);
    setForecast([]);
    setRegionData([]);

    try {
      const [priceRes, histRes, fcRes, regionRes] = await Promise.allSettled([
        pricingApi.getCurrentPrice(selectedCrop, DEFAULT_REGION),
        pricingApi.getPriceHistory(selectedCrop, DEFAULT_REGION, 90),
        pricingApi.getPriceForecast(selectedCrop, DEFAULT_REGION, 90),
        pricingApi.compareRegions(selectedCrop),
      ]);

      if (priceRes.status === 'fulfilled') setCurrentPrice(priceRes.value);
      if (histRes.status === 'fulfilled') setHistory(histRes.value?.history || []);
      if (fcRes.status === 'fulfilled') setForecast(fcRes.value?.forecast_data || []);
      if (regionRes.status === 'fulfilled') setRegionData(regionRes.value?.regions || []);

      if (
        priceRes.status === 'rejected' ||
        histRes.status === 'rejected' ||
        fcRes.status === 'rejected' ||
        regionRes.status === 'rejected'
      ) {
        setError('Không thể tải dữ liệu giá');
      }
    } catch {
      setError('Không thể tải dữ liệu giá');
    } finally {
      setLoading(false);
    }
  }, [selectedCrop]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Build chart combining history + forecast
  const histLabels = history.slice(-30).map((h) => h.date?.slice(5) || '');
  const fcLabels = forecast.slice(0, 30).map((f) => f.date?.slice(5) || '');
  const allLabels = [...histLabels, ...fcLabels];

  const histPrices = history.slice(-30).map((h) => h.avg_price || null);
  const bridgePoint = histPrices.length > 0 ? histPrices[histPrices.length - 1] : null;
  const fcPrices = [bridgePoint, ...forecast.slice(0, 30).map((f) => f.predicted_price || null)];
  const fcLabelsWithBridge = ['', ...fcLabels];

  const chartData = {
    labels: [...histLabels, ...fcLabels],
    datasets: [
      {
        label: 'Lịch sử',
        data: [...histPrices, ...Array(fcLabels.length).fill(null)],
        borderColor: '#15803d',
        backgroundColor: 'rgba(21, 128, 61, 0.08)',
        borderWidth: 2.5,
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 5,
      },
      {
        label: 'Dự báo AI',
        data: histLabels.length > 0
          ? [...Array(histLabels.length - 1).fill(null), bridgePoint, ...forecast.slice(0, 30).map((f) => f.predicted_price || null)]
          : forecast.slice(0, 30).map((f) => f.predicted_price || null),
        borderColor: '#15803d',
        backgroundColor: 'rgba(21, 128, 61, 0.04)',
        borderWidth: 2.5,
        borderDash: [5, 5],
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
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: 'rgba(0,0,0,0.8)',
        padding: 12,
        callbacks: { label: (ctx) => `${ctx.dataset.label}: ${(ctx.parsed.y || 0).toLocaleString()} ₫` },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } },
      y: {
        grid: { color: 'rgba(0,0,0,0.05)' },
        ticks: { callback: (v) => v.toLocaleString() + ' ₫' },
      },
    },
    interaction: { mode: 'nearest', axis: 'x', intersect: false },
  };

  const price = currentPrice?.current_price || 0;
  const changePct = currentPrice?.price_change_pct || 0;
  const priceChangeStr = `${changePct >= 0 ? '+' : ''}${changePct.toFixed(1)}%`;
  const cropLabel = CROP_LABELS[selectedCrop] || selectedCrop;

  const displayedRegions = regionData.length > 0
    ? regionData.slice(0, 3).map((r) => ({
        region: r.region,
        subRegion: '',
        price: r.price || 0,
        change: '+0.0%',
        trend: 'stable',
        status: r.price > price ? 'CAO' : r.price < price * 0.95 ? 'THẤP' : 'BÌNH THƯỜNG',
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start flex-wrap gap-4">
        <div>
          <div className="flex items-center space-x-2 text-sm text-gray-500 mb-2">
            <span>Phân tích giá nông sản</span>
            <ChevronRight className="w-4 h-4" />
            <span className="bg-yellow-100 text-yellow-800 px-3 py-1 rounded-full text-xs font-medium">
              DỮ LIỆU THỰC
            </span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Dự Báo Giá Thông Minh</h1>
          <p className="text-gray-600">Phân tích {cropLabel} theo thời gian thực — {DEFAULT_REGION_LABEL}</p>
        </div>
        <div className="text-right">
          {loading ? (
            <div className="flex items-center space-x-2 text-gray-500">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Đang tải...</span>
            </div>
          ) : (
            <>
              <div className="text-sm text-gray-500 mb-1">GIÁ HIỆN TẠI</div>
              <div className="text-4xl font-bold text-gray-900">{price.toLocaleString()} VNĐ/kg</div>
              <div className="flex items-center justify-end space-x-2 mt-1">
                {changePct >= 0 ? <TrendingUp className="w-5 h-5 text-green-600" /> : <TrendingDown className="w-5 h-5 text-red-600" />}
                <span className={`font-semibold ${changePct >= 0 ? 'text-green-600' : 'text-red-600'}`}>{priceChangeStr}</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Crop Selector */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-medium text-gray-600">Chọn cây trồng:</span>
          {CROPS.map((c) => (
            <button
              key={c}
              onClick={() => setSelectedCrop(c)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${selectedCrop === c ? 'bg-green-700 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
            >
              {CROP_LABELS[c] || c}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-2 text-red-700">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left Column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Price Chart */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <div className="flex justify-between items-center mb-6">
              <div>
                <h2 className="text-xl font-bold text-gray-900 mb-1">Dự Báo Giá</h2>
                <p className="text-sm text-gray-500">Lịch sử 30 ngày + dự báo 30 ngày tới</p>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <div className="flex items-center gap-1">
                  <div className="w-8 h-0.5 bg-green-700 rounded" />
                  <span className="text-gray-600">Lịch sử</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-8 border-t-2 border-dashed border-green-700" />
                  <span className="text-gray-600">Dự báo</span>
                </div>
              </div>
            </div>
            <div className="h-80">
              {history.length > 0 || forecast.length > 0
                ? <Line data={chartData} options={chartOptions} />
                : <div className="h-full flex items-center justify-center text-gray-400">Chưa có dữ liệu biểu đồ</div>
              }
            </div>
          </div>

          {/* Regional Comparison */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-gray-900">So Sánh Giá Theo Khu Vực</h2>
              <button className="flex items-center space-x-2 text-green-700 font-medium hover:text-green-800">
                <span>Lọc Khu Vực</span>
                <Filter className="w-4 h-4" />
              </button>
            </div>

            {displayedRegions.length > 0 ? (
              <div className="space-y-4">
                <div className="grid grid-cols-5 gap-4 text-xs font-medium text-gray-500 uppercase pb-2 border-b border-gray-200">
                  <div className="col-span-2">Khu vực</div>
                  <div className="text-right">Giá hôm nay</div>
                  <div className="text-right">Mức giá</div>
                  <div className="text-right">Hành động</div>
                </div>
                {displayedRegions.map((item, index) => (
                  <div key={index} className="grid grid-cols-5 gap-4 items-center py-3 border-b border-gray-100 hover:bg-gray-50 transition">
                    <div className="col-span-2 flex items-center space-x-3">
                      <MapPin className="w-5 h-5 text-gray-400" />
                      <div>
                        <div className="font-bold text-gray-900">{displayRegion(item.region)}</div>
                        {item.subRegion && <div className="text-sm text-gray-500">{item.subRegion}</div>}
                      </div>
                    </div>
                    <div className="text-right font-bold text-gray-900">
                      {item.price.toLocaleString()} VNĐ/kg
                    </div>
                    <div className="text-right">
                      <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                        item.status === 'CAO' ? 'bg-orange-100 text-orange-700' :
                        item.status === 'THẤP' ? 'bg-blue-100 text-blue-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {item.status}
                      </span>
                    </div>
                    <div className="text-right">
                      <button className="text-green-700 font-medium hover:text-green-800 text-sm">Xem Chi Tiết</button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400 text-sm py-4">Chưa có dữ liệu so sánh vùng miền.</p>
            )}
          </div>

          {/* International Market */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center space-x-2 mb-6">
              <Globe className="w-5 h-5 text-gray-600" />
              <h2 className="text-xl font-bold text-gray-900">Thị Trường Quốc Tế</h2>
              <span className="text-xs text-gray-500 ml-auto">Tham khảo</span>
            </div>
            <div className="space-y-4">
              {internationalPrices.map((item, index) => (
                <div key={index} className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                  <div className="flex items-center space-x-3">
                    <span className="text-2xl">{item.flag}</span>
                    <div>
                      <div className="font-medium text-gray-900">{item.market}</div>
                      <div className="text-sm text-gray-500">Giá tham khảo quốc tế</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-gray-900">{item.price}</div>
                    <div className={`text-sm ${item.change.includes('+') ? 'text-green-600' : 'text-red-600'}`}>{item.change}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="lg:col-span-1">
          <div className="bg-gradient-to-br from-green-800 to-green-900 rounded-2xl p-6 text-white sticky top-6 space-y-4">
            <div className="text-sm font-medium text-green-200">KHUYẾN NGHỊ AI</div>
            <h2 className="text-2xl font-bold">{currentPrice?.price_trend === 'increasing' ? 'Nên Giữ Lại' : 'Bán Theo Đợt'}</h2>
            <p className="text-green-100 leading-relaxed text-sm">
              {currentPrice?.weather_explanation || `Dựa trên xu hướng giá ${cropLabel} tại ${DEFAULT_REGION_LABEL}, cân nhắc bán dần để tối ưu lợi nhuận.`}
            </p>

            <div className="bg-green-700/40 rounded-xl p-4 space-y-2">
              <div className="text-xs text-green-300 uppercase font-medium">Thông tin giá</div>
              {currentPrice?.weather_adjusted_price && (
                <div className="flex justify-between text-sm">
                  <span className="text-green-200">Điều chỉnh thời tiết</span>
                  <span className="font-bold">{currentPrice.weather_adjusted_price.toLocaleString()} ₫/kg</span>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span className="text-green-200">Xu hướng</span>
                <span className="font-bold">{TREND_LABELS[currentPrice?.price_trend] || '–'}</span>
              </div>
            </div>

            <button className="w-full bg-white text-green-800 py-3 rounded-xl font-bold hover:bg-green-50 transition">
              Xem Dự Báo Chi Tiết →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PricingDashboard;
