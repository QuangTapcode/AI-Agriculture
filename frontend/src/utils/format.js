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
