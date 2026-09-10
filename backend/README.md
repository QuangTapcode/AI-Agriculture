# AgriAI — Backend

FastAPI backend cho hệ thống tư vấn nông nghiệp thông minh: dự báo thu hoạch, giá nông sản, kiểm tra chất lượng hình ảnh, gợi ý kênh tiêu thụ, cảnh báo giá và chatbot AI.

---

## Mục lục

- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt](#cài-đặt)
- [Cấu hình môi trường (.env)](#cấu-hình-môi-trường-env)
- [Khởi động server](#khởi-động-server)
- [Database](#database)
- [Tài khoản mặc định](#tài-khoản-mặc-định)
- [API Reference](#api-reference)
- [Chạy tests](#chạy-tests)

---

## Công nghệ sử dụng

| Layer | Công nghệ |
|-------|-----------|
| Web framework | FastAPI 0.115+ |
| ASGI server | Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Validation | Pydantic 2.8+ |
| Database chính | MS SQL Server 2019+ |
| Database dự phòng | SQLite (tự động fallback) |
| Auth | JWT (HS256) + passlib pbkdf2_sha256 |
| AI Chat | Google Gemini 2.5-flash |
| Tìm kiếm tin tức/giá | Tavily Search API |
| Thời tiết | Open-Meteo (miễn phí, không cần API key) |
| Kiểm tra chất lượng | YOLOv8 (ultralytics) |
| Dự báo giá | Prophet (Meta) |
| Task queue | Celery + Redis |
| Web crawler | httpx + Scrapy |
| HTTP client | httpx |
| Testing | pytest + pytest-asyncio |

---

## Cấu trúc dự án

```
backend/
├── app/
│   ├── api/                  # Route handlers (FastAPI routers)
│   │   ├── auth.py           # Đăng ký / đăng nhập / thông tin user
│   │   ├── chat.py           # Chatbot AI (Gemini) + Price Q&A (Tavily)
│   │   ├── crops.py          # Danh mục cây trồng
│   │   ├── harvest.py        # Dự báo thu hoạch & lịch canh tác
│   │   ├── quality.py        # Kiểm tra chất lượng ảnh (YOLOv8)
│   │   ├── pricing.py        # Giá thị trường & gợi ý giá bán
│   │   ├── price_forecast.py # Dự báo giá 7–30 ngày (Prophet)
│   │   ├── market.py         # Gợi ý kênh tiêu thụ
│   │   ├── alert.py          # Cảnh báo giá
│   │   ├── weather.py        # Thời tiết (Open-Meteo)
│   │   ├── crawler.py        # Kết quả crawler giá thực tế
│   │   └── news.py           # Tin tức & tác động thị trường (Tavily)
│   ├── core/
│   │   ├── config.py         # Pydantic Settings (đọc .env)
│   │   ├── database.py       # SQLAlchemy engine, SessionLocal, init_db
│   │   ├── security.py       # JWT, password hashing
│   │   └── redis_client.py   # Redis connection
│   ├── models/               # SQLAlchemy ORM models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Business logic
│   ├── repositories/         # DB query helpers
│   ├── integrations/         # Clients bên ngoài (Gemini, Tavily, v.v.)
│   ├── tasks/                # Background tasks (crawler loop, alerts)
│   └── main.py               # FastAPI app entry point
├── ai_models/
│   ├── harvest_forecast/     # Prophet model dự báo ngày thu hoạch
│   ├── price_forecast/       # Prophet model dự báo giá
│   └── yolo_inference.py     # YOLOv8 inference wrapper
├── crawler/                  # Scrapy project (Agro, GiaVN, NongNghiep)
├── tests/                    # pytest test suite
├── seed_db.py                # Seed CropTypes vào DB
├── requirements.txt          # Tất cả dependencies
└── .env                      # Biến môi trường (không commit)
```

---

## Yêu cầu hệ thống

- **Python** 3.11 hoặc 3.12 (khuyến nghị 3.11 vì Prophet/ultralytics chưa có wheel cho 3.14)
- **MS SQL Server** với instance `.\QUANGQUANG` và database `NongNghiepAI` (hoặc SQLite cho dev)
- **ODBC Driver 17 for SQL Server** (nếu dùng SQL Server)
- **Redis** (tuỳ chọn — chỉ cần nếu dùng Celery hoặc cache)

---

## Cài đặt

```bash
# 1. Di chuyển vào thư mục backend
cd backend

# 2. Tạo và kích hoạt virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. Nâng cấp pip
python -m pip install --upgrade pip setuptools wheel

# 4. Cài đặt dependencies
pip install -r requirements.txt
```

> **Lưu ý Windows:** Nếu Python 3.14 không có wheel cho `prophet` hoặc `ultralytics`, hãy dùng Python 3.11/3.12.

---

## Cấu hình môi trường (.env)

Tạo file `.env` trong thư mục `backend/` với nội dung sau:

```env
# ── Database ──────────────────────────────────────────────────────────────────
# SQL Server (chính):
DATABASE_URL=mssql+pyodbc://.\QUANGQUANG/NongNghiepAI?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes&TrustServerCertificate=yes

# Hoặc SQLite (fallback tự động khi SQL Server không kết nối được):
# DATABASE_URL=sqlite:///./agri_ai.db

# ── App ───────────────────────────────────────────────────────────────────────
ENVIRONMENT=development
SECRET_KEY=nongsan-ai-2026-secret-key-change-in-prod
UPLOAD_DIR=storage/uploads

# ── AI APIs ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY=<your-gemini-api-key>
# CLAUDE_API_KEY=sk-ant-...   # Không bắt buộc

# ── Tavily Search API (lấy tại https://app.tavily.com) ────────────────────────
TAVILY_API_KEY=<your-tavily-api-key>

# ── Thời tiết (Open-Meteo — miễn phí, không cần key) ─────────────────────────
WEATHER_PROVIDER=open-meteo
OPEN_METEO_BASE_URL=https://api.open-meteo.com
WEATHER_TIMEOUT_SECONDS=8.0
WEATHER_RETRY_COUNT=2

# ── Crawler ───────────────────────────────────────────────────────────────────
# 60   = mỗi phút (dev/demo)
# 1800 = mỗi 30 phút (production)
CRAWL_INTERVAL_SECONDS=1800

# ── Email alerts (SMTP) ── để trống = không gửi mail ─────────────────────────
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your@gmail.com
# SMTP_PASSWORD=app-password
# FROM_EMAIL=noreply@nongsan.vn

# ── Redis (chỉ cần cho Celery / cache) ───────────────────────────────────────
# REDIS_URL=redis://localhost:6379/0

# ── Fix encoding trên Windows ─────────────────────────────────────────────────
PYTHONUTF8=1
PYTHONIOENCODING=utf-8
```

---

## Khởi động server

```bash
# Cách thông thường (port 8000, auto-reload khi phát triển)
uvicorn app.main:app --reload --port 8000

# Chạy trực tiếp
python app/main.py
```

Sau khi khởi động:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health check:** http://localhost:8000/health
- **DB test:** http://localhost:8000/db-test

> Khi server khởi động, hệ thống tự động chạy crawler lần đầu để seed 7 ngày dữ liệu giá và thời tiết vào DB.

---

## Database

### SQL Server (khuyến nghị)

1. Tạo database `NongNghiepAI` trên SQL Server instance `.\QUANGQUANG`
2. Chạy file SQL schema:
   ```bash
   # Dùng SSMS hoặc sqlcmd
   sqlcmd -S .\QUANGQUANG -i ..\NongNghiepAI_Full.sql
   ```
3. Cấu hình `DATABASE_URL` trong `.env` như ví dụ trên
4. Khởi động server — SQLAlchemy tự `init_db()` để tạo các bảng còn thiếu

### SQLite (fallback tự động)

Nếu SQL Server không kết nối được, app tự chuyển sang SQLite (`agri_ai.db` trong thư mục backend). Không cần cấu hình thêm.

### Seed dữ liệu cây trồng

```bash
python seed_db.py
```

### Các bảng chính

| Bảng | Mô tả |
|------|-------|
| `Users` | Tài khoản người dùng |
| `CropTypes` | Danh mục 40+ loại cây trồng |
| `MarketPrices` | Giá thị trường crawl hàng ngày |
| `PriceHistory` | Lịch sử giá tổng hợp (avg/min/max) |
| `PriceForecastResults` | Kết quả dự báo giá (Prophet) |
| `HarvestSchedule` | Lịch canh tác của nông dân |
| `HarvestForecastResults` | Dự báo ngày thu hoạch |
| `QualityRecords` | Lịch sử kiểm tra chất lượng (YOLOv8) |
| `MarketSuggestions` | Lịch sử gợi ý kênh tiêu thụ |
| `AlertSubscriptions` | Cài đặt cảnh báo giá |
| `AlertNotifications` | Lịch sử gửi thông báo |
| `WeatherData` | Dữ liệu thời tiết (Open-Meteo) |
| `AIConversations` | Lịch sử hội thoại chatbot |

---

## Tài khoản mặc định

Sau khi chạy SQL schema, các tài khoản sau đã được seed (mật khẩu đặt lại bằng `reset_passwords` khi cần):

| Email | Mật khẩu | Role |
|-------|----------|------|
| `nguyenvanan@gmail.com` | `Farmer@2024` | farmer |
| `tranthimy2205@gmail.com` | `Farmer@2024` | farmer |
| `levanbinhfarmer@gmail.com` | `Farmer@2024` | farmer |
| `phamthilan@gmail.com` | `Farmer@2024` | farmer |
| `admin@agriAI.vn` | `Admin@2024` | admin |

Để reset mật khẩu hàng loạt, chạy script tạm thời hoặc gọi `POST /api/auth/register` với email chưa có.

---

## API Reference

Interactive docs đầy đủ tại `/docs`. Tóm tắt theo nhóm:

### Hệ thống

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/` | Danh sách tất cả endpoints |
| GET | `/health` | Health check |
| GET | `/db-test` | Kiểm tra kết nối database |

### Xác thực (Auth)

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| POST | `/api/auth/register` | — | Đăng ký tài khoản mới |
| POST | `/api/auth/login` | — | Đăng nhập, nhận JWT token |
| GET | `/api/auth/me` | Bearer | Thông tin user hiện tại |

**Ví dụ đăng nhập:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@agriAI.vn", "password": "Admin@2024"}'
```

Sau đó dùng `access_token` trong header: `Authorization: Bearer <token>`

### Cây trồng (Crops)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/crops` | Danh sách tất cả cây trồng |
| GET | `/api/crops/search?keyword={kw}` | Tìm kiếm cây trồng |
| GET | `/api/crops/{crop_id}` | Chi tiết một cây trồng |

### Thời tiết (Weather)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/weather/current/{region}` | Thời tiết hiện tại |
| GET | `/api/weather/forecast/{region}` | Dự báo 7 ngày |
| GET | `/api/weather/agriculture/{region}` | Phân tích thời tiết theo nông nghiệp |

`{region}`: `Ha Noi`, `TP.HCM`, `Da Nang`, `Can Tho`, `Dak Lak`, `Lam Dong`, ...

### Giá thị trường (Pricing)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/pricing/current?crop_name={}&region={}` | Giá hiện tại từ DB |
| POST | `/api/pricing/suggest` | Gợi ý giá bán tối ưu (chất lượng + vùng + số lượng) |
| GET | `/api/pricing/history/{crop_name}/{region}` | Lịch sử giá 30 ngày |
| GET | `/api/pricing/weather-forecast?crop_name={}&region={}` | Giá điều chỉnh theo dự báo thời tiết |
| GET | `/api/pricing/compare-regions/{crop_name}` | So sánh giá đa vùng |
| POST | `/api/pricing/forecast` | Dự báo giá đơn giản (legacy) |

**Ví dụ gợi ý giá:**
```json
POST /api/pricing/suggest
{
  "crop_name": "Sầu riêng",
  "region": "Đắk Lắk",
  "quantity_kg": 1000,
  "quality_grade": "Grade A"
}
```

### Dự báo giá AI (Price Forecast)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/price-forecast/predict` | Dự báo giá 7–30 ngày bằng Prophet |

```json
POST /api/price-forecast/predict
{
  "crop_name": "Cà phê",
  "region": "Đắk Lắk",
  "days_ahead": 14
}
```

### Dự báo thu hoạch (Harvest)

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| POST | `/api/harvest/forecast` | Tuỳ chọn | Dự báo thu hoạch từ ngày trồng |
| POST | `/api/harvest/predict` | Tuỳ chọn | Dự báo ngày thu hoạch (JSON body) |
| GET | `/api/harvest/history/{user_id}` | — | Lịch sử dự báo của user |
| GET | `/api/harvest/history/me` | Bearer | Lịch sử dự báo của user hiện tại |
| POST | `/api/harvest/schedules` | Bearer | Tạo lịch canh tác mới |
| GET | `/api/harvest/schedules/{user_id}` | — | Lịch canh tác của user |
| GET | `/api/harvest/schedules/me` | Bearer | Lịch canh tác của user hiện tại |

```json
POST /api/harvest/forecast
{
  "crop_name": "Lúa",
  "planting_date": "2026-01-15",
  "region": "Cần Thơ"
}
```

### Kiểm tra chất lượng (Quality)

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| POST | `/api/quality/check` | Tuỳ chọn | Upload ảnh → YOLOv8 phân tích chất lượng |
| GET | `/api/quality/grades` | — | Danh sách các mức chất lượng |
| GET | `/api/quality/history/{user_id}` | — | Lịch sử kiểm tra của user |
| GET | `/api/quality/{record_id}` | — | Chi tiết một lần kiểm tra |

```bash
# Upload ảnh nông sản
curl -X POST http://localhost:8000/api/quality/check \
  -F "file=@anh_nong_san.jpg" \
  -F "crop_name=Sầu riêng" \
  -F "user_id=1"
```

Trả về: `quality_grade` (grade_1/grade_2/grade_3), `suggested_price`, `disease_detected`, `defects`.

### Gợi ý kênh tiêu thụ (Market)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/market/channels` | Danh sách kênh tiêu thụ có sẵn |
| POST | `/api/market/suggest` | Gợi ý kênh tối ưu cho lô hàng |
| GET | `/api/market/history/{user_id}` | Lịch sử gợi ý |
| GET | `/api/market/demand/{crop_name}` | Nhu cầu thị trường của cây trồng |

```json
POST /api/market/suggest
{
  "crop_name": "Xoài",
  "quantity_kg": 5000,
  "quality_grade": "Grade A",
  "region": "Đồng Tháp",
  "user_id": 1
}
```

Trả về so sánh lợi nhuận giữa: xuất khẩu, siêu thị, chợ sỉ, bán lẻ, chế biến.

### Cảnh báo giá (Alert)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/alert/create` | Tạo cảnh báo khi giá vượt ngưỡng |
| GET | `/api/alert/list` | Danh sách cảnh báo |
| GET | `/api/alert/{alert_id}` | Chi tiết cảnh báo |
| DELETE | `/api/alert/{alert_id}` | Tắt cảnh báo |
| POST | `/api/alert/check` | Kích hoạt kiểm tra ngưỡng thủ công |

```json
POST /api/alert/create
{
  "crop_name": "Lúa",
  "region": "Cần Thơ",
  "target_price": 9000,
  "condition": "above",
  "notification_channel": "email",
  "receiver": "farmer@example.com"
}
```

### Chatbot AI (Chat)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/chat` | Hỏi chuyên gia nông nghiệp AI (Gemini 2.5-flash + Google Search + RAG từ DB) |
| POST | `/api/chat/price-qa` | Hỏi giá cụ thể (Tavily Search + DB context) |

```json
POST /api/chat
{
  "message": "Sầu riêng Đắk Lắk đang bị bệnh vàng lá, phải xử lý thế nào?"
}

POST /api/chat/price-qa
{
  "question": "Giá cà phê Đắk Lắk hôm nay bao nhiêu?"
}
```

Chat sử dụng RAG: tự động bổ sung dữ liệu giá & chu kỳ sinh trưởng từ DB vào context trước khi gửi Gemini.

### Crawler & Dữ liệu giá (Crawler)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/crawler/latest-crawled-data` | Dữ liệu giá mới nhất đã cào |
| GET | `/api/crawler/summary` | Thống kê tổng quan dữ liệu crawler |
| GET | `/api/crawler/standard-price?crop_name={}` | Giá chuẩn theo tên cây (7 ngày gần nhất) |

Crawler chạy tự động trong background khi server khởi động, cập nhật định kỳ theo `CRAWL_INTERVAL_SECONDS`.

**Nguồn giá:**
- BachHoaXanh, WinMart (độ tin cậy cao nhất)
- giacaphe.com, giatieu.com (chuyên ngành)
- nongnghiep.vn, gia.vn (tin tức)
- Tavily Search (realtime)
- Simulation (fallback khi không cào được)

### Tin tức & Tác động giá (News)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/news/market-impact?crop_name={}&region={}` | Phân tích tác động tin tức tổng hợp |
| GET | `/api/news/china-trade` | Theo dõi thương mại Trung Quốc |
| GET | `/api/news/disasters?region={}` | Tin tức thiên tai ảnh hưởng nông nghiệp |
| GET | `/api/news/combined-factor?crop_name={}&region={}` | Hệ số giá tổng hợp (tin tức 60% + thời tiết 40%) |
| GET | `/api/news/price-with-news?crop_name={}&region={}` | Giá điều chỉnh theo tin tức thị trường |

> `crop_name` và `region` là **bắt buộc** với `/combined-factor` và `/price-with-news`.

---

## Chạy tests

```bash
# Chạy toàn bộ test suite
python -m pytest

# Chạy kèm verbose output
python -m pytest -v

# Chạy một file cụ thể
python -m pytest tests/test_api.py -v
```

---

## Ghi chú triển khai

- **Encoding Windows:** File `.env` đã có `PYTHONUTF8=1` và `PYTHONIOENCODING=utf-8` — bắt buộc để tránh lỗi encode tiếng Việt trên Windows.
- **SQL Server Status constraint:** Cột `HarvestSchedule.Status` chỉ chấp nhận `'Dang trong'`, `'Sap thu hoach'`, `'Da thu hoach'`, `'That mua'` (không dấu).
- **Gemini fallback:** Nếu Gemini trả về `None` (nội dung bị block), chat trả về chuỗi rỗng thay vì lỗi 500.
- **Alert memory fallback:** Nếu DB không cho phép INSERT vào `AlertSubscriptions`, alert được lưu trong bộ nhớ process — sẽ mất khi restart server.
- **YOLOv8 model:** Nếu file `ai_models/weights/best.pt` không tồn tại, quality check tự dùng mock result với `confidence=0.8`.

## Trợ lý RAG

Hướng dẫn nạp tài liệu, cấu hình Ollama/Chroma và sử dụng lịch sử nhiều lượt: [assistant-rag.md](docs/assistant-rag.md).
