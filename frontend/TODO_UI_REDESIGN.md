# TODO — Thiết kế lại giao diện AgriAI

> Mục tiêu: ít chữ, số liệu có nguồn, hình ảnh hiện đại, chuyển động rõ nhưng nhẹ, dùng tốt trên desktop và điện thoại.
>
> Tham chiếu chuyển động: [video 1](https://www.tiktok.com/@tvcdevcntt/video/7649237352526662933) · [video 2](https://www.tiktok.com/@tvcdevcntt/video/7677468850878778644).

## Nguyên tắc đã chốt

- [ ] Dùng phong cách **Agri Intelligence**: nền tối xanh rừng, lớp kính mờ, ánh sáng mềm, bản đồ/địa hình và chuyển động không trọng lực lấy cảm hứng từ hai video Antigravity Pro.
- [ ] Mỗi màn hình chỉ có **một hành động chính**; nội dung phụ đưa vào tooltip, drawer hoặc trang chi tiết.
- [ ] Mỗi thẻ dữ liệu chỉ hiển thị: **giá trị, đơn vị, xu hướng, thời điểm, nguồn**.
- [ ] Không hiển thị số minh họa như số thật. Mọi thông số phải có trạng thái `live`, `cached`, `sample` hoặc `unavailable`.
- [ ] Animation có mục đích: giúp nhìn thấy thứ tự nội dung, thay đổi trạng thái và phản hồi thao tác.
- [ ] Tôn trọng `prefers-reduced-motion`; không để hiệu ứng làm chậm thao tác hoặc che dữ liệu.

## P0 — Sửa độ tin cậy của số liệu

- [ ] Lập bảng kiểm kê toàn bộ KPI trên frontend: tên trường, API, đơn vị, thời điểm cập nhật, fallback và màn hình sử dụng.
- [ ] Xóa hoặc thay bằng dữ liệu thật các số đang hard-code tại trang chủ: `5+`, `24/7`, `+3.2%`, “Ổn định”, “Sắp tới”.
- [ ] Thay các nhãn “Dữ liệu thời gian thực” bằng nhãn nguồn thực tế từ response API.
- [ ] Hiển thị `—` cùng lý do ngắn khi không có dữ liệu; không dùng `0` để thay cho dữ liệu thiếu.
- [ ] Chuẩn hóa tiền tệ, phần trăm, lượng mưa, nhiệt độ, khối lượng và múi giờ Việt Nam.
- [ ] Thêm “Cập nhật lúc” và tên nguồn cho giá, thời tiết, mùa vụ, cảnh báo, tài liệu RAG.
- [ ] Đối chiếu số liệu giữa Trang chủ, Dashboard, Giá, Thị trường và Thông báo; cùng một chỉ số phải cho cùng kết quả.
- [ ] Viết test cho formatter và mapping API; thêm test chống hiển thị dữ liệu mẫu như dữ liệu thật.

## P1 — Nền tảng thiết kế chung

- [ ] Tạo design tokens: màu, typography, radius, shadow, spacing, z-index, duration và easing.
- [ ] Chọn tối đa 2 font; giảm số mức cỡ chữ và độ đậm đang dùng.
- [ ] Tạo bộ component dùng chung: `PageHeader`, `MetricCard`, `SourceBadge`, `EmptyState`, `Skeleton`, `FilterBar`, `DataTable`, `Drawer`, `Toast`.
- [ ] Chuẩn hóa trạng thái hover, focus, active, disabled, loading, success và error.
- [ ] Chuẩn hóa icon Lucide; bỏ emoji và icon không cùng phong cách.
- [ ] Thiết kế grid responsive 4 mốc: mobile, tablet, laptop, desktop lớn.
- [ ] Giới hạn chiều rộng nội dung, loại bỏ scroll ngang và khoảng trống vô nghĩa.
- [ ] Thêm dark surface cho khu vực quan trọng nhưng giữ độ tương phản WCAG AA.

## P2 — Motion và tương tác

- [ ] Tạo hiệu ứng scroll reveal dùng `IntersectionObserver`: fade + translate + blur nhẹ.
- [ ] Stagger các card 40–70 ms; không animate toàn trang cùng lúc.
- [ ] Hero có nền hạt/đường địa hình chuyển động chậm và lớp parallax theo chuột.
- [ ] Card nổi 3D nhẹ khi hover; giới hạn góc nghiêng và tắt trên thiết bị cảm ứng.
- [ ] CTA có icon dịch chuyển, ánh sáng chạy ngắn và trạng thái nhấn rõ ràng.
- [ ] KPI animate khi dữ liệu đã tải; không chạy số giả trước khi API trả về.
- [ ] Biểu đồ animate khi vào viewport và khi đổi bộ lọc.
- [ ] Sidebar dùng indicator trượt; submenu mở/đóng có height + opacity transition.
- [ ] Modal/drawer dùng spring nhẹ; toast có enter/exit và thanh thời gian.
- [ ] Skeleton có shimmer chậm; tránh spinner giữa vùng trống lớn.
- [ ] Kiểm tra hiệu năng: giữ 60 fps, không gây layout shift, không animate thuộc tính kích thước khi không cần.

## P3 — Làm lại khu vực công khai

### Trang chủ `/`

- [ ] Rút hero còn 1 headline, 1 câu mô tả, 2 CTA.
- [ ] Thay khối “Tình hình hôm nay” bằng dữ liệu thật hoặc preview có nhãn “Minh họa”.
- [ ] Dùng một cảnh động xuyên suốt: ruộng/vùng trồng → dữ liệu → khuyến nghị AI.
- [ ] Chỉ giữ 3 lợi ích chính; chuyển mô tả dài sang trang Tính năng.
- [ ] Thêm section kể chuyện theo scroll: thời tiết → giá → mùa vụ → trợ lý.

### Tính năng `/features`

- [ ] Chuyển danh sách dài thành 3 workflow có thể tương tác.
- [ ] Hover/focus vào workflow để preview màn hình và nguồn dữ liệu.
- [ ] Gắn trạng thái “Đang hoạt động”, “Beta”, “Sắp có” theo cấu hình thật.

### Bài viết `/articles`

- [ ] Thay bài viết hard-code bằng API/CMS hoặc ghi rõ “Nội dung mẫu”.
- [ ] Dùng thẻ ảnh lớn, tiêu đề ngắn, thời gian đọc và nguồn.
- [ ] Thêm hover ảnh zoom nhẹ, category filter chuyển động và skeleton tải.
- [ ] Bỏ các khối hướng dẫn nội bộ khỏi giao diện người dùng.

### Gói dịch vụ `/pricing-plans`

- [ ] Chỉ hiển thị gói đã tồn tại trong backend/billing.
- [ ] Bỏ nội dung “Nên làm thêm…” và mọi ghi chú dành cho lập trình viên.
- [ ] Thay bảng gây scroll ngang bằng bảng responsive hoặc so sánh 2 gói mỗi lần trên mobile.
- [ ] Làm rõ giá, chu kỳ, giới hạn và CTA; không dùng số chưa được xác nhận.

### Liên hệ `/contact`

- [ ] Bỏ khối “Nâng cấp hệ thống nên có”.
- [ ] Rút form còn các trường cần thiết và kết nối endpoint lưu yêu cầu thật.
- [ ] Thêm validation tức thời, trạng thái gửi và mã yêu cầu sau khi thành công.

## P4 — Làm lại khu vực trong hệ thống

### Khung ứng dụng

- [ ] Thu gọn sidebar; nhóm menu theo “Theo dõi”, “Phân tích”, “AI”, “Hệ thống”.
- [ ] Thêm quick command/search và breadcrumb ngắn.
- [ ] Dùng page transition nhẹ khi đổi route; giữ nguyên vị trí scroll hợp lý.
- [ ] Navbar hiển thị trạng thái dữ liệu, thông báo và tài khoản rõ hơn.

### Dashboard

- [ ] Đưa “Việc cần làm hôm nay” lên đầu, tối đa 3 hành động.
- [ ] Tạo một hero data card theo vùng và cây trồng đã chọn.
- [ ] Giảm số card cùng cấp; nhóm thời tiết, giá và rủi ro theo mức ưu tiên.
- [ ] Cho phép drill-down bằng drawer thay vì đẩy quá nhiều chữ vào card.

### Thời tiết, Giá và Thị trường

- [ ] Dùng chung bộ chọn khu vực/cây trồng và lưu lựa chọn của người dùng.
- [ ] Biểu đồ có tooltip, đường chuẩn, khoảng tin cậy và nguồn.
- [ ] Nêu rõ dữ liệu live/cache/mất kết nối ngay cạnh chỉ số.
- [ ] Thêm hover crosshair, transition khi đổi vùng và empty/error state đẹp.

### Kiểm định chất lượng và Dự báo thu hoạch

- [ ] Chuyển thành flow từng bước: nhập dữ liệu → kiểm tra → kết quả → hành động.
- [ ] Preview ảnh có zoom, trạng thái upload và overlay kết quả trực quan.
- [ ] Phân biệt xác suất mô hình với kết luận; hiển thị phiên bản model và thời điểm chạy.

### Trợ lý AI và Kho tài liệu

- [ ] Thu hẹp vùng trống của chat; đưa gợi ý thành prompt chips có icon.
- [ ] Stream câu trả lời và hiển thị từng giai đoạn: tìm nguồn → tổng hợp → hoàn tất.
- [ ] Nguồn RAG hiển thị dạng citation card gọn, mở rộng khi cần.
- [ ] Kho tài liệu có tab “Mới”, “Đang dùng”, “Lỗi”, “Bản cũ”; thêm sort và drawer chi tiết.
- [ ] Animation cho tin nhắn mới, trạng thái suy luận và cập nhật chỉ mục.

### Mùa vụ, Cảnh báo, Thông báo và Cài đặt

- [ ] Mùa vụ dùng timeline/calendar thay cho danh sách dày chữ.
- [ ] Cảnh báo dùng rule builder trực quan và preview điều kiện.
- [ ] Thông báo nhóm theo ngày/mức độ, thao tác đọc/xóa có undo.
- [ ] Cài đặt chia section rõ, lưu từng phần và báo trạng thái kênh ngay tại chỗ.

## P5 — Nội dung, responsive và chất lượng

- [ ] Giới hạn headline tối đa 2 dòng, card description tối đa 2–3 dòng.
- [ ] Dùng động từ ngắn cho CTA: “Xem giá”, “Kiểm tra”, “Hỏi AI”, “Tạo cảnh báo”.
- [ ] Kiểm tra ở 360, 390, 768, 1024, 1440 và 1920 px.
- [ ] Bảo đảm vùng bấm tối thiểu 44 px, focus bằng bàn phím và screen reader label.
- [ ] Thêm visual regression cho các route chính và test không có scroll ngang.
- [ ] Đạt Lighthouse mục tiêu: Performance ≥ 85, Accessibility ≥ 95, CLS < 0.1.
- [ ] Theo dõi bundle; lazy-load hiệu ứng nặng và không tải WebGL ở màn hình không dùng.

## Thứ tự triển khai đề xuất

1. [ ] Chốt một concept từ prototype/video.
2. [ ] Hoàn thành P0 để số liệu đúng trước khi trang trí.
3. [ ] Làm design system và app shell.
4. [ ] Làm Trang chủ + Dashboard làm mẫu chuẩn.
5. [ ] Áp dụng chuẩn cho từng cụm chức năng.
6. [ ] Kiểm tra responsive, accessibility và performance.
7. [ ] Triển khai thử nghiệm, thu phản hồi rồi mới thay toàn bộ production.

## Tiêu chí hoàn thành

- [ ] Không còn số hoặc tuyên bố realtime hard-code được trình bày như dữ liệu thật.
- [ ] Không còn ghi chú nội bộ dành cho lập trình viên trên trang người dùng.
- [ ] Mọi màn hình có loading, empty, error và stale state nhất quán.
- [ ] Mọi thành phần tương tác có hover/focus/pressed và phản hồi trực quan.
- [ ] Scroll reveal hoạt động mượt và tự tắt khi người dùng giảm chuyển động.
- [ ] Không có scroll ngang ngoài bảng/biểu đồ được thiết kế chủ động.
- [ ] Giao diện production qua kiểm thử dữ liệu, responsive và visual regression.
