import { CloudSun, History, MailCheck, Trash2, TrendingDown, TrendingUp } from 'lucide-react';
import { formatNumber } from '../../utils/format';
import { useEffect, useState } from 'react';
import { alertApi } from '../../services/alertApi';
import { getApiErrorMessage } from '../../services/api';
import { severityLabel, statusLabel as systemStatusLabel, translateUiText } from '../../utils/vietnameseText';
import DataSourceBadge from '../DataSourceBadge';
import { EmptyState, InlineLoading, PageError } from '../StatusState';

const formatCurrency = (value) => Number(value || 0).toLocaleString('vi-VN');
const formatDate = (value) => (value ? new Date(value).toLocaleString('vi-VN') : 'Chưa kích hoạt');

const statusClass = (status) => {
  if (['sent', 'stored'].includes(status)) return 'bg-green-100 text-green-800';
  if (['failed', 'error'].includes(status)) return 'bg-red-100 text-red-700';
  if (['pending'].includes(status)) return 'bg-amber-100 text-amber-800';
  return 'bg-gray-100 text-gray-600';
};

const channelLabel = (channel) => ({
  email: 'Email',
  app: 'Ứng dụng',
  sms: 'SMS',
  zalo: 'Zalo',
}[channel] || channel || 'Ứng dụng');

const statusLabel = (status) => ({
  sent: 'đã gửi',
  stored: 'đã lưu',
  mock_sent: 'chưa gửi realtime',
  failed: 'lỗi gửi',
  error: 'lỗi gửi',
  pending: 'đang chờ',
}[status] || status || 'đã lưu');

const deliveryError = (message) => {
  if (message === 'SMTP is not configured') return 'SMTP chưa cấu hình nên chưa gửi Gmail thật.';
  return message;
};

const weatherConditionLabel = (condition) => ({
  rainfall: 'Mưa lớn',
  temperature: 'Nhiệt độ cao',
  wind: 'Gió mạnh',
  humidity: 'Độ ẩm cao',
  air_quality: 'Chỉ số UV cao',
}[condition] || 'Cảnh báo thời tiết');

