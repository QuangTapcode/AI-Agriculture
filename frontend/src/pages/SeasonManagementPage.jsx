import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  CloudSun,
  Clock,
  Edit,
  Leaf,
  MapPin,
  Plus,
  RefreshCw,
  Search,
  Sprout,
  Trash2,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { EmptyState, InlineLoading, PageError } from '../components/StatusState';
import { getApiErrorMessage, settledValue } from '../services/api';
import { seasonApi } from '../services/seasonApi';
import { formatConfidence } from '../utils/format';

const statusMeta = {
  planned: { label: 'Đã lên kế hoạch', className: 'border-sky-200 bg-sky-50 text-sky-700' },
  active: { label: 'Đang theo dõi', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  harvesting: { label: 'Đang thu hoạch', className: 'border-amber-200 bg-amber-50 text-amber-700' },
  completed: { label: 'Đã hoàn thành', className: 'border-slate-200 bg-slate-50 text-slate-700' },
  cancelled: { label: 'Đã hủy', className: 'border-rose-200 bg-rose-50 text-rose-700' },
};

const healthMeta = {
  good: { label: 'Tốt', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  warning: { label: 'Cần chú ý', className: 'border-amber-200 bg-amber-50 text-amber-700' },
  risk: { label: 'Rủi ro', className: 'border-rose-200 bg-rose-50 text-rose-700' },
};

const filterOptions = [
  { value: 'all', label: 'Tất cả' },
  { value: 'active', label: 'Đang theo dõi' },
  { value: 'upcoming', label: 'Sắp thu hoạch' },
  { value: 'completed', label: 'Đã hoàn thành' },
  { value: 'risk', label: 'Rủi ro' },
];

const initialForm = {
  crop_name: '',
  region: '',
  farm_name: '',
  area: '',
  area_unit: 'ha',
  start_date: '',
  expected_harvest_date: '',
  status: 'active',
  health_status: 'good',
  note: '',
};

const formatDate = (value) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString('vi-VN');
};

const formatArea = (season) => {
  if (!season.area) return '-';
  const unitLabel = season.area_unit === 'sao' ? 'sào' : season.area_unit;
  return `${Number(season.area).toLocaleString('vi-VN', { maximumFractionDigits: 2 })} ${unitLabel}`;
};

const harvestDistanceText = (season) => {
  if (season.status === 'completed') return 'Đã kết thúc';
  if (season.status === 'cancelled') return 'Đã hủy';
  const days = Number(season.days_until_harvest);
  if (!Number.isFinite(days)) return '-';
  if (days < 0) return `Quá hạn ${Math.abs(days)} ngày`;
  if (days === 0) return 'Thu hoạch hôm nay';
  return `Còn ${days} ngày`;
};

const toDateInput = (value) => {
  if (!value) return '';
  return String(value).slice(0, 10);
};

const validateForm = (form) => {
  if (!form.crop_name.trim()) return 'Tên cây trồng không được rỗng';
  if (!form.region.trim()) return 'Khu vực không được rỗng';
  if (!form.start_date) return 'Vui lòng chọn ngày bắt đầu mùa vụ';
  if (form.expected_harvest_date && new Date(form.expected_harvest_date) <= new Date(form.start_date)) {
    return 'Ngày dự kiến thu hoạch phải sau ngày bắt đầu';
  }
  if (form.area && Number(form.area) <= 0) return 'Diện tích phải là số dương';
  return null;
};

const Badge = ({ meta }) => (
  <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${meta.className}`}>
    {meta.label}
  </span>
);

const StatCard = ({ icon: Icon, label, value, className }) => (
  <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
    <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-lg ${className}`}>
      <Icon className="h-5 w-5" />
    </div>
    <div className="text-sm text-slate-500">{label}</div>
    <div className="mt-1 text-2xl font-bold text-slate-950">{value}</div>
  </div>
);

