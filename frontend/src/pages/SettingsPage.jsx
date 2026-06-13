import {
  Bell,
  Check,
  CheckCircle2,
  Globe2,
  KeyRound,
  Loader2,
  Mail,
  MapPin,
  Monitor,
  RefreshCw,
  Save,
  Send,
  ShieldCheck,
  Smartphone,
  User,
  XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import DataSourceBadge from '../components/DataSourceBadge';
import { InlineLoading, PageError } from '../components/StatusState';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import { getApiErrorMessage } from '../services/api';
import { settingsApi } from '../services/settingsApi';

const eventTypes = [
  { key: 'priceAlerts', label: 'Giá' },
  { key: 'weatherAlerts', label: 'Thời tiết' },
  { key: 'harvestReminders', label: 'Mùa vụ' },
];

const channels = [
  { key: 'app', label: 'App' },
  { key: 'emailChannel', label: 'Email', channel: 'email' },
  { key: 'zaloChannel', label: 'Zalo', channel: 'zalo' },
  { key: 'smsChannel', label: 'SMS', channel: 'sms' },
];

const Toggle = ({ checked, onChange, disabled = false }) => (
  <label className="relative inline-flex cursor-pointer items-center">
    <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} className="peer sr-only" />
    <span className="h-6 w-11 rounded-full bg-gray-200 transition peer-checked:bg-green-700 peer-disabled:opacity-50" />
    <span className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition peer-checked:translate-x-5" />
  </label>
);

const statusClass = (status) => {
  if (status === 'ready') return 'bg-green-100 text-green-800';
  if (status === 'mock' || status === 'missing_token' || status === 'not_configured') return 'bg-amber-100 text-amber-800';
  if (status === 'failed_last_test') return 'bg-red-100 text-red-700';
  return 'bg-gray-100 text-gray-700';
};

const statusLabel = (status) => ({
  ok: 'Hoạt động',
  ready: 'Sẵn sàng',
  disabled: 'Đã tắt',
  pending_verification: 'Thiếu người nhận',
  missing_token: 'Thiếu mã cấu hình',
  not_configured: 'Chưa cấu hình',
  mock: 'Chưa có realtime',
  failed_last_test: 'Lỗi lần thử',
  sent: 'Đã gửi',
  stored: 'Đã lưu',
  mock_sent: 'Chưa gửi realtime',
  failed: 'Thất bại',
}[status] || 'Không rõ');

const channelLabel = (channel) => ({
  app: 'Ứng dụng',
  email: 'Email',
  zalo: 'Zalo',
  sms: 'SMS',
}[channel] || 'Kênh gửi');

