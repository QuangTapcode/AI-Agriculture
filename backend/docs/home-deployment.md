# Triển khai `app.agriai.vn` trên máy hiện tại

Mô hình này giữ Ollama và toàn bộ dữ liệu trên máy Windows. Cloudflare Tunnel chuyển lưu lượng HTTPS tới frontend qua kết nối đi ra, không mở SQL Server, Redis, backend hoặc Ollama ra Internet.

## Chuẩn bị một lần

1. Thêm `agriai.vn` vào Cloudflare và trỏ nameserver tại nhà đăng ký tên miền theo hướng dẫn của Cloudflare.
2. Trong Cloudflare Zero Trust, tạo một tunnel và thêm public hostname `app.agriai.vn` với service `http://frontend:80`.
3. Sao chép `.env.home.example` thành `.env.home`, thay mật khẩu SQL Server, `SECRET_KEY` và tunnel token.
4. Sao lưu database hiện tại trước lần đầu chuyển sang `compose.home.yml`. File production gắn `/var/opt/mssql` vào volume `mssql_data`; cần restore bản sao lưu vào volume mới để giữ tài khoản và lịch sử hiện có.
5. Chạy:

```powershell
docker compose --env-file .env.home -f compose.home.yml up -d --build
```

Ứng dụng cũng có thể kiểm tra cục bộ tại `http://localhost:8080`.

## Tự chạy sau khi bật máy

- Docker Desktop phải bật `Start Docker Desktop when you sign in`.
- Ollama phải nằm trong Startup của Windows.
- Mọi service trong `compose.home.yml` dùng `restart: unless-stopped`.

Sau khi đăng nhập Windows, chờ Docker Desktop và SQL Server khởi động khoảng 30-90 giây rồi mở `https://app.agriai.vn`.

Nếu chủ động chạy `docker compose ... stop`, Docker sẽ hiểu đó là yêu cầu dừng và không tự bật các container đó. Dùng `docker compose --env-file .env.home -f compose.home.yml start` để bật lại.

## Kiểm tra

```powershell
docker compose --env-file .env.home -f compose.home.yml ps
Invoke-RestMethod http://localhost:8080/health
Invoke-RestMethod http://localhost:11434/api/tags
```

Trong giao diện, mở **Trợ lý AI → Kho tài liệu** để xem lần nạp tri thức gần nhất và số đoạn embedding.