const SeasonManagementPage = () => {
  const [seasons, setSeasons] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [formError, setFormError] = useState(null);
  const [modalMode, setModalMode] = useState(null);
  const [editingSeason, setEditingSeason] = useState(null);
  const [formData, setFormData] = useState(initialForm);
  const [forecasting, setForecasting] = useState(false);
  const [forecastInfo, setForecastInfo] = useState(null);
  const [forecastError, setForecastError] = useState(null);

  const loadSeasons = async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.allSettled([
        seasonApi.getSeasons(),
        seasonApi.getSeasonSummary(),
      ]);
      const listData = settledValue(results[0], null);
      const summaryData = settledValue(results[1], null);
      if (!listData) throw results[0].reason;
      setSeasons(listData.seasons || []);
      setSummary(summaryData || null);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể tải danh sách mùa vụ'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSeasons();
  }, []);

  const filteredSeasons = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return seasons.filter((season) => {
      const matchesFilter =
        filterStatus === 'all' ||
        (filterStatus === 'active' && ['active', 'harvesting'].includes(season.status)) ||
        (filterStatus === 'upcoming' && season.is_upcoming_harvest) ||
        (filterStatus === 'completed' && season.status === 'completed') ||
        (filterStatus === 'risk' && season.health_status === 'risk');
      const matchesSearch =
        !query ||
        season.crop_name.toLowerCase().includes(query) ||
        season.region.toLowerCase().includes(query) ||
        (season.farm_name || '').toLowerCase().includes(query);
      return matchesFilter && matchesSearch;
    });
  }, [filterStatus, searchQuery, seasons]);

  const localSummary = useMemo(() => ({
    total_seasons: summary?.total_seasons ?? seasons.length,
    active_seasons: summary?.active_seasons ?? seasons.filter((item) => ['active', 'harvesting'].includes(item.status)).length,
    completed_seasons: summary?.completed_seasons ?? seasons.filter((item) => item.status === 'completed').length,
    risk_seasons: summary?.risk_seasons ?? seasons.filter((item) => item.health_status === 'risk').length,
    upcoming_harvest_count: summary?.upcoming_harvest_count ?? seasons.filter((item) => item.is_upcoming_harvest).length,
  }), [seasons, summary]);

  const openCreateModal = () => {
    setEditingSeason(null);
    setFormData(initialForm);
    setFormError(null);
    setForecastInfo(null);
    setForecastError(null);
    setModalMode('create');
  };

  const openEditModal = (season) => {
    setEditingSeason(season);
    setFormData({
      crop_name: season.crop_name || '',
      region: season.region || '',
      farm_name: season.farm_name || '',
      area: season.area ?? '',
      area_unit: season.area_unit || 'ha',
      start_date: toDateInput(season.start_date),
      expected_harvest_date: toDateInput(season.expected_harvest_date),
      status: season.status || 'active',
      health_status: season.health_status || 'good',
      note: season.note || '',
    });
    setFormError(null);
    setForecastInfo(null);
    setForecastError(null);
    setModalMode('edit');
  };

  const closeModal = () => {
    if (saving) return;
    setModalMode(null);
    setEditingSeason(null);
    setFormError(null);
    setForecastInfo(null);
    setForecastError(null);
  };

  const buildPayload = () => ({
    crop_name: formData.crop_name.trim(),
    region: formData.region.trim(),
    farm_name: formData.farm_name.trim() || null,
    area: formData.area ? Number(formData.area) : null,
    area_unit: formData.area_unit,
    start_date: formData.start_date,
    expected_harvest_date: formData.expected_harvest_date || null,
    status: formData.status,
    health_status: formData.health_status,
    note: formData.note.trim() || null,
  });

  const canPredictHarvestDate = Boolean(
    formData.crop_name.trim() &&
    formData.region.trim() &&
    formData.start_date
  );

  const predictExpectedHarvestDate = useCallback(async ({ showError = true } = {}) => {
    const cropName = formData.crop_name.trim();
    const region = formData.region.trim();
    const startDate = formData.start_date;
    if (!cropName || !region || !startDate) {
      if (showError) setForecastError('Nhập tên cây trồng, khu vực và ngày bắt đầu để tính ngày thu hoạch');
      return;
    }

    setForecasting(true);
    setForecastError(null);
    try {
      const estimate = await seasonApi.predictHarvestDate({
        crop_name: cropName,
        region,
        start_date: startDate,
      });
      setForecastInfo(estimate);
      setFormData((current) => {
        if (
          current.crop_name.trim() !== cropName ||
          current.region.trim() !== region ||
          current.start_date !== startDate
        ) {
          return current;
        }
        return {
          ...current,
          expected_harvest_date: toDateInput(estimate.expected_harvest_date),
        };
      });
    } catch (err) {
      const message = getApiErrorMessage(err, 'Không thể tính ngày thu hoạch dự kiến');
      if (showError) setForecastError(message);
    } finally {
      setForecasting(false);
    }
  }, [formData.crop_name, formData.region, formData.start_date]);

  useEffect(() => {
    if (modalMode && !canPredictHarvestDate) {
      setForecastInfo(null);
      setForecastError(null);
    }
  }, [canPredictHarvestDate, modalMode]);

  useEffect(() => {
    if (modalMode !== 'create' || !canPredictHarvestDate) return undefined;
    const timer = window.setTimeout(() => {
      predictExpectedHarvestDate({ showError: false });
    }, 500);
    return () => window.clearTimeout(timer);
  }, [canPredictHarvestDate, modalMode, predictExpectedHarvestDate]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const validationMessage = validateForm(formData);
    if (validationMessage) {
      setFormError(validationMessage);
      return;
    }

    setSaving(true);
    setFormError(null);
    setError(null);
    try {
      const payload = buildPayload();
      if (modalMode === 'edit' && editingSeason) {
        await seasonApi.updateSeason(editingSeason.id, payload);
      } else {
        await seasonApi.createSeason(payload);
      }
      closeModal();
      await loadSeasons();
    } catch (err) {
      setFormError(getApiErrorMessage(err, 'Không thể lưu mùa vụ'));
    } finally {
      setSaving(false);
    }
  };

  const handleComplete = async (season) => {
    setError(null);
    try {
      await seasonApi.completeSeason(season.id);
      await loadSeasons();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể kết thúc mùa vụ'));
    }
  };

  const handleDelete = async (season) => {
    const confirmed = window.confirm(`Xóa mùa vụ ${season.crop_name}?`);
    if (!confirmed) return;
    setError(null);
    try {
      await seasonApi.deleteSeason(season.id);
      await loadSeasons();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể xóa mùa vụ'));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-emerald-700">Season management</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-950">Quản lý mùa vụ</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Theo dõi cây trồng, khu vực, lịch thu hoạch và tình trạng rủi ro của từng ruộng/vườn.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreateModal}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-700 px-5 py-3 font-semibold text-white shadow-sm hover:bg-emerald-800"
        >
          <Plus className="h-5 w-5" />
          Thêm mùa vụ
        </button>
      </div>

      {error && <PageError message={error} onRetry={loadSeasons} />}
      {loading && <InlineLoading text="Đang tải mùa vụ từ database..." />}

      {!loading && (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <StatCard icon={Sprout} label="Tổng mùa vụ" value={localSummary.total_seasons} className="bg-slate-100 text-slate-700" />
            <StatCard icon={Leaf} label="Đang theo dõi" value={localSummary.active_seasons} className="bg-emerald-50 text-emerald-700" />
            <StatCard icon={Clock} label="Sắp thu hoạch" value={localSummary.upcoming_harvest_count} className="bg-amber-50 text-amber-700" />
            <StatCard icon={CheckCircle2} label="Đã hoàn thành" value={localSummary.completed_seasons} className="bg-sky-50 text-sky-700" />
            <StatCard icon={AlertTriangle} label="Rủi ro" value={localSummary.risk_seasons} className="bg-rose-50 text-rose-700" />
          </div>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="relative w-full xl:max-w-md">
                <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Tìm theo cây trồng, khu vực hoặc tên ruộng/vườn..."
                  className="w-full rounded-lg border border-slate-300 py-3 pl-10 pr-4 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {filterOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setFilterStatus(option.value)}
                    className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                      filterStatus === option.value
                        ? 'bg-emerald-700 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </section>

          {filteredSeasons.length ? (
            <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
              {filteredSeasons.map((season) => (
                <article key={season.id} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm font-medium text-emerald-700">
                        <Sprout className="h-4 w-4" />
                        {season.crop_name}
                      </div>
                      <h2 className="mt-1 truncate text-xl font-bold text-slate-950">{season.crop_name}</h2>
                      <p className="mt-1 flex items-center gap-2 text-sm text-slate-600">
                        <MapPin className="h-4 w-4 shrink-0" />
                        <span className="truncate">{season.region}</span>
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2">
                      <Badge meta={statusMeta[season.status] || statusMeta.active} />
                      <Badge meta={healthMeta[season.health_status] || healthMeta.good} />
                    </div>
                  </div>

                  <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-md bg-slate-50 p-3">
                      <div className="text-slate-500">Ruộng/vườn</div>
                      <div className="mt-1 font-semibold text-slate-950">{season.farm_name || '-'}</div>
                    </div>
                    <div className="rounded-md bg-slate-50 p-3">
                      <div className="text-slate-500">Diện tích</div>
                      <div className="mt-1 font-semibold text-slate-950">{formatArea(season)}</div>
                    </div>
                    <div className="rounded-md bg-slate-50 p-3">
                      <div className="text-slate-500">Ngày bắt đầu</div>
                      <div className="mt-1 font-semibold text-slate-950">{formatDate(season.start_date)}</div>
                    </div>
                    <div className="rounded-md bg-slate-50 p-3">
                      <div className="text-slate-500">Dự kiến thu hoạch</div>
                      <div className="mt-1 font-semibold text-slate-950">{formatDate(season.expected_harvest_date)}</div>
                    </div>
                  </div>

                  <div className="mt-4 rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                    <div className="flex items-center gap-2 font-semibold">
                      <CalendarDays className="h-4 w-4" />
                      {harvestDistanceText(season)}
                    </div>
                    {season.note && <p className="mt-2 leading-6 text-emerald-800">{season.note}</p>}
                  </div>

                  <div className="mt-5 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => openEditModal(season)}
                      className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      <Edit className="h-4 w-4" />
                      Sửa
                    </button>
                    {season.status !== 'completed' && season.status !== 'cancelled' && (
                      <button
                        type="button"
                        onClick={() => handleComplete(season)}
                        className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-emerald-200 px-3 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-50"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Kết thúc
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDelete(season)}
                      className="inline-flex items-center justify-center gap-2 rounded-lg border border-rose-200 px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50"
                    >
                      <Trash2 className="h-4 w-4" />
                      Xóa
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title={seasons.length ? 'Không tìm thấy mùa vụ phù hợp' : 'Chưa có mùa vụ'}
              description={seasons.length ? 'Thử đổi bộ lọc hoặc từ khóa tìm kiếm.' : 'Tạo mùa vụ đầu tiên để bảng điều khiển hiển thị số liệu đang theo dõi.'}
              action={
                !seasons.length && (
                  <button
                    type="button"
                    onClick={openCreateModal}
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-700 px-5 py-3 font-semibold text-white hover:bg-emerald-800"
                  >
                    <Plus className="h-5 w-5" />
                    Thêm mùa vụ đầu tiên
                  </button>
                )
              }
            />
          )}
        </>
      )}

      {modalMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <form onSubmit={handleSubmit} className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-slate-950">{modalMode === 'edit' ? 'Sửa mùa vụ' : 'Thêm mùa vụ'}</h2>
                <p className="mt-1 text-sm text-slate-500">Cập nhật thông tin canh tác và trạng thái theo dõi.</p>
              </div>
              <button type="button" onClick={closeModal} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Đóng">
                <X className="h-5 w-5" />
              </button>
            </div>

            {formError && (
              <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {formError}
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Tên cây trồng</span>
                <input
                  value={formData.crop_name}
                  onChange={(event) => setFormData((current) => ({ ...current, crop_name: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Khu vực</span>
                <input
                  value={formData.region}
                  onChange={(event) => setFormData((current) => ({ ...current, region: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Tên ruộng/vườn</span>
                <input
                  value={formData.farm_name}
                  onChange={(event) => setFormData((current) => ({ ...current, farm_name: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                />
              </label>
              <div className="grid grid-cols-[1fr_7rem] gap-3">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">Diện tích</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={formData.area}
                    onChange={(event) => setFormData((current) => ({ ...current, area: event.target.value }))}
                    className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-700">Đơn vị</span>
                  <select
                    value={formData.area_unit}
                    onChange={(event) => setFormData((current) => ({ ...current, area_unit: event.target.value }))}
                    className="w-full rounded-lg border border-slate-300 px-3 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                  >
                    <option value="ha">ha</option>
                    <option value="m2">m2</option>
                    <option value="sao">sào</option>
                  </select>
                </label>
              </div>
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Ngày xuống giống / bắt đầu</span>
                <input
                  type="date"
                  value={formData.start_date}
                  onChange={(event) => setFormData((current) => ({ ...current, start_date: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                />
              </label>
              <div className="block">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="block text-sm font-medium text-slate-700">Ngày dự kiến thu hoạch</span>
                  <button
                    type="button"
                    onClick={() => predictExpectedHarvestDate()}
                    disabled={!canPredictHarvestDate || forecasting}
                    className="inline-flex items-center gap-1.5 rounded-md border border-emerald-200 px-2.5 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${forecasting ? 'animate-spin' : ''}`} />
                    Tính lại
                  </button>
                </div>
                <input
                  type="date"
                  value={formData.expected_harvest_date}
                  onChange={(event) => setFormData((current) => ({ ...current, expected_harvest_date: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                />
                {forecasting && (
                  <p className="mt-2 flex items-center gap-2 text-xs font-medium text-emerald-700">
                    <CloudSun className="h-4 w-4" />
                    Đang tính theo thời tiết và thời gian sinh trưởng...
                  </p>
                )}
                {!forecasting && forecastInfo && (
                  <div className="mt-2 rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-800">
                    <div className="font-semibold">
                      Độ tin cậy {formatConfidence(forecastInfo.confidence)}
                      {forecastInfo.weather_risk ? ` · Rủi ro thời tiết ${forecastInfo.weather_risk}` : ''}
                    </div>
                    {forecastInfo.warning && <div className="mt-1">{forecastInfo.warning}</div>}
                  </div>
                )}
                {forecastError && <p className="mt-2 text-xs font-medium text-rose-600">{forecastError}</p>}
              </div>
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Trạng thái</span>
                <select
                  value={formData.status}
                  onChange={(event) => setFormData((current) => ({ ...current, status: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                >
                  {Object.entries(statusMeta).map(([value, meta]) => (
                    <option key={value} value={value}>{meta.label}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Tình trạng</span>
                <select
                  value={formData.health_status}
                  onChange={(event) => setFormData((current) => ({ ...current, health_status: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                >
                  {Object.entries(healthMeta).map(([value, meta]) => (
                    <option key={value} value={value}>{meta.label}</option>
                  ))}
                </select>
              </label>
              <label className="block md:col-span-2">
                <span className="mb-2 block text-sm font-medium text-slate-700">Ghi chú</span>
                <textarea
                  rows={3}
                  value={formData.note}
                  onChange={(event) => setFormData((current) => ({ ...current, note: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                />
              </label>
            </div>

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={closeModal}
                className="rounded-lg border border-slate-300 px-5 py-3 font-semibold text-slate-700 hover:bg-slate-50"
              >
                Hủy
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-emerald-700 px-5 py-3 font-semibold text-white hover:bg-emerald-800 disabled:opacity-60"
              >
                {saving ? 'Đang lưu...' : 'Lưu mùa vụ'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default SeasonManagementPage;
