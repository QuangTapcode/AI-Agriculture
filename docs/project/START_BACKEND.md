# 🚀 Hướng dẫn Chạy Backend

## Bước 1: Mở Terminal trong thư mục backend

```bash
cd backend
```

## Bước 2: Chạy Backend Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Hoặc đơn giản hơn:**
```bash
uvicorn app.main:app --reload
```

## ✅ Kết quả mong đợi

Bạn sẽ thấy:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## 🌐 Truy cập

- **API Docs (Swagger):** http://localhost:8000/docs
- **API Docs (ReDoc):** http://localhost:8000/redoc
- **API Base URL:** http://localhost:8000/api

## 🛑 Dừng Backend

Nhấn `CTRL + C` trong terminal

---

## 📝 Lưu ý

1. Đảm bảo SQL Server đang chạy
2. Database `NongNghiepAI` đã được tạo với **10 bảng** (chạy file `docs/database/NongNghiepAI_Full.sql`)
3. File `.env` đã cấu hình đúng connection string
4. Đã cài đặt dependencies: `pip install -r requirements.txt`

## 🗄️ 10 Bảng trong Database

1. **Users** - Người dùng (nông dân, admin)
2. **CropTypes** - Loại nông sản
3. **WeatherData** - Dữ liệu thời tiết
4. **HarvestSchedule** - Lịch trình thu hoạch
5. **MarketPrices** - Giá thị trường hiện tại
6. **PriceHistory** - Lịch sử biến động giá
7. **PriceForecastResults** - Kết quả dự báo giá từ AI
8. **QualityRecords** - Kết quả kiểm tra chất lượng
9. **AlertSubscriptions** - Đăng ký cảnh báo giá
10. **AIConversations** - Lịch sử hội thoại với AI
