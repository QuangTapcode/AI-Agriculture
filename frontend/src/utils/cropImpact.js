import { hasValue } from './format';

/**
 * Quy tắc suy ra ảnh hưởng canh tác từ số đo thời tiết theo giờ.
 *
 * Vì sao tách khỏi trang: đây là lời khuyên hành động — phun thuốc, bón phân,
 * che nắng. Trước đây các số đo thiếu bị ép về `?? 0` (và nhiệt độ về `?? 25`),
 * nên một giờ không có dữ liệu vẫn rơi vào nhánh "an toàn" và trang khuyên
 * nông dân rằng trời ít mưa, thích hợp phun thuốc. Mỗi ngưỡng dưới đây chỉ được
 * đánh giá khi chính số đo của nó tồn tại; số 0 thật vẫn là một số đo hợp lệ.
 */
export function cropImpacts(hour = {}) {
  const items = [];

  const humidity = hour?.humidity;
  const rain = hour?.rain_probability;
  const wind = hour?.wind_speed;
  const uv = hour?.uv_index;
  const temperature = hour?.temperature;

  if (hasValue(humidity)) {
    const value = Number(humidity);
    if (value > 85) {
      items.push({ level: 'high', text: 'Độ ẩm cao — nguy cơ nấm bệnh, đạo ôn. Không phun thuốc.' });
    } else if (value > 70) {
      items.push({ level: 'medium', text: 'Độ ẩm trung bình — theo dõi bệnh hại lá.' });
    } else {
      items.push({ level: 'ok', text: 'Độ ẩm phù hợp canh tác.' });
    }
  }

  if (hasValue(rain)) {
    const value = Number(rain);
    if (value > 70) {
      items.push({ level: 'high', text: 'Xác suất mưa cao — tránh bón phân, phun thuốc.' });
    } else if (value > 40) {
      items.push({ level: 'medium', text: 'Có thể có mưa — chuẩn bị thoát nước.' });
    } else {
      items.push({ level: 'ok', text: 'Ít mưa — thích hợp phun thuốc, bón phân.' });
    }
  }

  if (hasValue(wind)) {
    const value = Number(wind);
    if (value > 25) {
      items.push({
        level: 'high',
        text: `Gió ${value.toLocaleString('vi-VN', { maximumFractionDigits: 0 })} km/h — không phun hóa chất, nguy cơ đổ cây.`,
      });
    } else if (value > 15) {
      items.push({ level: 'medium', text: 'Gió vừa — phun thuốc cẩn thận, chọn vòi định hướng.' });
    }
  }

  if (hasValue(uv) && Number(uv) > 7) {
    items.push({ level: 'medium', text: 'UV cao — che phủ cây non, tưới sáng sớm hoặc chiều tối.' });
  }

  if (hasValue(temperature)) {
    const value = Number(temperature);
    if (value > 37) {
      items.push({
        level: 'high',
        text: `Nhiệt độ ${value.toLocaleString('vi-VN', { maximumFractionDigits: 1 })}°C — cây dễ stress nhiệt. Tăng tưới, che nắng.`,
      });
    } else if (value < 15) {
      items.push({ level: 'medium', text: 'Nhiệt độ thấp — cây lúa và rau màu có thể bị lạnh cóng.' });
    }
  }

  return items;
}

export default cropImpacts;
