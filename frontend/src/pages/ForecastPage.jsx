import {
  AlertTriangle,
  Bot,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  CheckCircle2,
  Clock,
  CloudRain,
  CloudSun,
  Droplets,
  Eye,
  Gauge,
  Leaf,
  Loader2,
  MapPin,
  RefreshCw,
  Sprout,
  Sun,
  Thermometer,
  Umbrella,
  Wind,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import DataSourceBadge from '../components/DataSourceBadge';
import { getApiErrorMessage } from '../services/api';
import { weatherApi } from '../services/weatherApi';
import { cropImpacts } from '../utils/cropImpact';
import { thunderstormRisk } from '../utils/weatherRisk';
import { severityLabel, translateUiText } from '../utils/vietnameseText';

const regions = [
  { value: 'Ha Noi', label: 'Hà Nội' },
  { value: 'TP.HCM', label: 'TP.HCM' },
  { value: 'Da Nang', label: 'Đà Nẵng' },
  { value: 'Can Tho', label: 'Cần Thơ' },
  { value: 'Lam Dong', label: 'Lâm Đồng' },
  { value: 'Hai Phong', label: 'Hải Phòng' },
];
const crops = ['Lúa', 'Cà phê', 'Rau màu', 'Hồ tiêu', 'Cây ăn trái'];
const stages = ['Cây con', 'Sinh trưởng', 'Ra hoa', 'Làm đòng', 'Đậu trái', 'Thu hoạch'];

const severityStyles = {
  high: 'border-red-200 bg-red-50 text-red-800',
  medium: 'border-amber-200 bg-amber-50 text-amber-800',
  low: 'border-sky-200 bg-sky-50 text-sky-800',
};

const priorityStyles = {
  high: 'border-red-200 bg-red-50 text-red-800',
  medium: 'border-amber-200 bg-amber-50 text-amber-800',
  low: 'border-emerald-200 bg-emerald-50 text-emerald-800',
};

const CONDITION_EMOJI = {
  clear: '☀️',
  mostly_clear: '🌤️',
  partly_cloudy: '⛅',
  cloudy: '☁️',
  foggy: '🌫️',
  drizzle: '🌦️',
  heavy_drizzle: '🌧️',
  light_rain: '🌦️',
  rainy: '🌧️',
  heavy_rain: '🌧️',
  light_showers: '🌦️',
  rain_showers: '🌦️',
  heavy_showers: '🌧️',
  thunderstorm: '⛈️',
  thunderstorm_hail: '⛈️',
  cold_unusual: '❄️',
  unknown: '🌡️',
};

const CONDITION_LABELS = {
  clear: 'Quang đãng',
  mostly_clear: 'Khá quang',
  partly_cloudy: 'Ít mây',
  cloudy: 'Nhiều mây',
  foggy: 'Sương mù',
  drizzle: 'Mưa phùn',
  heavy_drizzle: 'Mưa phùn dày',
  light_rain: 'Mưa nhẹ',
  rainy: 'Có mưa',
  heavy_rain: 'Mưa lớn',
  light_showers: 'Mưa rào nhẹ',
  rain_showers: 'Mưa rào',
  heavy_showers: 'Mưa rào mạnh',
  thunderstorm: 'Giông bão',
  thunderstorm_hail: 'Giông kèm mưa đá',
  cold_unusual: 'Lạnh bất thường',
  unknown: '—',
};

const formatNumber = (value, suffix = '', digits = 1) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  return `${Number(value).toFixed(digits)}${suffix}`;
};

const formatDate = (value) => {
  if (!value) return 'N/A';
  return new Date(value).toLocaleDateString('vi-VN', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
  });
};

const formatTime = (value) => {
  if (!value) return 'N/A';
  const d = new Date(value);
  if (isNaN(d)) return String(value).slice(11, 16);
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
};

const uvLabel = (v) => {
  if (v == null) return '';
  if (v <= 2) return 'Thấp';
  if (v <= 5) return 'Vừa';
  if (v <= 7) return 'Cao';
  if (v <= 10) return 'Rất cao';
  return 'Cực cao';
};

