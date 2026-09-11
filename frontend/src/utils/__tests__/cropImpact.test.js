import { describe, expect, it } from 'vitest';
import { cropImpacts } from '../cropImpact';

/**
 * Lời khuyên nông vụ được suy ra từ số đo thời tiết. Nếu số đo thiếu mà vẫn suy
 * ra lời khuyên, nông dân nhận một chỉ dẫn có thật về hành động (phun thuốc,
 * bón phân) dựa trên dữ liệu không tồn tại.
 */
describe('crop impact advice', () => {
  it('gives no advice at all when the hour carries no measurements', () => {
    expect(cropImpacts({})).toEqual([]);
  });

  it('never suggests spraying when rain probability is unknown', () => {
    const advice = cropImpacts({ humidity: 60 });
    const text = advice.map((item) => item.text).join(' ');

    expect(text).not.toMatch(/thích hợp phun thuốc/i);
    expect(text).not.toMatch(/Ít mưa/i);
  });

  it('does not assume a comfortable 25 degrees when temperature is missing', () => {
    const advice = cropImpacts({ humidity: 90 });

    expect(advice.some((item) => /nhiệt độ/i.test(item.text))).toBe(false);
    expect(advice.some((item) => /nấm bệnh/i.test(item.text))).toBe(true);
  });

  it('still reports each risk the measurements actually support', () => {
    const advice = cropImpacts({
      humidity: 90,
      rain_probability: 80,
      wind_speed: 30,
      uv_index: 9,
      temperature: 39,
    });
    const text = advice.map((item) => item.text).join(' ');

    expect(text).toMatch(/nấm bệnh/i);
    expect(text).toMatch(/tránh bón phân/i);
    expect(text).toMatch(/không phun hóa chất/i);
    expect(text).toMatch(/UV cao/i);
    expect(text).toMatch(/stress nhiệt/i);
  });

  it('reads a genuine zero as a real measurement, not as missing', () => {
    const advice = cropImpacts({ rain_probability: 0 });

    expect(advice.map((item) => item.text).join(' ')).toMatch(/Ít mưa/i);
  });
});
