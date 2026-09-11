# Nhóm 5 — Vận hành nông nghiệp (Chất lượng, Thu hoạch, Mùa vụ, Cảnh báo, Thông báo)

Nhánh `feat/ui-field-command`. `deploy/agriai-demo-pages/_worker.js` nằm ngoài mọi commit giao diện.

## Phạm vi đã làm

| Page | Route | Trạng thái |
| --- | --- | --- |
| Kiểm định chất lượng | `/quality` | Xong |
| Dự báo thu hoạch | `/harvest` | Xong |
| Quản lý mùa vụ | `/season-management` | Xong |
| Cảnh báo | `/alerts` | Xong |
| Thông báo | `/notifications` | Xong |

## Lỗi nghiêm trọng: trang Cảnh báo sập khi phản hồi thiếu trường

`AlertSubscribe` gán thẳng phản hồi vào state (`setOptions(data)`). Một phản hồi
không kèm `crops` khiến `options.crops` thành `undefined`, và `.find()` ngay bên
dưới ném lỗi — toàn bộ route `/alerts` rơi xuống error boundary với màn hình
"Có lỗi xảy ra". Nay mọi danh sách được giữ đúng hình dạng mảng.

## Lỗi dữ liệu thật đã sửa

| Nơi | Vấn đề |
| --- | --- |
| Chất lượng, Thu hoạch | `(confidence * 100).toFixed(0)%` không có guard → in ra **`NaN%`** |
| Chất lượng | Cùng giá trị đó điều khiển `width` thanh tiến trình → thanh rỗng hoặc đầy ngẫu nhiên |
| Chất lượng | Kết quả quay video hạ `confidence` thiếu về `0` trước khi lưu |
| Thông báo | 4 ô thống kê và các chip lọc ép số thiếu về `0` → gọi API hỏng trông như tài khoản trống |
| Thông báo | Loader tự đóng dấu `source: 'database'` và `confidence: 0.7` lên summary |
| Cảnh báo | Badge nguồn dựng sẵn `source: 'database', confidence: 0.7` khi chưa có phản hồi |
| Cảnh báo | Toast báo "Đã quét 0 cảnh báo" khi backend không trả `triggered_count` |
| Mùa vụ | Độ tin cậy dự báo hiển thị `0%` khi thiếu |

## Accessibility đã sửa

- 11 `<label>` trên form Chất lượng, Thu hoạch và Cảnh báo không gắn với control nào.
- Hai `<select>` trang Chất lượng không có tên cho trình đọc màn hình.
- Tương phản: `emerald-600` và `primary-600` làm nền cho chữ trắng 14–16px chỉ đạt
  3.3–3.8:1; chữ phụ `gray-300/400` thấp tới 1.5:1; `red-600` trên nền canvas 4.46:1.
  Tất cả đã nâng lên trên 4.5:1.

## Kết quả kiểm thử

```
Unit (Vitest)      26 file, 104 test — pass
E2E (Playwright)   142 test trên 4 khung hình, 2 skip — pass
Build production   pass
```

Sửa thêm ở hạ tầng test: helper e2e trả đúng `text/event-stream` cho luồng thông
báo. Trước đó stub trả JSON khiến trình duyệt tự log lỗi MIME, và cổng "không có
lỗi console" đổ lỗi nhầm cho trang.

## Ảnh và video

`docs/redesign/evidence/group-5-operations/` — `quality-*`, `harvest-*`,
`season-*`, `alerts-*`, `notifications-*` cho cả bốn khung hình, kèm
`drawer-open-*` và `scroll-*.mp4`.