const cloudLabel = (pct) => {
  if (pct == null) return '';
  if (pct <= 10) return 'Trời quang';
  if (pct <= 30) return 'Ít mây';
  if (pct <= 60) return 'Mây rải rác';
  if (pct <= 85) return 'Nhiều mây';
  return 'Trời âm u';
};

// ── Current weather metric card ────────────────────────────────────────────────
const WeatherMetric = ({ icon: Icon, label, value, detail, tone = 'slate' }) => {
  const tones = {
    slate: 'bg-slate-50 text-slate-700 border-slate-200',
    sky: 'bg-sky-50 text-sky-700 border-sky-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    rose: 'bg-rose-50 text-rose-700 border-rose-200',
  };
  return (
    <div className={`rounded-lg border p-4 ${tones[tone]}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-600">{label}</p>
          <p className="mt-2 text-2xl font-bold text-slate-950">{value}</p>
        </div>
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/80">
          <Icon className="h-5 w-5" />
        </span>
      </div>
      {detail && <p className="mt-3 text-sm leading-6 text-slate-600">{detail}</p>}
    </div>
  );
};

// ── Day card (clickable) ───────────────────────────────────────────────────────
const DayCard = ({ day, selected, onClick }) => {
  const emoji = CONDITION_EMOJI[day.condition] || '🌡️';
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center gap-1 rounded-xl border px-3 py-3 text-center transition min-w-[80px] ${
        selected
          ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-200'
          : 'border-gray-200 bg-white hover:border-emerald-300 hover:bg-emerald-50/50'
      }`}
    >
      <span className="text-xs font-semibold text-gray-500">{formatDate(day.date)}</span>
      <span className="text-2xl">{emoji}</span>
      <span className="text-xs text-gray-700 font-medium">
        {formatNumber(day.temp_max, '°', 0)} / {formatNumber(day.temp_min, '°', 0)}
      </span>
      <span className="text-xs text-blue-500">{formatNumber(day.rain_probability, '%', 0)} mưa</span>
    </button>
  );
};

// ── Hour pill ──────────────────────────────────────────────────────────────────
const HourPill = ({ hour, selected, onClick }) => {
  const emoji = CONDITION_EMOJI[hour.condition] || '🌡️';
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center gap-0.5 rounded-xl border px-3 py-2 text-center transition min-w-[64px] ${
        selected
          ? 'border-sky-500 bg-sky-50 ring-2 ring-sky-200'
          : 'border-gray-200 bg-white hover:border-sky-300 hover:bg-sky-50/50'
      }`}
    >
      <span className="text-xs font-bold text-gray-700">{formatTime(hour.forecast_at || hour.time)}</span>
      <span className="text-lg">{emoji}</span>
      <span className="text-xs font-semibold text-gray-800">{formatNumber(hour.temperature, '°', 0)}</span>
      <span className="text-xs text-blue-400">{formatNumber(hour.rain_probability, '%', 0)}</span>
    </button>
  );
};

// ── Helper: metric row inside a section ───────────────────────────────────────
const MetricRow = ({ label, value, sub }) => (
  <div className="flex items-start justify-between gap-3 py-2 border-b border-gray-100 last:border-0">
    <span className="text-sm text-gray-500">{label}</span>
    <div className="text-right">
      <span className="text-sm font-semibold text-gray-900">{value}</span>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  </div>
);

// ── Section card ───────────────────────────────────────────────────────────────
const Section = ({ icon: Icon, title, iconColor, borderColor, children }) => (
  <div className={`rounded-xl border ${borderColor} bg-white p-4`}>
    <div className="flex items-center gap-2 mb-3">
      <Icon className={`h-4 w-4 ${iconColor}`} />
      <h3 className="text-sm font-bold text-gray-800">{title}</h3>
    </div>
    {children}
  </div>
);

// ── UV scale bar ───────────────────────────────────────────────────────────────
const UVBar = ({ value }) => {
  if (value == null) return <p className="text-sm text-gray-400">Không có dữ liệu</p>;
  const pct = Math.min((value / 12) * 100, 100);
  const color = value <= 2 ? 'bg-green-500' : value <= 5 ? 'bg-yellow-400' : value <= 7 ? 'bg-orange-400' : value <= 10 ? 'bg-red-500' : 'bg-purple-600';
  const label = value <= 2 ? 'Thấp' : value <= 5 ? 'Vừa' : value <= 7 ? 'Cao' : value <= 10 ? 'Rất cao' : 'Cực cao';
  const advice = value <= 2 ? 'An toàn, không cần che chắn.' : value <= 5 ? 'Nên đội mũ khi làm ngoài trời.' : value <= 7 ? 'Hạn chế ra ngoài 10:00–14:00.' : 'Che phủ đầy đủ, tưới vào sáng sớm/chiều tối.';
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-2xl font-bold text-gray-900">{formatNumber(value, '', 1)}</span>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full text-white ${color}`}>{label}</span>
      </div>
      <div className="w-full h-2 rounded-full bg-gray-100 overflow-hidden mb-2">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-gray-500">{advice}</p>
    </div>
  );
};

