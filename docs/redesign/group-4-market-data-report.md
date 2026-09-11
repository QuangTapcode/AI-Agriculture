# Nhóm 4 — Dữ liệu thị trường (Thời tiết, Định giá, Chi tiết cây trồng, Phân tích thị trường)

Nhánh `feat/ui-field-command`. `deploy/agriai-demo-pages/_worker.js` vẫn nằm ngoài mọi commit giao diện.

## Phạm vi đã làm

| Page | Route | Trạng thái |
| --- | --- | --- |
| Thời tiết | `/weather` | Xong |
| Định giá | `/pricing` | Xong |
| Chi tiết cây trồng | `/crop/:cropId` | Xong |
| Phân tích thị trường | `/market` | Xong |

## Kết quả kiểm thử

```
Unit (Vitest)      21 file, 93 test — pass
E2E (Playwright)   94 test trên 4 khung hình, 2 skip — pass
Build production   pass
```

## Lỗi dữ liệu thật đã phát hiện và sửa

### Nghiêm trọng nhất: lời khuyên canh tác sinh ra từ dữ liệu trống

`cropImpacts` trong trang Thời tiết ép mọi số đo thiếu về `0`, riêng nhiệt độ về
`25`. Một giờ **không có dữ liệu nào** vì thế rơi trúng nhánh "an toàn" của từng
quy tắc, và trang hiển thị:

> Độ ẩm phù hợp canh tác. — Ít mưa, thích hợp phun thuốc, bón phân.

Đây là chỉ dẫn hành động thật (phun thuốc, bón phân) suy ra từ payload rỗng.
Giờ mỗi ngưỡng chỉ được xét khi chính số đo của nó tồn tại; số `0` thật vẫn là
một số đo hợp lệ; giờ không có số đo nào thì nói rõ là chưa đủ dữ liệu để khuyến nghị.

Cùng dạng: `thunderRisk` trả nhãn xanh "Không có" khi giờ đó thiếu cả
`condition` lẫn `weather_code`.

### Bảng giá vùng miền bịa ra ở trang Chi tiết cây trồng

Khi `compareRegions` không trả dữ liệu, trang **tự dựng hai dòng so sánh**: gán
`typical_price_max` của cây trồng thành giá "Hà Nội / Bắc Bộ" và
`typical_price_min` thành giá "Cần Thơ / Mekong". Một khoảng giá tham khảo chung
bị trình bày thành giá đo được theo vùng — đúng loại con số mà người ta bán cả
vụ mùa dựa vào. Đã bỏ hoàn toàn, chỉ hiện vùng nào backend thực sự trả về.

### Các điểm còn lại

| Nơi | Vấn đề |
| --- | --- |
| Chi tiết cây trồng | `current_price` lùi về `typical_price_min` → cận dưới tham khảo thành giá hôm nay |
| Chi tiết cây trồng | Biến động ngày mặc định `'+0.0%'` — một xu hướng phẳng nhưng mang dấu dương |
| Chi tiết cây trồng | Mùa vụ không rõ bị đóng dấu `CẬP NHẬT HÔM NAY`, rồi `Quanh năm` |
| Chi tiết cây trồng | Nhãn xanh "Dữ liệu thực" nằm trên panel dự báo rỗng |
| Chi tiết cây trồng | Biểu đồ vẽ điểm thiếu thành `0` → cú sập giá không có thật; nay ngắt đường |
| Chi tiết cây trồng | Chênh lệch dự báo tính trên mốc `0` khi thiếu dòng đầu → chênh lệch bằng đúng giá |
| Định giá | Loại nguồn mặc định `'database'` — gán xuất xứ cho dữ liệu không khai báo |
| Định giá | Độ tin cậy thiếu hiển thị `0%`; giá tham chiếu quốc tế thiếu hiển thị `0` |
| Phân tích thị trường | Badge giá cửa hàng hardcode `confidence: 0.72` và nguồn `Gemini Google Search` |
| Phân tích thị trường | Xu hướng 30 ngày mặc định `'Ổn định'` khi thiếu `direction` |
| Phân tích thị trường | Dòng vùng miền in `0 đ/kg` và `0.00%` cho trường không có trong response |

Quy tắc "thiếu khác 0" nay nằm một chỗ: `formatConfidence` trong `utils/format.js`.

## Lỗi chức năng và accessibility đã sửa

- Nút **Chia sẻ** và **Đặt cảnh báo giá** trên trang cây trồng không có handler —
  bấm không làm gì. Nút cảnh báo nay dẫn sang `/alerts` kèm cây trồng (chức năng
  đã có thật), nút chia sẻ dùng Web Share API và fallback clipboard. Cả hai có tên
  cho trình đọc màn hình.
- Bảy `<label>` trên form Định giá và Phân tích thị trường không gắn với input nào.

## Cổng chất lượng

| Tiêu chí | Kết quả |
| --- | --- |
| Không có dữ liệu mẫu trình bày như dữ liệu thật | Đạt — e2e quét lại các chuỗi đã gỡ |
| Không có lỗi console hoặc request hỏng bị che | Đạt |
| Không tràn ngang ở 390×844, 768×1024, 1024×768, 1440×900 | Đạt |
| Chuột, bàn phím, cảm ứng | Đạt |
| Focus rõ, tương phản WCAG AA, reduced motion | Đạt — axe không còn vi phạm critical/serious |
| Loading, empty, lỗi, cache, live đều có test | Đạt cho empty/lỗi/dữ liệu thật; xem ghi chú |
| Build production và toàn bộ test cũ vẫn chạy | Đạt |

## Ảnh và video

`docs/redesign/evidence/group-4-market-data/` (media không commit):

- `weather-*.png`, `pricing-*.png`, `crop-detail-*.png`, `market-*.png` cho cả
  bốn khung hình
- `drawer-open-mobile-390.png`, `drawer-open-tablet-768.png`
- `scroll-*.mp4` (H.264) kèm `.webm` gốc

Tạo lại:

```bash
cd frontend
EVIDENCE_GROUP=group-4-market-data npx playwright test tests/e2e/capture-evidence.spec.js
cd ../docs/redesign/evidence/group-4-market-data
for f in *.webm; do ffmpeg -y -i "$f" -c:v libx264 -preset slow -crf 23 \
  -pix_fmt yuv420p -movflags +faststart \
  -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" "${f%.webm}.mp4"; done
```

## Ghi chú còn mở

- Bốn trang này chưa có test render riêng cho trạng thái `cached` so với `live`.
  Badge nguồn đã nhận đúng metadata, nhưng phần khẳng định "đang xem bản cache"
  nên được phủ khi làm badge nguồn dùng chung.
- Tiêu đề trang Thời tiết vẫn viết "Theo dõi thời gian thực". Đây là mô tả tính
  năng chứ không phải nhãn gắn lên một con số cụ thể, và nguồn Open-Meteo có làm
  mới thật, nên tôi giữ nguyên. Nếu bạn muốn siết đúng câu chữ thì sửa được ngay.
