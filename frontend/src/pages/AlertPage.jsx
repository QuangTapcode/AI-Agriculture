import { CloudSun, PlayCircle, TrendingUp } from 'lucide-react';
import { useState } from 'react';
import AlertHistory from '../components/Alert/AlertHistory';
import AlertSubscribe from '../components/Alert/AlertSubscribe';
import DataSourceBadge from '../components/DataSourceBadge';
import { alertApi } from '../services/alertApi';
import { getApiErrorMessage } from '../services/api';
import { formatNumber, hasValue } from '../utils/format';
import { translateUiText } from '../utils/vietnameseText';

const tabs = [
  { value: 'price', label: 'Cảnh báo giá', icon: TrendingUp },
  { value: 'weather', label: 'Cảnh báo thời tiết', icon: CloudSun },
];

const AlertPage = () => {
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeTab, setActiveTab] = useState('price');
  const [checkState, setCheckState] = useState({ loading: false, message: '', error: '' });
  const [autoAlert, setAutoAlert] = useState(null);

  const handleCheckNow = async () => {
    setCheckState({ loading: true, message: '', error: '' });
    try {
      const result = await alertApi.checkNow();
      setCheckState({
        loading: false,
        // Chỉ nêu con số khi backend thực sự báo về; không mặc định "đã quét 0".
        message: hasValue(result?.triggered_count)
          ? `Đã quét ${formatNumber(result.triggered_count)} cảnh báo, ${formatNumber(result.triggered?.length ?? 0)} lượt được kích hoạt.`
          : 'Đã chạy kiểm tra cảnh báo. Hệ thống chưa trả về số lượng đã quét.',
        error: '',
      });
      setRefreshKey((value) => value + 1);
    } catch (err) {
      setCheckState({ loading: false, message: '', error: getApiErrorMessage(err, 'Không thể kiểm tra cảnh báo') });
    }
  };

  const handleAutoGenerate = async () => {
    setCheckState({ loading: true, message: '', error: '' });
    try {
      const result = await alertApi.autoGenerate({
        alertType: activeTab === 'weather' ? 'weather' : 'price',
        cropName: 'lua',
        region: 'Ha Noi',
      });
      setAutoAlert(result);
      setCheckState({
        loading: false,
        message: translateUiText(result.title || 'AI đã tạo gợi ý cảnh báo tự động.'),
        error: '',
      });
    } catch (err) {
      setCheckState({ loading: false, message: '', error: getApiErrorMessage(err, 'Không thể tạo cảnh báo AI') });
    }
  };

  return (
    <div className="space-y-6 px-4 py-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold uppercase tracking-wide text-green-700">Bộ cảnh báo</p>
            {/* Chỉ gắn badge nguồn khi đã có phản hồi thật; không dựng metadata thay backend. */}
            {autoAlert && <DataSourceBadge data={autoAlert} />}
          </div>
          <h1 className="mt-2 text-3xl font-bold text-gray-900">Trung tâm cảnh báo</h1>
          <p className="mt-2 max-w-3xl text-gray-600">
            Tạo cảnh báo giá và thời tiết từ dữ liệu hệ thống, kiểm tra nhanh và gửi thông báo vào hộp tin.
          </p>
        </div>
        <button
          type="button"
          onClick={handleCheckNow}
          disabled={checkState.loading}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-green-700 px-4 py-3 font-semibold text-white hover:bg-green-800 disabled:opacity-60"
        >
          <PlayCircle className="h-5 w-5" />
          {checkState.loading ? 'Đang kiểm tra...' : 'Kiểm tra ngay'}
        </button>
        <button
          type="button"
          onClick={handleAutoGenerate}
          disabled={checkState.loading}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-green-700 px-4 py-3 font-semibold text-green-800 hover:bg-green-50 disabled:opacity-60"
        >
          AI tạo gợi ý
        </button>
      </div>

      {(checkState.message || checkState.error) && (
        <div
          className={`rounded-lg border p-4 text-sm ${
            checkState.error ? 'border-red-200 bg-red-50 text-red-700' : 'border-green-200 bg-green-50 text-green-800'
          }`}
        >
          {checkState.error || checkState.message}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${
                activeTab === tab.value
                  ? 'bg-green-700 text-white'
                  : 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,520px)_1fr]">
        <AlertSubscribe mode={activeTab} onCreated={() => setRefreshKey((value) => value + 1)} />
        <AlertHistory refreshKey={refreshKey} />
      </div>
    </div>
  );
};

export default AlertPage;