// ── Hour detail: 6 sections ────────────────────────────────────────────────────
const HourDetail = ({ hour }) => {
  if (!hour) return null;
  const emoji = CONDITION_EMOJI[hour.condition] || '🌡️';
  const timeStr = formatTime(hour.forecast_at || hour.time);
  const visKm = hour.visibility != null ? formatNumber(hour.visibility / 1000, ' km', 1) : '—';
  const visScore = hour.visibility != null
    ? hour.visibility >= 10000 ? 'Rất tốt' : hour.visibility >= 5000 ? 'Tốt' : hour.visibility >= 2000 ? 'Trung bình' : 'Kém'
    : '—';
  const thunder = thunderstormRisk(hour);
  const isThunderstorm = thunder.level === 'active';
  const thunderRisk = thunder.label;
  const thunderColor = {
    active: 'text-red-600',
    elevated: 'text-orange-500',
    none: 'text-green-600',
    unknown: 'text-gray-500',
  }[thunder.level];
  const impacts = cropImpacts(hour);
  const levelColor = { high: 'text-red-600 bg-red-50 border-red-200', medium: 'text-orange-600 bg-orange-50 border-orange-200', ok: 'text-green-700 bg-green-50 border-green-200' };

  return (
    <div className="mt-3 rounded-2xl border border-sky-100 bg-gray-50 p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4 bg-white rounded-xl p-3 border border-gray-100">
        <span className="text-4xl">{emoji}</span>
        <div className="flex-1">
          <p className="text-xs text-gray-400">{timeStr}</p>
          <p className="text-base font-bold text-gray-900">{CONDITION_LABELS[hour.condition] || '—'}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-gray-900">{formatNumber(hour.temperature, '°C')}</p>
          <p className="text-xs text-gray-400">Cảm giác {formatNumber(hour.apparent_temperature, '°C')}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">

        {/* 1. Độ trong khí quyển */}
        <Section icon={Eye} title="Độ trong khí quyển" iconColor="text-indigo-500" borderColor="border-indigo-100">
          <MetricRow label="Tầm nhìn" value={visKm} sub={visScore} />
          <MetricRow label="Mây phủ" value={formatNumber(hour.cloud_cover, '%', 0)} sub={cloudLabel(hour.cloud_cover)} />
          <MetricRow label="Điểm sương" value={formatNumber(hour.dew_point, '°C')} />
        </Section>

        {/* 2. Môi trường & Gió */}
        <Section icon={Wind} title="Môi trường & Gió" iconColor="text-teal-500" borderColor="border-teal-100">
          <MetricRow label="Nhiệt độ" value={formatNumber(hour.temperature, '°C')} sub={`Cảm giác ${formatNumber(hour.apparent_temperature, '°C')}`} />
          <MetricRow label="Độ ẩm" value={formatNumber(hour.humidity, '%', 0)} />
          <MetricRow label="Gió" value={formatNumber(hour.wind_speed, ' km/h', 0)} sub={hour.wind_gusts != null ? `Giật ${formatNumber(hour.wind_gusts, ' km/h', 0)}` : null} />
          <MetricRow label="Áp suất" value={formatNumber(hour.pressure, ' hPa', 0)} />
        </Section>

        {/* 3. Mây và mưa */}
        <Section icon={CloudRain} title="Mây và mưa" iconColor="text-blue-500" borderColor="border-blue-100">
          <MetricRow label="Tình trạng" value={CONDITION_LABELS[hour.condition] || '—'} />
          <MetricRow label="Lượng mưa" value={formatNumber(hour.rainfall, ' mm')} />
          <MetricRow label="Xác suất mưa" value={formatNumber(hour.rain_probability, '%', 0)} />
          <MetricRow label="Mây phủ" value={formatNumber(hour.cloud_cover, '%', 0)} sub={cloudLabel(hour.cloud_cover)} />
        </Section>

        {/* 4. Giông lốc */}
        <Section icon={Zap} title="Giông lốc" iconColor={isThunderstorm ? 'text-red-500' : 'text-gray-400'} borderColor={isThunderstorm ? 'border-red-200' : 'border-gray-100'}>
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-base font-bold ${thunderColor}`}>{thunderRisk}</span>
            {isThunderstorm && <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-semibold">⚠ Cảnh báo</span>}
          </div>
          {isThunderstorm ? (
            <p className="text-xs text-red-600">
              {hour.condition === 'thunderstorm_hail'
                ? 'Giông kèm mưa đá — không ra ngoài, che chắn nhà kính và thiết bị nông nghiệp.'
                : 'Giông bão đang xảy ra — không làm việc ngoài trời, tránh cây cao, thu dọn dụng cụ.'}
            </p>
          ) : thunder.level === 'elevated' ? (
            <p className="text-xs text-orange-600">Mưa lớn/mưa rào mạnh có thể kéo theo giông. Theo dõi sát, chuẩn bị thoát nước đồng ruộng.</p>
          ) : thunder.level === 'none' ? (
            <p className="text-xs text-gray-400">Không có nguy cơ giông lốc trong khung giờ này.</p>
          ) : (
            <p className="text-xs text-gray-500">Chưa có dữ liệu điều kiện thời tiết cho khung giờ này.</p>
          )}
        </Section>

        {/* 5. Mức độ UV */}
        <Section icon={Sun} title="Mức độ UV" iconColor="text-yellow-500" borderColor="border-yellow-100">
          <UVBar value={hour.uv_index} />
        </Section>

        {/* 6. Ảnh hưởng đến cây trồng */}
        <Section icon={Leaf} title="Ảnh hưởng đến cây trồng" iconColor="text-emerald-600" borderColor="border-emerald-100">
          <div className="space-y-1.5">
            {impacts.length ? (
              impacts.map((item, i) => (
                <div key={i} className={`flex items-start gap-2 rounded-lg border px-2 py-1.5 text-xs ${levelColor[item.level]}`}>
                  <span className="mt-0.5 shrink-0">{item.level === 'high' ? '⚠' : item.level === 'medium' ? '●' : '✓'}</span>
                  <span>{item.text}</span>
                </div>
              ))
            ) : (
              <p className="rounded-lg border border-dashed border-gray-200 px-2 py-3 text-center text-xs text-gray-500">
                Chưa đủ số đo thời tiết cho giờ này để đưa ra khuyến nghị canh tác.
              </p>
            )}
          </div>
        </Section>

      </div>
    </div>
  );
};

// ── Main page ──────────────────────────────────────────────────────────────────
const ForecastPage = () => {
  const [region, setRegion] = useState('Ha Noi');
  const [cropName, setCropName] = useState('Lúa');
  const [growthStage, setGrowthStage] = useState('Làm đòng');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [staleWarning, setStaleWarning] = useState('');

  // Drill-down state
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedHour, setSelectedHour] = useState(null);
  const [hourlyByDate, setHourlyByDate] = useState({});
  const [loadingHourly, setLoadingHourly] = useState(false);

  const fetchWeather = useCallback(async () => {
    setLoading(true);
    setError('');
    setStaleWarning('');
    setSelectedDate(null);
    setSelectedHour(null);
    setHourlyByDate({});
    try {
      // Fire-and-forget: không await — background refresh không được block trang
      weatherApi.refreshCurrentWeather(region).catch(() => {});
      weatherApi.getForecast(region, 7).catch(() => {});

      const results = await Promise.allSettled([
        weatherApi.getAgricultureWeather({
          region,
          cropName,
          growthStage,
          days: 7,
          includeHourly: true,
        }),
        weatherApi.getRiskAnalysis({ region, cropName }),
        weatherApi.getFarmingRecommendation({ region, cropName }),
      ]);
      const [weatherResult, riskResult, recommendationResult] = results;
      if (weatherResult.status === 'rejected') {
        const err = weatherResult.reason;
        const isTimeout = err?.isTimeout || err?.code === 'ECONNABORTED' ||
          String(err?.message || '').toLowerCase().includes('timeout');
        if (isTimeout) {
          setError('Dữ liệu realtime đang chậm (timeout). Vui lòng thử lại sau ít phút.');
        } else {
          throw err;
        }
        return;
      }
      const result = weatherResult.value;

      // Backend trả success:false (cache miss hoàn toàn, không có cache nào) → báo lỗi rõ
      if (result?.success === false || !result?.current) {
        throw new Error(result?.message || result?.error?.message || 'Không có dữ liệu thời tiết. Vui lòng thử lại.');
      }

      // Phát hiện dữ liệu cũ (stale_emergency hoặc stale_cache) từ current weather
      const currentCacheStatus = result?.current?.cache_status;
      const currentTimeout = result?.current?.timeout;
      const currentWarning = result?.current?.warning;
      if (currentCacheStatus === 'stale_emergency') {
        setStaleWarning(currentWarning || 'Dữ liệu thời tiết đang dùng cache cũ do kết nối chậm. Sẽ tự cập nhật khi có mạng.');
      } else if (currentTimeout) {
        setStaleWarning('Kết nối realtime chậm, một số dữ liệu có thể chưa được cập nhật mới nhất.');
      }

      const riskAnalysis = riskResult.status === 'fulfilled' ? riskResult.value : result.risk_analysis;
      const farmingRecommendation = recommendationResult.status === 'fulfilled'
        ? recommendationResult.value
        : result.farming_recommendation;
      setData({
        ...result,
        risk_analysis: riskAnalysis,
        farming_recommendation: farmingRecommendation,
      });
      if (riskResult.status === 'rejected' || recommendationResult.status === 'rejected') {
        setStaleWarning((prev) =>
          prev
            ? prev
            : 'Một số khối khuyến nghị phản hồi chậm, dự báo chính vẫn hiển thị từ cache.'
        );
      }
    } catch (err) {
      setData(null);
      setError(getApiErrorMessage(err, 'Không thể tải dữ liệu thời tiết nông vụ'));
    } finally {
      setLoading(false);
    }
  }, [cropName, growthStage, region]);

  useEffect(() => { fetchWeather(); }, [fetchWeather]);

  const handleDayClick = async (date) => {
    if (selectedDate === date) {
      setSelectedDate(null);
      setSelectedHour(null);
      return;
    }
    setSelectedDate(date);
    setSelectedHour(null);

    // Use hourly already fetched from agriculture endpoint if available
    if (hourlyByDate[date]) return;

    // Group existing hourly data first
    if (data?.hourly_forecast?.length) {
      const grouped = {};
      for (const h of data.hourly_forecast) {
        const d = h.date || (h.time || '').slice(0, 10);
        if (!grouped[d]) grouped[d] = [];
        grouped[d].push(h);
      }
      if (grouped[date]) {
        setHourlyByDate(prev => ({ ...prev, ...grouped }));
        return;
      }
    }

    // Fetch full 7-day hourly if not cached
    setLoadingHourly(true);
    try {
      const res = await weatherApi.getHourlyForecast(region, 168);
      const grouped = {};
      for (const h of res.forecast || []) {
        const d = h.date || (h.time || '').slice(0, 10);
        if (!grouped[d]) grouped[d] = [];
        grouped[d].push(h);
      }
      setHourlyByDate(grouped);
    } catch {
      // silently ignore
    } finally {
      setLoadingHourly(false);
    }
  };

  const current = data?.current;
  const topActions = useMemo(
    () => (data?.activity_recommendations || []).filter((item) => item.action_type !== 'crop_stage'),
    [data]
  );
  const hoursForDay = selectedDate ? (hourlyByDate[selectedDate] || []) : [];

  const handleSubmit = (event) => {
    event.preventDefault();
    fetchWeather();
  };

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700">
            <CloudSun className="h-4 w-4" />
            Thời tiết nông vụ thông minh
          </div>
          <h1 className="mt-3 text-3xl font-bold text-slate-950">Dự báo thời tiết canh tác</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Theo dõi thời gian thực, dự báo 7 ngày, cảnh báo rủi ro và khuyến nghị tưới, phun thuốc, bón phân, thu hoạch theo cây trồng.
          </p>
        </div>
        {current && (
          <div className="flex flex-wrap items-center gap-2">
            <DataSourceBadge data={current} />
            <span className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600">
              <Clock className="h-4 w-4" />
              {current.last_updated ? new Date(current.last_updated).toLocaleString('vi-VN') : 'Chưa rõ thời gian'}
            </span>
          </div>
        )}
      </div>

      {/* ── Filter form ── */}
      <form onSubmit={handleSubmit} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-4 md:grid-cols-4">
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Khu vực</span>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
            >
              {regions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Cây trồng</span>
            <select
              value={cropName}
              onChange={(e) => setCropName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
            >
              {crops.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Giai đoạn</span>
            <select
              value={growthStage}
              onChange={(e) => setGrowthStage(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
            >
              {stages.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Cập nhật
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>
      )}

      {staleWarning && !error && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <span className="mt-0.5 shrink-0 text-base">⚠</span>
          <span>{staleWarning}</span>
          <button
            type="button"
            onClick={() => setStaleWarning('')}
            className="ml-auto shrink-0 text-amber-600 hover:text-amber-800"
            aria-label="Đóng"
          >✕</button>
        </div>
      )}

      {loading && !data && (
        <div className="flex min-h-[320px] items-center justify-center rounded-lg border border-slate-200 bg-white">
          <div className="text-center text-slate-600">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-emerald-700" />
            <p className="mt-3 text-sm font-medium">Đang tải dữ liệu thời tiết...</p>
          </div>
        </div>
      )}

      {data && current && (
        <>
          {/* ── Current metrics ── */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <WeatherMetric icon={Thermometer} label="Nhiệt độ" value={formatNumber(current.temperature, '°C')}
              detail={current.apparent_temperature != null
                ? `Cảm giác ${formatNumber(current.apparent_temperature, '°C')} · ${formatNumber(current.temp_min, '°C')}–${formatNumber(current.temp_max, '°C')}`
                : `${formatNumber(current.temp_min, '°C')} – ${formatNumber(current.temp_max, '°C')}`}
              tone="rose" />
            <WeatherMetric icon={Droplets} label="Độ ẩm" value={formatNumber(current.humidity, '%', 0)}
              detail="Theo dõi nấm bệnh khi vượt 85%" tone="sky" />
            <WeatherMetric icon={CloudRain} label="Mưa hiện tại" value={formatNumber(current.rainfall, ' mm')}
              detail="Ảnh hưởng tưới tiêu và phun thuốc" tone="emerald" />
            <WeatherMetric icon={Wind} label="Gió" value={formatNumber(current.wind_speed, ' km/h')}
              detail="Không phun thuốc khi vượt 25 km/h" tone="slate" />
            <WeatherMetric icon={Sun} label="UV" value={formatNumber(current.uv_index, '', 1)}
              detail="Che cây non khi UV cao" tone="amber" />
          </div>

          {/* ── AI recommendation + data flow ── */}
          <div className="grid gap-6 xl:grid-cols-3">
            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm xl:col-span-2">
              <div className="flex items-center gap-2 flex-wrap">
                <Bot className="h-5 w-5 text-indigo-600" />
                <h2 className="text-lg font-bold text-slate-950">Khuyến nghị canh tác</h2>
                {data.ai_recommendation?.ai_generated && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700">
                    <Bot className="h-3 w-3" /> AI Gemini
                  </span>
                )}
                <DataSourceBadge data={data.farming_recommendation || data.risk_analysis || {}} />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-700">{translateUiText(data.ai_recommendation.summary)}</p>
              <p className="mt-2 text-sm leading-6 text-slate-700">{translateUiText(data.ai_recommendation.risk_explanation)}</p>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {data.ai_recommendation.action_plan.map((item) => (
                  <div key={item} className="rounded-lg border border-indigo-100 bg-indigo-50 p-3 text-sm leading-6 text-indigo-900">{translateUiText(item)}</div>
                ))}
              </div>
              {data.ai_recommendation.crop_note && (
                <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm leading-6 text-emerald-800">
                  {translateUiText(data.ai_recommendation.crop_note)}
                </div>
              )}
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-emerald-700" />
                <h2 className="text-lg font-bold text-slate-950">Nguồn & xử lý</h2>
              </div>
              <div className="mt-4 space-y-3">
                {(data.data_flow || []).map((item, index) => (
                  <div key={item} className="flex gap-3">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-700">
                      {index + 1}
                    </span>
                    <p className="text-sm leading-6 text-slate-600">{translateUiText(item)}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
                {translateUiText(data.ai_recommendation.data_note)}
              </div>
            </section>
          </div>

          {/* ── Alerts ── */}
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
                <h2 className="text-lg font-bold text-slate-950">Cảnh báo thời tiết nông nghiệp</h2>
              </div>
              <span className="rounded-lg border border-slate-200 px-3 py-1 text-sm font-semibold text-slate-600">
                {data.alerts.length} cảnh báo
              </span>
            </div>
            {data.alerts.length === 0 ? (
              <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm font-medium text-emerald-800">
                <CheckCircle2 className="h-5 w-5" />
                Chưa có cảnh báo lớn trong 7 ngày tới.
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {data.alerts.map((alert) => (
                  <article
                    key={`${alert.alert_type}-${alert.forecast_date}-${alert.title}`}
                    className={`rounded-lg border p-4 ${severityStyles[alert.severity] || severityStyles.medium}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="font-bold">{translateUiText(alert.title)}</h3>
                      <span className="rounded-full bg-white/80 px-2 py-1 text-xs font-semibold">{severityLabel(alert.severity)}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6">{translateUiText(alert.message)}</p>
                    <p className="mt-2 text-sm font-medium leading-6">{translateUiText(alert.recommendation)}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <p className="text-xs font-semibold">{formatDate(alert.forecast_date)}</p>
                      <DataSourceBadge data={alert.source ? alert : (data.risk_analysis || data.farming_recommendation || current)} compact />
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          {/* ── Activity schedule ── */}
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <Sprout className="h-5 w-5 text-emerald-700" />
              <h2 className="text-lg font-bold text-slate-950">Gợi ý lịch canh tác theo thời tiết</h2>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {topActions.map((item) => (
                <article
                  key={item.action_type}
                  className={`rounded-lg border p-4 ${priorityStyles[item.priority] || priorityStyles.medium}`}
                >
                  <h3 className="font-bold">{translateUiText(item.action)}</h3>
                  <p className="mt-2 text-xl font-bold text-slate-950">{translateUiText(item.decision)}</p>
                  <p className="mt-2 text-sm leading-6">{translateUiText(item.reason)}</p>
                  {item.timing && <p className="mt-3 text-xs font-semibold uppercase">{translateUiText(item.timing)}</p>}
                  <div className="mt-3">
                    <DataSourceBadge data={item.source ? item : (data.farming_recommendation || data.risk_analysis || current)} compact />
                  </div>
                </article>
              ))}
            </div>
          </section>

          {/* ── 7-day drill-down ── */}
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <CalendarDays className="h-5 w-5 text-sky-700" />
              <h2 className="text-lg font-bold text-slate-950">Dự báo 7 ngày</h2>
              <span className="ml-auto text-xs text-slate-400">Nhấn vào ngày để xem từng giờ</span>
            </div>

            {/* Day cards row */}
            <div className="overflow-x-auto pb-2">
              <div className="flex gap-2">
                {data.forecast.map((day) => (
                  <DayCard
                    key={day.date}
                    day={day}
                    selected={selectedDate === day.date}
                    onClick={() => handleDayClick(day.date)}
                  />
                ))}
              </div>
            </div>

            {/* 24h hourly drill-down */}
            {selectedDate && (
              <div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <button
                    onClick={() => { setSelectedDate(null); setSelectedHour(null); }}
                    className="p-1 rounded hover:bg-gray-200 transition"
                  >
                    <ChevronLeft className="h-4 w-4 text-gray-500" />
                  </button>
                  <span className="font-semibold text-gray-800 text-sm">
                    {formatDate(selectedDate)} — 24 giờ
                  </span>
                  {loadingHourly && <Loader2 className="h-4 w-4 animate-spin text-sky-500 ml-auto" />}
                </div>

                {hoursForDay.length > 0 ? (
                  <div className="overflow-x-auto pb-1">
                    <div className="flex gap-2">
                      {hoursForDay.map((h) => {
                        const key = h.forecast_at || h.time;
                        return (
                          <HourPill
                            key={key}
                            hour={h}
                            selected={selectedHour === key}
                            onClick={() => setSelectedHour(selectedHour === key ? null : key)}
                          />
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  !loadingHourly && (
                    <p className="text-sm text-gray-400 text-center py-4">Chưa có dữ liệu giờ cho ngày này</p>
                  )
                )}

                {/* Hour detail */}
                {selectedHour && (
                  <HourDetail
                    hour={hoursForDay.find((h) => (h.forecast_at || h.time) === selectedHour)}
                  />
                )}
              </div>
            )}

            {/* Detailed table */}
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-3">Ngày</th>
                    <th className="px-3 py-3">Nhiệt độ</th>
                    <th className="px-3 py-3">Mưa</th>
                    <th className="px-3 py-3">Độ ẩm</th>
                    <th className="px-3 py-3">Gió</th>
                    <th className="px-3 py-3">Khuyến nghị</th>
                    <th className="px-3 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.forecast.map((item) => (
                    <tr
                      key={item.date}
                      onClick={() => handleDayClick(item.date)}
                      className="align-top cursor-pointer hover:bg-emerald-50/40 transition"
                    >
                      <td className="px-3 py-3 font-semibold text-slate-900">
                        {item.day_label || formatDate(item.date)}
                        <span className="block text-xs font-normal text-slate-500">{formatDate(item.date)}</span>
                      </td>
                      <td className="px-3 py-3 text-slate-700">
                        {formatNumber(item.temp_min, '°C')} - {formatNumber(item.temp_max, '°C')}
                      </td>
                      <td className="px-3 py-3 text-slate-700">
                        {formatNumber(item.rainfall, ' mm')}
                        <span className="block text-xs text-slate-500">{formatNumber(item.rain_probability, '%', 0)}</span>
                      </td>
                      <td className="px-3 py-3 text-slate-700">{formatNumber(item.humidity, '%', 0)}</td>
                      <td className="px-3 py-3 text-slate-700">{formatNumber(item.wind_speed, ' km/h')}</td>
                      <td className="max-w-sm px-3 py-3 text-slate-700">{translateUiText(item.recommendation)}</td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <DataSourceBadge data={item} compact />
                          <ChevronDown className={`h-4 w-4 transition-transform ${selectedDate === item.date ? 'rotate-180 text-emerald-600' : 'text-gray-300'}`} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <Clock className="h-5 w-5 text-slate-700" />
              <h2 className="text-lg font-bold text-slate-950">24 giờ tới</h2>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {(data.hourly_forecast || []).slice(0, 8).map((item) => (
                <article key={item.forecast_at || item.time} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-slate-900">{formatTime(item.forecast_at || item.time)}</p>
                    <Umbrella className="h-4 w-4 text-sky-700" />
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{formatNumber(item.temperature, '°C')}</p>
                  <p className="text-sm text-slate-600">{formatNumber(item.humidity, '%', 0)} ẩm</p>
                  <p className="text-sm text-slate-600">{formatNumber(item.rain_probability, '%', 0)} mưa</p>
                  <p className="mt-2 text-xs leading-5 text-slate-500">{translateUiText(item.recommendation)}</p>
                  <div className="mt-2">
                    <DataSourceBadge data={item.source ? item : current} compact />
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
};

export default ForecastPage;
