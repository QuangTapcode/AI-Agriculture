import { AlertCircle, Calendar, TrendingUp } from 'lucide-react';
import { useState } from 'react';
import { formatConfidence, hasValue } from '../utils/format';
import DataSourceBadge from '../components/DataSourceBadge';
import { getApiErrorMessage } from '../services/api';
import { harvestApi } from '../services/harvestApi';
import { translateUiText } from '../utils/vietnameseText';

const cropOptions = [
  { value: 'ca chua', label: 'Cà chua' },
  { value: 'dua chuot', label: 'Dưa chuột' },
  { value: 'rau muong', label: 'Rau muống' },
  { value: 'cai xanh', label: 'Cải xanh' },
  { value: 'ot', label: 'Ớt' },
  { value: 'lua', label: 'Lúa' },
];

const regionOptions = [
  { value: 'Ha Noi', label: 'Hà Nội' },
  { value: 'TP.HCM', label: 'TP.HCM' },
  { value: 'Da Nang', label: 'Đà Nẵng' },
  { value: 'Can Tho', label: 'Cần Thơ' },
  { value: 'Hai Phong', label: 'Hải Phòng' },
];

const dateDiffDays = (start, end) => {
  if (!start || !end) return 0;
  return Math.round((new Date(end) - new Date(start)) / (1000 * 60 * 60 * 24));
};

const HarvestPage = () => {
  const [formData, setFormData] = useState({
    crop: 'ca chua',
    region: 'Ha Noi',
    plantingDate: '',
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await harvestApi.optimizeHarvest(
        formData.crop,
        formData.plantingDate,
        formData.region
      );
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(getApiErrorMessage(err, 'Không thể dự báo thu hoạch'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="px-4 py-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dự báo thu hoạch</h1>
        <p className="mt-2 text-gray-600">
          Dự đoán thời điểm thu hoạch tối ưu từ dữ liệu hệ thống.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Thông tin cây trồng</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="harvest-crop" className="mb-2 block text-sm font-medium text-gray-700">
                Loại cây trồng
              </label>
              <select
                id="harvest-crop"
                value={formData.crop}
                onChange={(e) => setFormData({ ...formData, crop: e.target.value })}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {cropOptions.map((crop) => (
                  <option key={crop.value} value={crop.value}>
                    {crop.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="harvest-region" className="mb-2 block text-sm font-medium text-gray-700">
                Khu vực
              </label>
              <select
                id="harvest-region"
                value={formData.region}
                onChange={(e) => setFormData({ ...formData, region: e.target.value })}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {regionOptions.map((region) => (
                  <option key={region.value} value={region.value}>
                    {region.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="harvest-planting-date" className="mb-2 block text-sm font-medium text-gray-700">
                Ngày xuống giống
              </label>
              <input
                id="harvest-planting-date"
                type="date"
                value={formData.plantingDate}
                onChange={(e) => setFormData({ ...formData, plantingDate: e.target.value })}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
                <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-700 text-white py-2 px-4 rounded-md hover:bg-primary-800 disabled:bg-gray-300"
            >
              {loading ? 'Đang dự báo...' : 'Dự báo thu hoạch'}
            </button>
          </form>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Kết quả dự báo</h2>

          {result ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3">
                <DataSourceBadge data={result} />
                {result.fetched_at && (
                  <span className="text-xs text-gray-500">
                    Cập nhật {new Date(result.fetched_at).toLocaleString('vi-VN')}
                  </span>
                )}
                {hasValue(result.confidence) && (
                  <span className="text-xs font-semibold text-gray-600">
                    Độ tin cậy {formatConfidence(result.confidence)}
                  </span>
                )}
              </div>
              <div className="border rounded-lg p-4">
                <div className="flex items-center mb-2">
                  <Calendar className="h-5 w-5 text-primary-600 mr-2" />
                  <span className="text-sm font-medium text-gray-700">
                    Ngày thu hoạch dự kiến
                  </span>
                </div>
                <p className="text-2xl font-bold text-gray-900">
                  {new Date(result.expected_harvest_date).toLocaleDateString('vi-VN')}
                </p>
                <p className="text-sm text-gray-600 mt-1">
                  Sau {dateDiffDays(result.planting_date, result.expected_harvest_date)} ngày kể từ ngày xuống giống
                </p>
              </div>

              <div className="border rounded-lg p-4">
                <div className="flex items-center mb-2">
                  <TrendingUp className="h-5 w-5 text-green-600 mr-2" />
                  <span className="text-sm font-medium text-gray-700">Độ tin cậy</span>
                </div>
                <p data-testid="harvest-confidence" className="text-2xl font-bold text-gray-900">
                  {formatConfidence(result.confidence)}
                </p>
              </div>

              {(result.warning || result.recommendation) && (
                <div className="bg-blue-50 rounded-lg p-4">
                  {result.warning && (
                    <p className="text-sm text-blue-900 mb-2">{translateUiText(result.warning)}</p>
                  )}
                  <p className="text-sm text-blue-800">{translateUiText(result.recommendation)}</p>
                </div>
              )}
              {(result.earliest_harvest_date || result.latest_harvest_date) && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
                    <p className="text-xs font-semibold text-emerald-700">Sớm nhất</p>
                    <p className="mt-1 font-bold text-gray-900">{new Date(result.earliest_harvest_date).toLocaleDateString('vi-VN')}</p>
                  </div>
                  <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
                    <p className="text-xs font-semibold text-blue-700">Tối ưu</p>
                    <p className="mt-1 font-bold text-gray-900">{new Date(result.optimal_harvest_date || result.expected_harvest_date).toLocaleDateString('vi-VN')}</p>
                  </div>
                  <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                    <p className="text-xs font-semibold text-amber-700">Muộn nhất</p>
                    <p className="mt-1 font-bold text-gray-900">{new Date(result.latest_harvest_date).toLocaleDateString('vi-VN')}</p>
                  </div>
                </div>
              )}
              {(result.weather_risk || result.market_condition) && (
                <div className="rounded-lg border border-gray-200 p-4">
                  <p className="text-sm font-semibold text-gray-700">Yếu tố rủi ro AI</p>
                  <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <span className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">Thời tiết: {translateUiText(result.weather_risk)}</span>
                    <span className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">Thị trường: {translateUiText(result.market_condition)}</span>
                  </div>
                </div>
              )}
              {result.preparation_tasks?.length > 0 && (
                <div className="rounded-lg border border-gray-200 p-4">
                  <p className="text-sm font-semibold text-gray-700">Việc cần chuẩn bị</p>
                  <div className="mt-2 space-y-2">
                    {result.preparation_tasks.map((task) => (
                      <label key={task} className="flex items-start gap-2 text-sm text-gray-700">
                        <input type="checkbox" className="mt-1 rounded border-gray-300" />
                        <span>{translateUiText(task)}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-12">
              <Calendar className="mx-auto h-12 w-12 text-gray-400 mb-4" />
              <p>Nhập thông tin để dự báo thu hoạch</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default HarvestPage;
