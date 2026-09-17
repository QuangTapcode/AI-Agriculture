# Các phân hệ đã gỡ khỏi giao diện

AgriAI không còn hiển thị hai trang độc lập:

- **Dự báo thu hoạch** được đưa ra khỏi sidebar và khỏi route ứng dụng. Quản lý mùa vụ chỉ lưu ngày dự kiến do người dùng nhập; hệ thống không tự suy đoán ngày thu hoạch.
- **Phân tích thị trường** được đưa ra khỏi sidebar và khỏi route ứng dụng. Dữ liệu giá và tin thị trường vẫn có thể được dùng bên trong Định giá, Dashboard và Trợ lý AI khi API xác nhận nguồn.

Các URL cũ vẫn được giữ để không làm hỏng liên kết đã lưu:

| URL cũ | Trang đích |
| --- | --- |
| `/harvest`, `/harvest-forecast` | `/season-management` |
| `/market`, `/market-strategy` | `/dashboard` |

Redirect được áp dụng cả với prefix ngôn ngữ (`/vi/...`, `/en/...`). Các endpoint backend cũ chưa bị xóa để bảo toàn tương thích API; chúng không còn được gọi bởi trang độc lập nào.
