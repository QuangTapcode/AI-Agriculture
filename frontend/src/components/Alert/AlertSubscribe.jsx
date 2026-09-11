import { Bell, CloudSun, Loader2, Send, Sparkles, ThermometerSun } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import DataSourceBadge from '../DataSourceBadge';
import { PageError } from '../StatusState';
import { getApiErrorMessage } from '../../services/api';
import { alertApi } from '../../services/alertApi';
import { sourceNameLabel, translateUiText } from '../../utils/vietnameseText';

const formatCurrency = (value) => Number(value || 0).toLocaleString('vi-VN');

const AlertSubscribe = ({ mode = 'price', onCreated }) => {
  const [options, setOptions] = useState({ crops: [], regions: [], channels: [], rule_types: [] });
  const [formData, setFormData] = useState({
    cropId: '',
    cropName: '',
    regionKey: '',
    region: '',
    targetPrice: 25000,
    condition: 'above',
    notifyMethod: 'email',
    contact: '',
    weatherCondition: 'rainfall',
    weatherThreshold: 50,
  });
  const [currentPrice, setCurrentPrice] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [weatherAlerts, setWeatherAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [metaLoading, setMetaLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const selectedCrop = useMemo(
    () => options.crops?.find((crop) => String(crop.crop_id || crop.crop_name) === String(formData.cropId)),
    [formData.cropId, options.crops]
  );
  const selectedRegion = useMemo(
    () => options.regions?.find((region) => region.region_key === formData.regionKey),
    [formData.regionKey, options.regions]
  );

  useEffect(() => {
    let active = true;
    const loadOptions = async () => {
      setMetaLoading(true);
      setError(null);
      try {
        const data = await alertApi.getOptions();
        if (!active) return;
        const firstCrop = data?.crops?.[0];
        const defaultRegion =
          data?.regions?.find((region) => region.display_name === data.default_region) || data?.regions?.[0];
        /*
         * Giữ nguyên hình dạng mảng cho mọi danh sách. Trước đây ta gán thẳng
         * `data` vào state, nên một phản hồi thiếu `crops` biến options.crops
         * thành undefined và `.find()` ngay dưới làm sập toàn bộ trang cảnh báo.
         */
        setOptions({
          ...data,
          crops: Array.isArray(data?.crops) ? data.crops : [],
          regions: Array.isArray(data?.regions) ? data.regions : [],
          channels: Array.isArray(data?.channels) ? data.channels : [],
          rule_types: Array.isArray(data?.rule_types) ? data.rule_types : [],
        });
        setFormData((current) => ({
          ...current,
          cropId: current.cropId || String(firstCrop?.crop_id || firstCrop?.crop_name || ''),
          cropName: current.cropName || firstCrop?.crop_name || '',
          regionKey: current.regionKey || defaultRegion?.region_key || '',
          region: current.region || defaultRegion?.display_name || '',
          notifyMethod: current.notifyMethod || data.channels?.[0]?.value || 'email',
        }));
      } catch (err) {
        if (active) setError(getApiErrorMessage(err, 'Không thể tải danh mục cảnh báo'));
      } finally {
        if (active) setMetaLoading(false);
      }
    };
    loadOptions();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedCrop || !selectedRegion) return;
    let active = true;
    const loadPriceContext = async () => {
      try {
        const results = await Promise.allSettled([
          alertApi.getCurrentPrice({
            cropName: selectedCrop.crop_name,
            cropId: selectedCrop.crop_id,
            region: selectedRegion.display_name,
            regionKey: selectedRegion.region_key,
          }),
          alertApi.getSuggestions({
            cropName: selectedCrop.crop_name,
            cropId: selectedCrop.crop_id,
            region: selectedRegion.display_name,
            regionKey: selectedRegion.region_key,
          }),
        ]);
        const priceData = results[0].status === 'fulfilled' ? results[0].value : null;
        const suggestionData = results[1].status === 'fulfilled' ? results[1].value : { suggestions: [] };
        if (!active) return;
        setCurrentPrice(priceData);
        setSuggestions(suggestionData.suggestions || []);
      } catch (err) {
        if (active) setCurrentPrice(null);
      }
    };
    loadPriceContext();
    return () => {
      active = false;
    };
  }, [selectedCrop, selectedRegion]);

  useEffect(() => {
    if (mode !== 'weather' || !selectedRegion) return;
    let active = true;
    const loadWeatherAlerts = async () => {
      try {
        const rows = await alertApi.getWeatherAlerts(selectedRegion.display_name);
        if (active) setWeatherAlerts(Array.isArray(rows) ? rows : []);
      } catch {
        if (active) setWeatherAlerts([]);
      }
    };
    loadWeatherAlerts();
    return () => {
      active = false;
    };
  }, [mode, selectedRegion]);

  const updateField = (key, value) => {
    setFormData((current) => ({ ...current, [key]: value }));
    setMessage(null);
  };

  const handleCropChange = (value) => {
    const crop = options.crops?.find((item) => String(item.crop_id || item.crop_name) === String(value));
    setFormData((current) => ({
      ...current,
      cropId: value,
      cropName: crop?.crop_name || '',
    }));
  };

  const handleRegionChange = (value) => {
    const region = options.regions?.find((item) => item.region_key === value);
    setFormData((current) => ({
      ...current,
      regionKey: value,
      region: region?.display_name || '',
    }));
  };

  const applySuggestion = (suggestion) => {
    if (suggestion.rule_type === 'above' || suggestion.rule_type === 'below') {
      setFormData((current) => ({
        ...current,
        condition: suggestion.rule_type,
        targetPrice: suggestion.target_price,
      }));
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setMessage(null);

    const receiver = formData.contact.trim();
    if (formData.notifyMethod === 'email' && !receiver) {
      setError(
        mode === 'weather'
          ? 'Vui lòng nhập Gmail để nhận email xác nhận và các lần thời tiết thay đổi.'
          : 'Vui lòng nhập Gmail để nhận email xác nhận và các lần giá thay đổi.'
      );
      return;
    }

    setLoading(true);

    try {
      if (mode === 'weather') {
        const result = await alertApi.createWeatherAlert({
          region: formData.region,
          region_key: formData.regionKey,
          condition: formData.weatherCondition,
          threshold: Number(formData.weatherThreshold),
          severity: Number(formData.weatherThreshold) >= 50 ? 'high' : 'medium',
          notification_channel: formData.notifyMethod,
          receiver,
        });
        setMessage(result.message || 'Đã tạo cảnh báo thời tiết');
        onCreated?.(result);
      } else {
        const alert = await alertApi.createPriceAlert({
          cropName: formData.cropName,
          cropId: formData.cropId && Number.isFinite(Number(formData.cropId)) ? Number(formData.cropId) : undefined,
          region: formData.region,
          regionKey: formData.regionKey,
          targetPrice: formData.targetPrice,
          condition: formData.condition,
          notificationChannel: formData.notifyMethod,
          receiver,
        });
        setMessage(alert.message || 'Đã tạo cảnh báo giá');
        onCreated?.(alert);
      }
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể tạo cảnh báo'));
    } finally {
      setLoading(false);
    }
  };

  if (metaLoading) {
    return (
      <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3 text-sm text-gray-600">
          <Loader2 className="h-4 w-4 animate-spin" />
          Đang tải danh mục cảnh báo...
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-5 flex items-center gap-3">
        <div className="rounded-lg bg-green-50 p-2 text-green-700">
          {mode === 'weather' ? <CloudSun className="h-6 w-6" /> : <Bell className="h-6 w-6" />}
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            {mode === 'weather' ? 'Tạo cảnh báo thời tiết nông vụ' : 'Tạo cảnh báo thông minh'}
          </h2>
          <p className="text-sm text-gray-600">
            Dữ liệu danh mục, giá hiện tại và trạng thái nguồn được lấy từ hệ thống.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="alert-nong-san" className="mb-2 block text-sm font-medium text-gray-700">Nông sản</label>
            <select id="alert-nong-san"
              value={formData.cropId}
              onChange={(event) => handleCropChange(event.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            >
              {options.crops.map((crop) => (
                <option key={crop.crop_id || crop.crop_name} value={crop.crop_id || crop.crop_name}>
                  {crop.crop_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="alert-khu-vuc-chuan-hoa" className="mb-2 block text-sm font-medium text-gray-700">Khu vực chuẩn hóa</label>
            <select id="alert-khu-vuc-chuan-hoa"
              value={formData.regionKey}
              onChange={(event) => handleRegionChange(event.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            >
              {options.regions.map((region) => (
                <option key={region.region_key} value={region.region_key}>
                  {region.display_name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {mode === 'price' ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="alert-dieu-kien" className="mb-2 block text-sm font-medium text-gray-700">Điều kiện</label>
                <select id="alert-dieu-kien"
                  value={formData.condition}
                  onChange={(event) => updateField('condition', event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                >
                  <option value="above">Giá trên ngưỡng</option>
                  <option value="below">Giá dưới ngưỡng</option>
                </select>
              </div>

              <div>
                <label htmlFor="alert-gia-muc-tieu" className="mb-2 block text-sm font-medium text-gray-700">Giá mục tiêu</label>
                <input id="alert-gia-muc-tieu"
                  type="number"
                  min="1"
                  value={formData.targetPrice}
                  onChange={(event) => updateField('targetPrice', event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                  required
                />
              </div>
            </div>

            {currentPrice && (
              <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-blue-900">Giá hiện tại</div>
                    <div className="mt-1 text-2xl font-bold text-gray-900">
                      {formatCurrency(currentPrice.current_price)} {currentPrice.unit}
                    </div>
                  </div>
                  <DataSourceBadge data={currentPrice} />
                </div>
                <div className="mt-3 text-xs text-blue-900">
                  Nguồn: {sourceNameLabel(currentPrice.source_name || currentPrice.source)} · Cập nhật:{' '}
                  {currentPrice.last_updated ? new Date(currentPrice.last_updated).toLocaleString('vi-VN') : 'chưa rõ'}
                </div>
              </div>
            )}

            {suggestions.length > 0 && (
              <div className="rounded-lg border border-gray-200 p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900">
                  <Sparkles className="h-4 w-4 text-amber-500" />
                  Gợi ý ngưỡng cảnh báo
                </div>
                <div className="grid gap-2">
                  {suggestions.map((suggestion) => (
                    <button
                      key={`${suggestion.rule_type}-${suggestion.label}`}
                      type="button"
                      onClick={() => applySuggestion(suggestion)}
                      className="rounded-lg border border-gray-200 p-3 text-left text-sm hover:border-green-300 hover:bg-green-50"
                    >
                      <div className="font-medium text-gray-900">{suggestion.label}</div>
                      <div className="mt-1 text-gray-600">
                        {suggestion.target_price
                          ? `${formatCurrency(suggestion.target_price)} VND/kg`
                          : `${suggestion.threshold_percent}%`}
                        {' · '}
                        {translateUiText(suggestion.reason)}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="alert-loai-rui-ro" className="mb-2 block text-sm font-medium text-gray-700">Loại rủi ro</label>
                <select id="alert-loai-rui-ro"
                  value={formData.weatherCondition}
                  onChange={(event) => updateField('weatherCondition', event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                >
                  <option value="rainfall">Mưa lớn 24h tới</option>
                  <option value="temperature">Nhiệt độ vượt ngưỡng</option>
                  <option value="wind">Gió mạnh</option>
                  <option value="humidity">Độ ẩm cao</option>
                </select>
              </div>
              <div>
                <label htmlFor="alert-nguong-canh-bao" className="mb-2 block text-sm font-medium text-gray-700">Ngưỡng cảnh báo</label>
                <input id="alert-nguong-canh-bao"
                  type="number"
                  min="0"
                  value={formData.weatherThreshold}
                  onChange={(event) => updateField('weatherThreshold', event.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
                />
              </div>
            </div>

            <div className="rounded-lg border border-amber-100 bg-amber-50 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                <ThermometerSun className="h-4 w-4" />
                Cảnh báo thời tiết hiện có
              </div>
              <div className="mt-3 space-y-2">
                {weatherAlerts.length ? (
                  weatherAlerts.slice(0, 3).map((item, index) => (
                    <div key={`${item.title}-${index}`} className="rounded-lg bg-white p-3 text-sm text-gray-700">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium text-gray-900">{translateUiText(item.title || item.alert_type)}</div>
                        <DataSourceBadge data={item.source ? item : { ...item, source: 'realtime_api', source_name: 'Cảnh báo thời tiết' }} />
                      </div>
                      <div className="mt-1">{translateUiText(item.message)}</div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-amber-900">Chưa có rủi ro nổi bật, có thể tạo rule theo ngưỡng riêng.</p>
                )}
              </div>
            </div>
          </>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="alert-kenh-nhan" className="mb-2 block text-sm font-medium text-gray-700">Kênh nhận</label>
            <select id="alert-kenh-nhan"
              value={formData.notifyMethod}
              onChange={(event) => updateField('notifyMethod', event.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            >
              {(options.channels || []).map((channel) => (
                <option key={channel.value} value={channel.value}>
                  {channel.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="alert-nguoi-nhan" className="mb-2 block text-sm font-medium text-gray-700">Người nhận</label>
            <input id="alert-nguoi-nhan"
              type={formData.notifyMethod === 'email' ? 'email' : 'text'}
              value={formData.contact}
              onChange={(event) => updateField('contact', event.target.value)}
              placeholder={
                formData.notifyMethod === 'email'
                  ? 'example@gmail.com'
                  : formData.notifyMethod === 'zalo'
                    ? 'Zalo UID theo OA'
                    : formData.notifyMethod === 'app'
                      ? 'Tự dùng tài khoản hiện tại'
                      : 'Số điện thoại'
              }
              required={formData.notifyMethod !== 'app'}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 outline-none focus:border-green-600 focus:ring-2 focus:ring-green-100"
            />
            {formData.notifyMethod === 'zalo' && (
              <p className="mt-1 text-xs text-gray-500">
                Nhập UID của người dùng đã quan tâm Zalo OA để hệ thống gửi cảnh báo.
              </p>
            )}
            {formData.notifyMethod === 'email' && (
              <p className="mt-1 text-xs text-gray-500">
                {mode === 'weather'
                  ? 'AgriAI sẽ gửi email xác nhận ngay và gửi tiếp khi thời tiết thay đổi.'
                  : 'AgriAI sẽ gửi email xác nhận ngay và gửi tiếp khi giá thay đổi.'}
              </p>
            )}
          </div>
        </div>

        {message && <p className="rounded-lg bg-green-50 p-3 text-sm text-green-700">{message}</p>}
        {error && <PageError message={error} />}

        <button
          type="submit"
          disabled={loading}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-green-700 px-4 py-3 font-semibold text-white transition-colors hover:bg-green-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          {loading ? 'Đang tạo...' : mode === 'weather' ? 'Tạo cảnh báo thời tiết' : 'Đăng ký cảnh báo giá'}
        </button>
      </form>
    </section>
  );
};

export default AlertSubscribe;
