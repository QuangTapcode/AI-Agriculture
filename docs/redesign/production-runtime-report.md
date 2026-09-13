# Báo cáo phục hồi production — 13/09/2026

## Sự cố

`https://agriai-demo.pages.dev` từng trả HTTP 530. Hai nguyên nhân độc lập:

1. Cloudflare Quick Tunnel cũ đã hết hiệu lực (`Unauthorized: Tunnel not found`).
2. Nginx public giữ IP cũ của container backend sau khi Docker recreate, khiến
   `/health` và `/api/*` trả 502.

Container frontend local cũng bị lệch cấu hình: Compose công khai cổng 5173 nhưng
image Nginx cũ chỉ nghe cổng 80. Việc build lại `backend`, `frontend` và `worker`
đã đưa local về đúng cấu hình hiện tại.

## Sửa chữa

- `frontend/nginx.production.conf` dùng resolver Docker `127.0.0.11` và biến
  upstream để phân giải lại tên `backend` định kỳ.
- `scripts/ensure-public-web.ps1` kiểm tra Pages; nếu hỏng sẽ phục hồi container,
  tạo lại tunnel và cập nhật Pages proxy.
- `scripts/install-public-web-watchdog.ps1` cài scheduled task chạy mỗi giờ.
- Production image được build sạch, dùng font WOFF2 nội bộ và favicon AgriAI.

File `deploy/agriai-demo-pages/_worker.js` chứa URL tunnel tạm thời nên không nằm
trong commit, đúng quy tắc repository.

## Xác minh

Ngày 13/09/2026, các đường dẫn sau đều trả HTTP 200:

- `https://agriai-demo.pages.dev/`
- `https://agriai-demo.pages.dev/login`
- `https://agriai-demo.pages.dev/ai-chat`
- `https://agriai-demo.pages.dev/health`

`POST /api/public/contact-requests` với payload rỗng trả 422, xác nhận proxy API
đến backend và validation thật đang hoạt động. Scheduled task có
`LastTaskResult = 0` sau lần chạy thử.

## Lệnh kiểm tra thủ công

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ensure-public-web.ps1
Invoke-WebRequest https://agriai-demo.pages.dev/health -UseBasicParsing
```
