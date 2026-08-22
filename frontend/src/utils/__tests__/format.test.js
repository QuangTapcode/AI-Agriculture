/**
 * TDD: dữ liệu thiếu không được biến thành số 0.
 *
 * Backend trả price = null khi cache_status = "miss" (đúng spec anti-mock,
 * TOD0 §1). Nhưng trong JavaScript Number(null) === 0, nên hàm format cũ chỉ
 * chặn NaN đã để lọt null và vẽ ra "0 VND/kg" kèm nhãn nguồn chính phủ.
 * Nông dân đọc thành "lúa giá 0 đồng" — vi phạm TOD0 §5: không hiển thị bất
 * kỳ dữ liệu số nào khi backend báo miss.
 */
import { describe, expect, it } from 'vitest';

import { formatNumber, formatPct, hasValue } from '../format';

describe('formatNumber', () => {
  it('hiển thị số thật', () => {
    expect(formatNumber(96433)).toBe('96.433');
  });

  it('null là THIẾU dữ liệu, không phải số 0', () => {
    expect(formatNumber(null)).toBe('—');
  });

  it('undefined là thiếu dữ liệu', () => {
    expect(formatNumber(undefined)).toBe('—');
  });

  it('chuỗi rỗng là thiếu dữ liệu', () => {
    expect(formatNumber('')).toBe('—');
  });

  it('số 0 thật vẫn hiển thị là 0', () => {
    expect(formatNumber(0)).toBe('0');
  });
});

describe('formatPct', () => {
  it('null không được thành +0.0%', () => {
    expect(formatPct(null)).toBe('—');
  });

  it('phần trăm thật giữ dấu', () => {
    expect(formatPct(2.5)).toBe('+2.5%');
    expect(formatPct(-1.25)).toBe('-1.3%');
  });

  it('0% thật vẫn hiển thị', () => {
    expect(formatPct(0)).toBe('+0.0%');
  });
});

describe('hasValue', () => {
  it('phân biệt thiếu dữ liệu với số 0', () => {
    expect(hasValue(0)).toBe(true);
    expect(hasValue(null)).toBe(false);
    expect(hasValue(undefined)).toBe(false);
    expect(hasValue('')).toBe(false);
  });
});
