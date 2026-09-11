/**
 * Định dạng số/phần trăm cho UI, phân biệt rõ "thiếu dữ liệu" với "giá trị 0".
 *
 * Vì sao cần module riêng: backend trả `null` khi cache_status = "miss"
 * (spec anti-mock, TOD0 §1). Trong JavaScript `Number(null) === 0`, nên mọi
 * hàm format chỉ chặn NaN đều để lọt null và vẽ ra số 0 — người dùng đọc
 * thành "giá 0 đồng". TOD0 §5 cấm hiển thị bất kỳ số nào khi backend báo miss.
 */

/** Ký hiệu dùng khi không có dữ liệu. */
export const MISSING = '—';

/** true nếu giá trị thực sự tồn tại — số 0 vẫn tính là có. */
export function hasValue(value) {
  if (value === null || value === undefined || value === '') return false;
  return Number.isFinite(Number(value));
}

/** Số có phân cách hàng nghìn; thiếu dữ liệu trả MISSING chứ không phải 0. */
export function formatNumber(value, digits = 0) {
  if (!hasValue(value)) return MISSING;
  return Number(value).toLocaleString('vi-VN', { maximumFractionDigits: digits });
}

/** Phần trăm kèm dấu; thiếu dữ liệu trả MISSING chứ không phải "+0.0%". */
export function formatPct(value) {
  if (!hasValue(value)) return MISSING;
  const number = Number(value);
  return `${number >= 0 ? '+' : ''}${number.toFixed(1)}%`;
}

/**
 * Độ tin cậy dạng phần trăm.
 *
 * Nhiều trang từng viết `(value || 0) * 100`, biến "không đo được độ tin cậy"
 * thành "độ tin cậy 0%" — hai điều hoàn toàn khác nhau với người đọc. Thiếu thì
 * trả MISSING; 0 thật vẫn là 0%.
 *
 * @param {number|string|null|undefined} value
 * @param {{scale?: number}} [options] scale = 100 khi backend trả tỉ lệ 0..1
 */
export function formatConfidence(value, { scale = 100 } = {}) {
  if (!hasValue(value)) return MISSING;
  return `${Math.round(Number(value) * scale)}%`;
}
