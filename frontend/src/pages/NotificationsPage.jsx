import {
  Bell,
  CheckCheck,
  ChevronRight,
  CloudSun,
  Filter,
  LineChart,
  RefreshCcw,
  ShieldAlert,
  Sprout,
  Trash2,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { formatNumber } from '../utils/format';
import DataSourceBadge from '../components/DataSourceBadge';
import { EmptyState, InlineLoading, PageError } from '../components/StatusState';
import { getApiErrorMessage } from '../services/api';
import { notificationsApi } from '../services/notificationsApi';
import { statusLabel as systemStatusLabel, translateUiText } from '../utils/vietnameseText';

const baseFilters = [
  { value: 'all', label: 'Tất cả' },
  { value: 'unread', label: 'Chưa đọc' },
  { value: 'important', label: 'Quan trọng' },
  { value: 'price', label: 'Giá' },
  { value: 'weather', label: 'Thời tiết' },
  { value: 'air_quality', label: 'Không khí' },
  { value: 'harvest', label: 'Mùa vụ' },
  { value: 'delivery_failed', label: 'Gửi lỗi' },
  { value: 'system', label: 'Hệ thống' },
];

const iconMap = {
  price: { icon: LineChart, color: 'text-green-700 bg-green-50' },
  weather: { icon: CloudSun, color: 'text-amber-700 bg-amber-50' },
  air_quality: { icon: CloudSun, color: 'text-cyan-700 bg-cyan-50' },
  harvest: { icon: Sprout, color: 'text-blue-700 bg-blue-50' },
  delivery_failed: { icon: ShieldAlert, color: 'text-red-700 bg-red-50' },
  system: { icon: ShieldAlert, color: 'text-gray-700 bg-gray-100' },
};

const formatTime = (value) => {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('vi-VN');
};

const normalizeNotification = (item) => ({
  id: item.notification_id,
  type: item.type || 'system',
  title: item.title,
  description: item.message,
  createdAt: item.created_at,
  time: formatTime(item.created_at),
  read: Boolean(item.is_read),
  priority: item.priority || 'medium',
  channel: item.channel || 'app',
  relatedEntityType: item.related_entity_type,
  relatedEntityId: item.related_entity_id,
  relatedAlertId: item.related_alert_id,
  source: item.source,
  source_name: item.source_name,
  fetched_at: item.fetched_at,
  updated_at: item.updated_at || item.created_at,
  confidence: item.confidence,
  actionRequired: item.action_required,
  suggestedAction: item.suggested_action,
});

const deliveryClass = (status) => {
  if (['sent', 'stored'].includes(status)) return 'bg-green-100 text-green-800';
  if (['failed', 'error'].includes(status)) return 'bg-red-100 text-red-700';
  if (status === 'mock_sent') return 'bg-red-100 text-red-700';
  if (status === 'pending') return 'bg-amber-100 text-amber-800';
  return 'bg-gray-100 text-gray-700';
};

const priorityLabel = (priority) => ({
  high: 'Cao',
  medium: 'Trung bình',
  low: 'Thấp',
  urgent: 'Khẩn cấp',
}[priority] || 'Không rõ');

const streamStatusLabel = (status) => ({
  connected: 'Đã kết nối',
  reconnecting: 'Đang kết nối lại',
  offline: 'Ngoại tuyến',
  connecting: 'Đang kết nối',
}[status] || 'Chưa rõ');

const channelLabel = (channel) => ({
  app: 'Ứng dụng',
  email: 'Email',
  zalo: 'Zalo',
  sms: 'SMS',
}[channel] || translateUiText(channel, 'Kênh gửi'));

const entityTypeLabel = (type) => ({
  price_alert: 'Cảnh báo giá',
  weather_alert: 'Cảnh báo thời tiết',
  alert: 'Cảnh báo',
  harvest: 'Mùa vụ',
  season: 'Mùa vụ',
  crop: 'Nông sản',
}[type] || 'Liên quan');

const NotificationsPage = () => {
  const [notifications, setNotifications] = useState([]);
  // Khởi tạo rỗng: trước khi gọi xong thì chưa biết con số nào, không phải là 0.
  const [summary, setSummary] = useState({
    total: null,
    unread: null,
    by_type: {},
    delivery_failed: null,
    high_priority: null,
  });
  const [activeFilter, setActiveFilter] = useState('all');
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [streamStatus, setStreamStatus] = useState('connecting');
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);
  const reloadTimerRef = useRef(null);

  const loadSummary = async () => {
    const results = await Promise.allSettled([
      notificationsApi.summary(),
      notificationsApi.unreadCount(),
    ]);
    const data = results[0].status === 'fulfilled' ? results[0].value : summary;
    const unread = results[1].status === 'fulfilled' ? results[1].value : {};
    // Không tự gán source/confidence: metadata phải đến từ chính phản hồi.
    setSummary({
      ...data,
      unread: unread.unread_count ?? data.unread,
    });
  };

  const loadNotifications = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeFilter === 'important') {
        const data = await notificationsApi.priority({ minPriority: 'high' });
        const rows = (data.notifications || []).map(normalizeNotification);
        setNotifications(rows);
        setSelectedId((current) => current || rows[0]?.id || null);
        await loadSummary();
        return;
      }
      const type =
        activeFilter === 'all' || activeFilter === 'unread' || activeFilter === 'delivery_failed'
          ? undefined
          : activeFilter;
      const data = await notificationsApi.list({
        type,
        unreadOnly: activeFilter === 'unread',
        limit: 100,
      });
      const rows = (data.notifications || []).map(normalizeNotification);
      setNotifications(rows);
      setSelectedId((current) => current || rows[0]?.id || null);
      await loadSummary();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể tải thông báo'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();
  }, [activeFilter]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      setStreamStatus('offline');
      return undefined;
    }
    const source = new EventSource(notificationsApi.streamUrl());
    source.addEventListener('open', () => setStreamStatus('connected'));
    source.addEventListener('summary', (event) => {
      setStreamStatus('connected');
      try {
        setSummary(JSON.parse(event.data));
        window.clearTimeout(reloadTimerRef.current);
        reloadTimerRef.current = window.setTimeout(() => {
          loadNotifications();
        }, 600);
      } catch {
        loadSummary().catch(() => {});
      }
    });
    source.addEventListener('error', () => setStreamStatus('reconnecting'));
    return () => {
      window.clearTimeout(reloadTimerRef.current);
      source.close();
    };
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let active = true;
    const loadDetail = async () => {
      setDetailLoading(true);
      try {
        const data = await notificationsApi.detail(selectedId);
        if (active) setDetail(data);
      } catch {
        if (active) setDetail(null);
      } finally {
        if (active) setDetailLoading(false);
      }
    };
    loadDetail();
    return () => {
      active = false;
    };
  }, [selectedId]);

  const selectedNotification = useMemo(
    () => notifications.find((notification) => notification.id === selectedId) || notifications[0],
    [notifications, selectedId]
  );

  /** Số trên chip lọc: thiếu thì trả null để hiển thị em dash thay vì 0. */
  const filterCount = (filter) => {
    if (filter.value === 'all') return summary.total;
    if (filter.value === 'unread') return summary.unread;
    if (filter.value === 'important') return summary.high_priority;
    if (filter.value === 'delivery_failed') return summary.delivery_failed;
    return summary.by_type?.[filter.value];
  };

  const markAsRead = async (id) => {
    await notificationsApi.markRead(id);
    setNotifications((current) =>
      current.map((notification) => (notification.id === id ? { ...notification, read: true } : notification))
    );
    await loadSummary();
  };

  const markAllAsRead = async () => {
    await notificationsApi.markAllRead();
    setNotifications((current) => current.map((notification) => ({ ...notification, read: true })));
    await loadSummary();
  };

  const bulkDelete = async () => {
    await notificationsApi.bulk({
      action: 'delete',
      type: activeFilter === 'all' || activeFilter === 'unread' || activeFilter === 'delivery_failed' ? undefined : activeFilter,
      unreadOnly: activeFilter === 'unread',
    });
    setSelectedId(null);
    await loadNotifications();
  };

  const removeNotification = async (id) => {
    await notificationsApi.remove(id);
    setNotifications((current) => current.filter((notification) => notification.id !== id));
    if (selectedId === id) setSelectedId(null);
    await loadSummary();
  };

  const retryDelivery = async () => {
    if (!selectedNotification) return;
    await notificationsApi.retryDelivery(selectedNotification.id);
    const data = await notificationsApi.detail(selectedNotification.id);
    setDetail(data);
    await loadSummary();
  };

  const StreamIcon = streamStatus === 'connected' ? Wifi : WifiOff;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold uppercase tracking-wide text-green-700">Hộp thông báo trực tiếp</p>
            <DataSourceBadge data={summary} />
          </div>
          <h1 className="mt-2 text-3xl font-bold text-gray-900">Thông báo</h1>
          <p className="mt-2 text-gray-600">
            Thông báo giá, thời tiết, mùa vụ và lịch sử gửi được cập nhật tại đây.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700">
            <StreamIcon className="h-4 w-4" />
            {streamStatusLabel(streamStatus)}
          </span>
          <button
            type="button"
            onClick={markAllAsRead}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-2 font-medium text-gray-700 hover:bg-gray-50"
          >
            <CheckCheck className="h-5 w-5" />
            Đánh dấu đã đọc
          </button>
        </div>
      </div>

      {error && <PageError message={error} onRetry={loadNotifications} />}
      {loading && <InlineLoading text="Đang tải thông báo..." />}

      {!loading && !error && (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <div data-testid="summary-total" className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <Bell className="mb-3 h-6 w-6 text-green-700" aria-hidden="true" />
              <div data-testid="summary-value" className="text-2xl font-bold text-gray-900">
                {formatNumber(summary.total)}
              </div>
              <div className="text-sm text-gray-600">tổng thông báo</div>
            </div>
            <div data-testid="summary-unread" className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <Filter className="mb-3 h-6 w-6 text-amber-600" aria-hidden="true" />
              <div data-testid="summary-value" className="text-2xl font-bold text-gray-900">
                {formatNumber(summary.unread)}
              </div>
              <div className="text-sm text-gray-600">chưa đọc</div>
            </div>
            <div data-testid="summary-price" className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <LineChart className="mb-3 h-6 w-6 text-blue-600" aria-hidden="true" />
              <div data-testid="summary-value" className="text-2xl font-bold text-gray-900">
                {formatNumber(summary.by_type?.price)}
              </div>
              <div className="text-sm text-gray-600">cảnh báo giá</div>
            </div>
            <div data-testid="summary-failed" className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <ShieldAlert className="mb-3 h-6 w-6 text-red-700" aria-hidden="true" />
              <div data-testid="summary-value" className="text-2xl font-bold text-gray-900">
                {formatNumber(summary.delivery_failed)}
              </div>
              <div className="text-sm text-gray-600">gửi lỗi</div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {baseFilters.map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => setActiveFilter(filter.value)}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                  activeFilter === filter.value
                    ? 'bg-green-700 text-white'
                    : 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                {filter.label} ({formatNumber(filterCount(filter))})
              </button>
            ))}
            <button
              type="button"
              onClick={bulkDelete}
              className="ml-auto inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
            >
              <Trash2 className="h-4 w-4" />
              Xóa theo bộ lọc
            </button>
          </div>

          {notifications.length ? (
            <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
              <div className="space-y-3">
                {notifications.map((notification) => {
                  const iconConfig = iconMap[notification.type] || iconMap.system;
                  const Icon = iconConfig.icon;
                  return (
                    <article
                      key={notification.id}
                      className={`rounded-lg border bg-white p-4 shadow-sm transition ${
                        notification.read ? 'border-gray-200' : 'border-green-300'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedId(notification.id);
                          if (!notification.read) markAsRead(notification.id);
                        }}
                        className="flex w-full items-start gap-4 text-left"
                      >
                        <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${iconConfig.color}`}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h2 className="font-bold text-gray-900">{translateUiText(notification.title)}</h2>
                            {!notification.read && <span className="h-2 w-2 rounded-full bg-green-600" />}
                          </div>
                          <p className="mt-1 text-sm leading-6 text-gray-600">{translateUiText(notification.description)}</p>
                          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-500">
                            <span>{notification.time}</span>
                            <span className="rounded-full bg-gray-100 px-2.5 py-1 font-medium text-gray-700">
                              {priorityLabel(notification.priority)}
                            </span>
                            <DataSourceBadge data={notification} />
                            {notification.relatedEntityType && <span>{entityTypeLabel(notification.relatedEntityType)} #{notification.relatedEntityId}</span>}
                          </div>
                        </div>
                        <ChevronRight className="mt-1 h-5 w-5 shrink-0 text-gray-400" />
                      </button>
                    </article>
                  );
                })}
              </div>

              <aside className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
                {selectedNotification ? (
                  <>
                    <div className="mb-5 flex items-start justify-between gap-4">
                      <div>
                        <p className="text-sm font-semibold uppercase tracking-wide text-green-700">Chi tiết</p>
                        <h2 className="mt-2 text-xl font-bold text-gray-900">{translateUiText(selectedNotification.title)}</h2>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeNotification(selectedNotification.id)}
                        className="rounded-lg p-2 text-gray-500 hover:bg-red-50 hover:text-red-700"
                        aria-label="Xóa thông báo"
                      >
                        <Trash2 className="h-5 w-5" />
                      </button>
                    </div>
                    {detailLoading ? (
                      <InlineLoading text="Đang tải chi tiết..." />
                    ) : (
                      <>
                        <p className="text-sm leading-7 text-gray-600">{translateUiText(detail?.message || selectedNotification.description)}</p>
                        {detail?.related_entity && (
                          <div className="mt-5 rounded-lg bg-green-50 p-4 text-sm text-green-900">
                            <div className="font-semibold">Thông tin liên quan</div>
                            <p className="mt-2">
                              {detail.related_entity.crop_name} · {detail.related_entity.region} · ngưỡng{' '}
                              {Number(detail.related_entity.target_price).toLocaleString('vi-VN')} VND/kg
                            </p>
                          </div>
                        )}
                        <div className="mt-5">
                          <div className="mb-3 font-semibold text-gray-900">Lịch sử gửi</div>
                          <div className="space-y-2">
                            {(detail?.deliveries || []).map((delivery) => (
                              <div key={delivery.delivery_id} className="rounded-lg border border-gray-200 p-3 text-sm">
                                <div className="flex items-center justify-between gap-3">
                                  <span className="font-medium text-gray-900">{channelLabel(delivery.channel)}</span>
                                  <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${deliveryClass(delivery.status)}`}>
                                    {systemStatusLabel(delivery.status)}
                                  </span>
                                </div>
                                <div className="mt-1 text-xs text-gray-500">
                                  {formatTime(delivery.sent_at)}
                                </div>
                                {delivery.error_message && <div className="mt-1 text-xs text-red-700">{delivery.error_message}</div>}
                              </div>
                            ))}
                            {!detail?.deliveries?.length && (
                              <div className="rounded-lg border border-dashed border-gray-300 p-3 text-sm text-gray-600">
                                Chưa có lịch sử gửi.
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="mt-5 grid gap-2">
                          <button
                            type="button"
                            onClick={() => markAsRead(selectedNotification.id)}
                            className="rounded-lg bg-green-700 px-4 py-3 font-semibold text-white hover:bg-green-800"
                          >
                            Đánh dấu đã đọc
                          </button>
                          <button
                            type="button"
                            onClick={retryDelivery}
                            className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-3 font-medium text-gray-700 hover:bg-gray-50"
                          >
                            <RefreshCcw className="h-4 w-4" />
                            Gửi lại kênh lỗi
                          </button>
                        </div>
                      </>
                    )}
                  </>
                ) : (
                  <div className="py-10 text-center text-sm text-gray-600">Chọn một thông báo để xem chi tiết.</div>
                )}
              </aside>
            </div>
          ) : (
            <EmptyState
              title="Chưa có thông báo"
              description="Cảnh báo giá, thời tiết, lịch sử gửi và nhắc mùa vụ sẽ xuất hiện tại đây khi hệ thống tạo thông báo."
            />
          )}
        </>
      )}
    </div>
  );
};

export default NotificationsPage;
