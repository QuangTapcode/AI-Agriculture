const THUNDERSTORM_CODES = new Set([95, 96, 99]);
const THUNDERSTORM_CONDITIONS = new Set(['thunderstorm', 'thunderstorm_hail']);
const HEAVY_RAIN_CONDITIONS = new Set(['heavy_rain', 'heavy_showers']);

/**
 * Nguy cơ giông lốc cho một giờ dự báo.
 *
 * Không suy ra "Không có" từ chỗ thiếu dữ liệu: nếu giờ đó không mang cả
 * `condition` lẫn `weather_code` thì ta chưa biết gì, và một nhãn xanh
 * "Không có" sẽ là lời trấn an dựa trên khoảng trống.
 */
export function thunderstormRisk(hour = {}) {
  const code = hour?.weather_code;
  const condition = String(hour?.condition || '').toLowerCase();
  const hasCode = code !== null && code !== undefined && Number.isFinite(Number(code));

  if (!hasCode && !condition) {
    return { level: 'unknown', label: 'Chưa có dữ liệu' };
  }

  if ((hasCode && THUNDERSTORM_CODES.has(Number(code))) || THUNDERSTORM_CONDITIONS.has(condition)) {
    return { level: 'active', label: 'Đang xảy ra' };
  }

  if (HEAVY_RAIN_CONDITIONS.has(condition)) {
    return { level: 'elevated', label: 'Nguy cơ cao' };
  }

  return { level: 'none', label: 'Không có' };
}

export default thunderstormRisk;