const AlertHistory = ({ refreshKey = 0 }) => {
  const [alerts, setAlerts] = useState([]);
  const [triggers, setTriggers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadAlerts = async () => {
    setLoading(true);
    setError(null);

    try {
      const results = await Promise.allSettled([
        alertApi.getAlerts(),
        alertApi.getTriggers(),
      ]);
      const [alertData, triggerData] = results.map((item) => (
        item.status === 'fulfilled' ? item.value : null
      ));
      if (results.every((item) => item.status === 'rejected')) {
        throw results[0].reason;
      }
      setAlerts(alertData?.alerts || []);
      setTriggers(triggerData?.events || []);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể tải danh sách cảnh báo'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
  }, [refreshKey]);

  const handleDeactivate = async (alertId) => {
    try {
      await alertApi.deactivate(alertId);
      await loadAlerts();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể tắt cảnh báo'));
    }
  };

  const handleDeactivateAlert = async (alert) => {
    try {
      if (alert.alert_kind === 'weather' || alert.rule_type === 'weather_threshold') {
        await alertApi.deactivateWeather(alert.alert_id);
      } else {
        await alertApi.deactivate(alert.alert_id);
      }
      await loadAlerts();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể tắt cảnh báo'));
    }
  };

  return (
    <section className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-900">Cảnh báo đang hoạt động</h2>
        <p className="mt-1 text-sm text-gray-600">
          Theo dõi gói cảnh báo, lần kích hoạt gần nhất và trạng thái gửi qua từng kênh.
        </p>
        <div className="mt-3">
          <DataSourceBadge data={{ source: 'database', source_name: 'Quy tắc cảnh báo', confidence: 0.7 }} />
        </div>
      </div>

      <div className="space-y-6 p-5">
        {error && <PageError message={error} onRetry={loadAlerts} />}
        {loading && <InlineLoading text="Đang tải cảnh báo..." />}

        {!loading && !error && alerts.length === 0 && (
          <EmptyState
            title="Chưa có cảnh báo"
            description="Tạo cảnh báo mới để theo dõi biến động giá theo nông sản và khu vực."
          />
        )}

        {!loading && !error && alerts.length > 0 && (
          <div className="divide-y divide-gray-200 overflow-hidden rounded-lg border border-gray-200">
            {alerts.map((alert) => (
              <div key={`${alert.alert_kind || 'price'}-${alert.alert_id}`} className="bg-white p-4 hover:bg-gray-50">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                  <div className="flex items-start gap-3 sm:flex-1">
                    {alert.alert_kind === 'weather' || alert.rule_type === 'weather_threshold' ? (
                      <CloudSun className="mt-1 h-6 w-6 shrink-0 text-blue-600" />
                    ) : alert.condition === 'above' ? (
                      <TrendingUp className="mt-1 h-6 w-6 shrink-0 text-green-600" />
                    ) : (
                      <TrendingDown className="mt-1 h-6 w-6 shrink-0 text-red-600" />
                    )}
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900">
                        {alert.alert_kind === 'weather' || alert.rule_type === 'weather_threshold'
                          ? `${weatherConditionLabel(alert.weather_condition || alert.condition)} · ${alert.region}`
                          : `${alert.crop_name} · ${alert.region}`}
                      </p>
                      <p className="mt-1 text-sm text-gray-600">
                        {alert.alert_kind === 'weather' || alert.rule_type === 'weather_threshold'
                          ? `Ngưỡng ${formatNumber(alert.target_price)} ${alert.trigger_unit || ''} qua ${channelLabel(alert.notification_channel)}`
                          : `${alert.condition === 'above' ? 'Giá trên' : 'Giá dưới'} ${formatCurrency(alert.target_price)} VND/kg qua ${channelLabel(alert.notification_channel)}`}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-600">
                        <span className="rounded-full bg-gray-100 px-2.5 py-1 font-medium text-gray-700">
                          Mức độ: {severityLabel(alert.severity || alert.priority)}
                        </span>
                        <span>Nông sản: {alert.affected_crop || alert.crop_name || 'N/A'}</span>
                        <span>Kênh gửi: {(alert.send_channels || [alert.notification_channel || 'app']).map(channelLabel).join(', ')}</span>
                        {alert.confidence !== undefined && <span>Độ tin cậy: {Math.round(Number(alert.confidence || 0) * 100)}%</span>}
                        {alert.sent_status && <span>Trạng thái gửi: {systemStatusLabel(alert.sent_status)}</span>}
                        <DataSourceBadge data={alert} />
                      </div>
                      {(alert.recommended_action || alert.suggested_action || alert.recommendation) && (
                        <p className="mt-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800">
                          Khuyến nghị: {translateUiText(alert.recommended_action || alert.suggested_action || alert.recommendation)}
                        </p>
                      )}
                      <p className="mt-1 text-xs text-gray-500">
                        Tạo: {formatDate(alert.created_at)} · Kích hoạt gần nhất: {formatDate(alert.last_triggered_at)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-3 sm:justify-end">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                        alert.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {alert.is_active ? 'Đang bật' : 'Đã tắt'}
                    </span>
                    {alert.is_active && (
                      <button
                        type="button"
                        onClick={() => handleDeactivateAlert(alert)}
                        className="rounded-lg p-2 text-gray-400 hover:bg-red-50 hover:text-red-600"
                        title="Tắt cảnh báo"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && !error && (
          <div>
            <div className="mb-3 flex items-center gap-2">
              <History className="h-5 w-5 text-blue-600" />
              <h3 className="font-semibold text-gray-900">Lịch sử kích hoạt</h3>
            </div>
            {triggers.length ? (
              <div className="space-y-3">
                {triggers.map((event) => (
                  <div key={event.event_id} className="rounded-lg border border-gray-200 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-medium text-gray-900">
                          {event.alert_kind === 'weather'
                            ? `${weatherConditionLabel(event.weather_condition || event.condition)} · ${event.region}`
                            : `${event.crop_name} · ${event.region}`}
                        </div>
                        <div className="mt-1 text-sm text-gray-600">
                          {event.alert_kind === 'weather'
                            ? `Giá trị ${formatNumber(event.current_price)} ${event.trigger_unit || ''}, ngưỡng ${formatNumber(event.target_price)} ${event.trigger_unit || ''}`
                            : `Giá thực tế ${formatCurrency(event.current_price)} VND/kg, ngưỡng ${formatCurrency(event.target_price)} VND/kg`}
                        </div>
                        <div className="mt-1 text-xs text-gray-500">{formatDate(event.triggered_at)}</div>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusClass(event.status)}`}>
                        {channelLabel(event.channel)}: {statusLabel(event.status)}
                      </span>
                    </div>
                    <div className="mt-3 flex items-start gap-2 rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                      <MailCheck className="mt-0.5 h-4 w-4 text-gray-500" />
                      <div>
                        {event.message}
                        {event.error_message && <div className="mt-1 text-red-600">{deliveryError(event.error_message)}</div>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-gray-300 p-4 text-sm text-gray-600">
                Chưa có lịch sử kích hoạt. Dùng nút “Kiểm tra ngay” để quét cảnh báo thử.
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
};

export default AlertHistory;
