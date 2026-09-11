# Nhóm 3 — Khung ứng dụng (Sidebar, Navbar, Dashboard, Báo cáo)

Nhánh `feat/ui-field-command`. Mọi thay đổi tunnel trong `deploy/agriai-demo-pages/_worker.js`
được giữ nguyên ngoài commit giao diện.

## Phạm vi đã làm

| Hạng mục | Trạng thái |
| --- | --- |
| Sidebar, Navbar, app shell responsive | Xong |
| Dashboard | Xong |
| Báo cáo và route `/reports` | Xong |
| Gộp 6 route cũ về page chuẩn | Xong |

## Kết quả kiểm thử

```
Unit (Vitest)      16 file, 71 test — pass
E2E (Playwright)   66 test trên 4 khung hình, 2 skip — pass
Backend (pytest)   478 pass, 7 skip, 1 fail (có sẵn, xem bên dưới)
Build production   pass
```

Bốn khung hình chạy đủ: 390×844, 768×1024, 1024×768, 1440×900.

Một test backend hỏng từ trước và không liên quan đến đợt này:
`test_port_convention.py::test_docker_expose_cong_chuan` đọc `docker-compose.yml`,
trong khi thay đổi backend của nhóm này chỉ gồm 3 dòng ở `app/api/response.py`.

## Lỗi dữ liệu thật đã phát hiện và sửa

1. `/reports` nằm trong danh sách route nhưng không có `<Route>` nào, nên rơi
   xuống trang 404 dù `ReportsPage` và service đã tồn tại.
2. Sáu page cũ (`/dashboard-new`, `/pricing-dashboard`, `/quality-check`,
   `/harvest-forecast`, `/market-strategy`, `/alerts-management`) không gọi API
   nào — chúng hardcode số liệu như `4.2 Tấn/Hecta`, `+12%`, và các dòng cảnh báo
   gắn nhãn "Cập nhật thời gian thực". Đã redirect về page chuẩn và xoá file.
   Không mất chức năng: so sánh giá theo vùng vốn đã nằm ở `/crop/:cropId`.
3. Ô "Tình trạng mùa vụ" ép giá trị thiếu thành `0`, khiến "chưa lấy được dữ
   liệu" trông giống "không có mùa vụ nào".
4. Ô độ tin cậy AI hiển thị `0%` khi backend không trả confidence.
5. Mọi dòng dự báo giá thiếu trường confidence đều bị gán nhãn "Tin cậy trung bình".
6. `getDashboardFullData` bịa `0.7` khi không có confidence, hardcode `0.72` cho
   risk summary, và chặn trần ở `0.78` — một giá trị thật `0.91` bị ghi đè thành `0.78`.
7. `api_response` và `success_response` ở backend đóng dấu `confidence: 0.0` lên
   mọi phản hồi không có độ tin cậy.
8. `RiskBadge` mặc định về "Rủi ro Thấp" khi thiếu `risk_level` — một lần gọi API
   hỏng biến thành lời trấn an rằng ruộng đang an toàn.
9. Badge "Trung tâm cảnh báo" hiển thị "0 cảnh báo" cả khi backend không trả
   trường `alert_center`.
10. Navbar hiển thị chấm thông báo chưa đọc mà không có dữ liệu nào phía sau.
11. Trang Báo cáo khởi tạo state bằng `0` và format bằng `Number(value || 0)`,
    nên tài khoản chưa có bản ghi nào vẫn thấy "0 đ" doanh thu và "0 kg" sản lượng.

## Lỗi chất lượng khác đã sửa

- Vitest nuốt luôn các file spec Playwright, nên `npm run check` không chạy được.
- Testing Library không dọn DOM giữa các test (thiếu `cleanup`), gây rò rỉ giữa các case.
- Build production hỏng: `ReceiptText` không tồn tại trong lucide-react đang cài.
- Navbar và page cùng render `<h1>`, mỗi trang có hai heading cấp một.
- Hai `<select>` trên Dashboard không có tên cho trình đọc màn hình và dùng
  `focus:outline-none`, xoá mất vòng focus bàn phím.
- Tagline trong header sidebar tràn khỏi viền 64px.
- Tiêu đề "Thời tiết hiện tại" bị cắt cụt, badge rủi ro xuống 3 dòng.

## Cổng chất lượng

| Tiêu chí | Kết quả |
| --- | --- |
| Không có dữ liệu mẫu trình bày như dữ liệu thật | Đạt — 11 điểm vi phạm ở trên đã sửa |
| Không có lỗi console hoặc request hỏng bị che | Đạt — e2e assert `consoleErrors` rỗng |
| Không tràn ngang ở 4 khung hình | Đạt — assert `scrollWidth <= clientWidth` |
| Chuột, bàn phím, cảm ứng | Đạt — drawer mở/đóng bằng nút, Escape; link focus được |
| Focus rõ, tương phản WCAG AA, reduced motion | Đạt — axe không còn vi phạm critical/serious |
| Loading, empty, lỗi, cache, live đều có test | Đạt ở tầng dữ liệu; xem ghi chú |
| Build production và toàn bộ test cũ vẫn chạy | Đạt |

## Ảnh và video

Thư mục `docs/redesign/evidence/group-3-app-shell/` (không commit media):

- `dashboard-desktop-1440.png`, `dashboard-mobile-390.png`,
  `dashboard-tablet-768.png`, `dashboard-tablet-1024.png`
- `reports-*.png` cho cùng bốn khung hình
- `drawer-open-mobile-390.png`, `drawer-open-tablet-768.png`
- `scroll-desktop-1440.webm`, `scroll-mobile-390.webm`

Video đang ở định dạng WebM chứ chưa phải MP4: ffmpeg đi kèm Playwright là bản
rút gọn chỉ có muxer webm, và máy này chưa cài ffmpeg hệ thống. Cài ffmpeg là đủ
để xuất MP4, cần bạn duyệt trước khi tôi cài.

Tạo lại toàn bộ:

```bash
cd frontend
npx playwright test tests/e2e/capture-evidence.spec.js --project=desktop-1440 --project=mobile-390
```

## Ghi chú còn mở

- Trạng thái cache và live của Dashboard mới được phủ ở tầng `normalizeDataMeta`
  và `dashboardApi`; chưa có test render riêng cho từng trạng thái trên page.
  Sẽ bổ sung khi làm nhóm dữ liệu thị trường, nơi badge nguồn là trọng tâm.
- `unwrapApiResponse` trả về cả phong bì lẫn payload phẳng do backend spread
  `dict(data)`. Việc này đang chạy đúng nhưng dễ gây nhầm; nên tách rõ ở một đợt
  riêng thay vì sửa kèm trong đợt giao diện.