const ChannelStatus = ({ channel, status, testState, onTest }) => {
  const active = testState.channel === channel;
  const isLoading = active && testState.status === 'loading';
  const isOk = active && testState.status === 'ok';
  const isErr = active && testState.status === 'error';

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-gray-900">{channelLabel(channel)}</div>
          <div className="mt-1 text-xs text-gray-500">{status?.receiver || 'Chưa có người nhận'}</div>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusClass(status?.status)}`}>
          {statusLabel(status?.status)}
        </span>
      </div>
      <div className="mt-3 text-xs text-gray-500">
        {status?.last_tested_at ? `Lần thử gần nhất: ${new Date(status.last_tested_at).toLocaleString('vi-VN')}` : 'Chưa gửi thử'}
      </div>
      {status?.error && <div className="mt-2 text-xs text-amber-700">{status.error}</div>}
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={onTest}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 rounded border border-green-600 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-50 disabled:opacity-50"
        >
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
          Gửi thử
        </button>
        {isOk && (
          <span className="flex items-center gap-1 text-xs text-green-700">
            <CheckCircle2 className="h-3.5 w-3.5" /> {testState.message}
          </span>
        )}
        {isErr && (
          <span className="flex items-center gap-1 text-xs text-red-600">
            <XCircle className="h-3.5 w-3.5" /> {testState.message}
          </span>
        )}
      </div>
    </div>
  );
};

const SettingsPage = () => {
  const { user } = useAuth();
  const { language, setLanguage, t } = useLanguage();
  const [settings, setSettings] = useState({
    fullName: user?.name || '',
    email: user?.email || '',
    phone: user?.phone || '',
    zaloUserId: '',
    regionKey: '',
    location: user?.region || '',
    language: language,
    unit: 'hectare',
    theme: 'light',
    priceAlerts: true,
    weatherAlerts: true,
    harvestReminders: true,
    emailChannel: true,
    zaloChannel: false,
    smsChannel: false,
  });
  const [locations, setLocations] = useState([]);
  const [channelStatus, setChannelStatus] = useState({});
  const [sourceMeta, setSourceMeta] = useState({});
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [testState, setTestState] = useState({ channel: null, status: null, message: '' });
  const [passwordForm, setPasswordForm] = useState({ oldPassword: '', newPassword: '', message: '' });

  const loadChannelStatus = async () => {
    const data = await settingsApi.getChannelStatus();
    setChannelStatus(data);
  };

  const loadSettings = useCallback(async ({ background = false } = {}) => {
    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      const results = await Promise.allSettled([
        settingsApi.getProfile(),
        settingsApi.getFarm(),
        settingsApi.getAlertPreferences(),
        settingsApi.getAiPreferences(),
        settingsApi.getLocations(),
        settingsApi.getChannelStatus(),
      ]);
      const [profileData, farmData, alertPrefs, aiPrefs, locationData, channelData] = results.map((item) => (
        item.status === 'fulfilled' ? item.value : {}
      ));
      const failed = results.filter((item) => item.status === 'rejected');
      setLocations(locationData.locations || []);
      setChannelStatus(channelData);
      setSourceMeta({
        profile: profileData,
        farm: farmData,
        alerts: alertPrefs,
        ai: aiPrefs,
        channels: channelData,
      });
      setSettings((current) => ({
        ...current,
        fullName: profileData.full_name || user?.name || '',
        email: profileData.email || user?.email || '',
        phone: profileData.phone_number || user?.phone || '',
        zaloUserId: profileData.zalo_user_id || '',
        regionKey: profileData.region_key || '',
        location: farmData.region || profileData.region || user?.region || '',
        language: current.language || aiPrefs.language || 'vi',
        unit: profileData.unit || current.unit,
        theme: profileData.theme || current.theme,
        priceAlerts: Boolean(alertPrefs.price_alerts),
        weatherAlerts: Boolean(alertPrefs.weather_alerts),
        harvestReminders: Boolean(alertPrefs.harvest_reminders),
        emailChannel: Boolean(alertPrefs.channels?.email),
        zaloChannel: Boolean(alertPrefs.channels?.zalo),
        smsChannel: Boolean(alertPrefs.channels?.sms),
      }));
      if (failed.length) {
        setError('Một số cấu hình phản hồi chậm, trang đang hiển thị phần dữ liệu tải được.');
      }
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể tải cài đặt'));
    } finally {
      if (background) {
        setRefreshing(false);
        return;
      }
      setLoading(false);
    }
  }, [user?.name, user?.email, user?.phone, user?.region]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const updateSetting = (key, value) => {
    setSettings((current) => ({ ...current, [key]: value }));
    if (key === 'language') {
      setLanguage(value);
    }
    setSaved(false);
  };

  const handleRegionChange = (regionKey) => {
    const region = locations.find((item) => item.region_key === regionKey);
    setSettings((current) => ({
      ...current,
      regionKey,
      location: region?.display_name || current.location,
    }));
    setSaved(false);
  };

  const handleRefresh = async () => {
    await loadSettings({ background: true });
  };

  const handleSendTest = async (channel) => {
    const receiverMap = {
      email: settings.email,
      zalo: settings.zaloUserId,
      sms: settings.phone,
    };
    setTestState({ channel, status: 'loading', message: '' });
    try {
      const result = await settingsApi.testNotificationChannel({ channel, receiver: receiverMap[channel] });
      const ok = ['sent', 'stored'].includes(result?.status);
      setTestState({
        channel,
        status: ok ? 'ok' : 'error',
        message: ok ? statusLabel(result.status) : result?.error || 'Gửi thất bại.',
      });
      await loadChannelStatus();
    } catch (err) {
      setTestState({ channel, status: 'error', message: getApiErrorMessage(err, 'Lỗi kết nối') });
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setSaved(false);
    try {
      const results = await Promise.allSettled([
        settingsApi.saveProfile({
          full_name: settings.fullName,
          email: settings.email,
          phone_number: settings.phone,
          zalo_user_id: settings.zaloUserId,
          region: settings.location,
          region_key: settings.regionKey,
          language: settings.language,
          unit: settings.unit,
          theme: settings.theme,
        }),
        settingsApi.saveFarm({
          region: settings.location,
          main_crops: ['lua'],
        }),
        settingsApi.saveAlertPreferences({
          price_alerts: settings.priceAlerts,
          weather_alerts: settings.weatherAlerts,
          harvest_reminders: settings.harvestReminders,
          email_channel: settings.emailChannel,
          zalo_channel: settings.zaloChannel,
          sms_channel: settings.smsChannel,
        }),
        settingsApi.saveAiPreferences({
          language: settings.language,
          explanation_level: 'balanced',
        }),
      ]);
      const failed = results.filter((item) => item.status === 'rejected');
      if (failed.length === results.length) {
        throw failed[0].reason;
      }
      const [profile, farm, alertPrefs, aiPrefs] = results.map((item) => (
        item.status === 'fulfilled' ? item.value : {}
      ));
      setSourceMeta((current) => ({
        ...current,
        profile,
        farm,
        alerts: alertPrefs,
        ai: aiPrefs,
      }));
      setSettings((current) => ({
        ...current,
        fullName: profile.full_name || current.fullName,
        email: profile.email || current.email,
        phone: profile.phone_number || current.phone,
        zaloUserId: profile.zalo_user_id || current.zaloUserId,
        regionKey: profile.region_key || current.regionKey,
        location: farm.region || profile.region || current.location,
      }));
      setLanguage(settings.language);
      setSaved(true);
      if (failed.length) {
        setError('Một số mục cài đặt chưa lưu được do phản hồi chậm. Các mục còn lại đã được cập nhật.');
      }
      await loadChannelStatus();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể lưu cài đặt'));
    }
  };

  const changePassword = async () => {
    setError(null);
    try {
      await settingsApi.changePassword({
        oldPassword: passwordForm.oldPassword,
        newPassword: passwordForm.newPassword,
      });
      setPasswordForm({ oldPassword: '', newPassword: '', message: 'Đã đổi mật khẩu.' });
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể đổi mật khẩu'));
    }
  };

  if (loading) {
    return <InlineLoading text="Đang tải cài đặt từ hệ thống..." />;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold uppercase tracking-wide text-green-700">{t('operationSettings')}</p>
            <DataSourceBadge data={sourceMeta.profile || { source: 'database', source_name: 'Hồ sơ người dùng', confidence: 0.72 }} />
          </div>
          <h1 className="mt-2 text-3xl font-bold text-gray-900">{t('settingsHeading')}</h1>
          <p className="mt-2 text-gray-600">{t('settingsSubheading')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-blue-300 bg-blue-50 px-5 py-3 font-semibold text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {refreshing ? <Loader2 className="h-5 w-5 animate-spin" /> : <RefreshCw className="h-5 w-5" />}
            Refresh
          </button>
          <button
            type="submit"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-green-700 px-5 py-3 font-semibold text-white hover:bg-green-800"
          >
            <Save className="h-5 w-5" />
            {t('saveSettings')}
          </button>
        </div>
      </div>

      {error && <PageError message={error} />}

      {saved && (
        <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
          <Check className="h-5 w-5" />
          Đã lưu cấu hình vào hệ thống.
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1fr_400px]">
        <div className="space-y-6">
          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-lg bg-green-50 p-2 text-green-700">
                <User className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">Hồ sơ tài khoản</h2>
                <p className="text-sm text-gray-600">Thông tin dùng cho cá nhân hóa và kênh nhận cảnh báo.</p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Họ và tên</label>
                <input
                  value={settings.fullName}
                  onChange={(event) => updateSetting('fullName', event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Số điện thoại</label>
                <input
                  value={settings.phone}
                  onChange={(event) => updateSetting('phone', event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Email</label>
                <input
                  type="email"
                  value={settings.email}
                  onChange={(event) => updateSetting('email', event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Zalo UID theo OA</label>
                <input
                  value={settings.zaloUserId}
                  onChange={(event) => updateSetting('zaloUserId', event.target.value)}
                  placeholder="UID người dùng đã quan tâm OA"
                  className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Đây là user_id theo Zalo OA, không phải số điện thoại cá nhân.
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-lg bg-blue-50 p-2 text-blue-700">
                <Monitor className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">{t('regionAndDisplay')}</h2>
                <p className="text-sm text-gray-600">{t('sharedRegion')}</p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              <div className="md:col-span-2">
                <label className="mb-2 block text-sm font-medium text-gray-700">{t('normalizedRegion')}</label>
                <select
                  value={settings.regionKey}
                  onChange={(event) => handleRegionChange(event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                >
                  {locations.map((location) => (
                    <option key={location.region_key} value={location.region_key}>
                      {location.display_name}
                      {location.latitude ? ` · ${location.latitude}, ${location.longitude}` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">{t('language')}</label>
                <select
                  value={settings.language}
                  onChange={(event) => updateSetting('language', event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                >
                  <option value="vi">{t('vietnamese')}</option>
                  <option value="en">{t('english')}</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">{t('theme')}</label>
                <select
                  value={settings.theme}
                  onChange={(event) => updateSetting('theme', event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-3 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                >
                  <option value="light">{t('light')}</option>
                  <option value="dark">{t('dark')}</option>
                  <option value="system">{t('system')}</option>
                </select>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-lg bg-amber-50 p-2 text-amber-700">
                <Bell className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">Ma trận thông báo</h2>
                <p className="text-sm text-gray-600">Bật/tắt loại thông báo và kênh nhận tương ứng.</p>
              </div>
            </div>

            <div className="overflow-hidden rounded-lg border border-gray-200">
              <div className="grid grid-cols-[1fr_repeat(4,80px)] bg-gray-50 text-sm font-semibold text-gray-700">
                <div className="p-3">Loại thông báo</div>
                {channels.map((channel) => (
                  <div key={channel.key} className="p-3 text-center">
                    {channel.label}
                  </div>
                ))}
              </div>
              {eventTypes.map((eventType) => (
                <div key={eventType.key} className="grid grid-cols-[1fr_repeat(4,80px)] border-t border-gray-200 text-sm">
                  <div className="p-3 font-medium text-gray-900">{eventType.label}</div>
                  {channels.map((channel) => (
                    <div key={channel.key} className="flex items-center justify-center p-3">
                      <Toggle
                        checked={channel.key === 'app' ? settings[eventType.key] : settings[eventType.key] && settings[channel.key]}
                        onChange={() =>
                          channel.key === 'app'
                            ? updateSetting(eventType.key, !settings[eventType.key])
                            : updateSetting(channel.key, !settings[channel.key])
                        }
                      />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="space-y-6">
          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-lg bg-gray-100 p-2 text-gray-700">
                <Mail className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Kênh nhận và trạng thái</h2>
                <p className="text-xs text-gray-500">Trạng thái lấy từ hệ thống và kênh gửi, không chỉ là nút bật/tắt.</p>
              </div>
            </div>

            <div className="mb-4 grid gap-3">
              <label className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                <span className="text-sm font-medium text-gray-900">Email</span>
                <Toggle checked={settings.emailChannel} onChange={() => updateSetting('emailChannel', !settings.emailChannel)} />
              </label>
              <label className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                <span className="text-sm font-medium text-gray-900">Zalo OA</span>
                <Toggle checked={settings.zaloChannel} onChange={() => updateSetting('zaloChannel', !settings.zaloChannel)} />
              </label>
              <label className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                <span className="text-sm font-medium text-gray-900">SMS</span>
                <Toggle checked={settings.smsChannel} onChange={() => updateSetting('smsChannel', !settings.smsChannel)} />
              </label>
            </div>

            <div className="space-y-3">
              {['email', 'zalo', 'sms'].map((channel) => (
                <ChannelStatus
                  key={channel}
                  channel={channel}
                  status={channelStatus[channel]}
                  testState={testState}
                  onTest={() => handleSendTest(channel)}
                />
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-lg bg-green-50 p-2 text-green-700">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <h2 className="text-lg font-bold text-gray-900">Bảo mật</h2>
            </div>
            <div className="space-y-4">
              <div className="rounded-lg border border-gray-200 p-4">
                <div className="mb-3 flex items-center gap-2 font-semibold text-gray-900">
                  <KeyRound className="h-4 w-4" />
                  Đổi mật khẩu
                </div>
                <div className="grid gap-2">
                  <input
                    type="password"
                    value={passwordForm.oldPassword}
                    onChange={(event) => setPasswordForm((current) => ({ ...current, oldPassword: event.target.value }))}
                    placeholder="Mật khẩu hiện tại"
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-green-600"
                  />
                  <input
                    type="password"
                    value={passwordForm.newPassword}
                    onChange={(event) => setPasswordForm((current) => ({ ...current, newPassword: event.target.value }))}
                    placeholder="Mật khẩu mới"
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-green-600"
                  />
                  <button
                    type="button"
                    onClick={changePassword}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Cập nhật mật khẩu
                  </button>
                  {passwordForm.message && <div className="text-xs text-green-700">{passwordForm.message}</div>}
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-bold text-gray-900">Trạng thái nguồn dữ liệu</h2>
              <DataSourceBadge data={sourceMeta.channels || { source: 'database', source_name: 'Trạng thái kênh thông báo', confidence: 0.7 }} />
            </div>
            <div className="mt-4 space-y-3 text-sm text-gray-700">
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2">
                  <Globe2 className="h-4 w-4 text-green-700" />
                  Dữ liệu thời tiết
                </span>
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusClass(channelStatus.data_sources?.weather?.status)}`}>
                  {channelStatus.data_sources?.weather?.status === 'ok' ? 'Hoạt động' : 'Chưa rõ'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-blue-600" />
                  Dữ liệu giá
                </span>
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusClass(channelStatus.data_sources?.price?.status)}`}>
                  {channelStatus.data_sources?.price?.status === 'ok' ? 'Hoạt động' : 'Chưa rõ'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2">
                  <Smartphone className="h-4 w-4 text-amber-600" />
                  Nhà cung cấp SMS
                </span>
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusClass(channelStatus.sms?.status)}`}>
                  {channelStatus.sms?.status === 'ok' ? 'Hoạt động' : 'Chưa rõ'}
                </span>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </form>
  );
};

export default SettingsPage;
