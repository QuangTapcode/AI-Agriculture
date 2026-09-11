import { describe, expect, it } from 'vitest';
import { thunderstormRisk } from '../weatherRisk';

describe('thunderstorm risk', () => {
  it('reports unknown when the hour carries no condition or weather code', () => {
    expect(thunderstormRisk({})).toMatchObject({ level: 'unknown', label: 'Chưa có dữ liệu' });
  });

  it('reports an active storm from the weather code', () => {
    expect(thunderstormRisk({ weather_code: 95 })).toMatchObject({ level: 'active' });
  });

  it('reports an active storm from the condition name', () => {
    expect(thunderstormRisk({ condition: 'thunderstorm_hail' })).toMatchObject({ level: 'active' });
  });

  it('flags heavy rain as elevated risk', () => {
    expect(thunderstormRisk({ condition: 'heavy_rain' })).toMatchObject({ level: 'elevated' });
  });

  it('only clears the risk when a condition was actually reported', () => {
    expect(thunderstormRisk({ condition: 'clear' })).toMatchObject({ level: 'none', label: 'Không có' });
  });
});
