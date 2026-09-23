# SKILL.md — Hệ thống AI Hỗ trợ Nông dân (AgriAI)
## Dự báo Thu hoạch & Định giá Nông sản

**Phiên bản:** 1.2 | **Ngày:** 05/2026  
**Nguồn:** NongNghiep.docx · Nhiệm_vụ_chi_tiết_Người_2.docx · docs/database/NongNghiepAI_Full.sql
**Stack:** Python / FastAPI · React 18 / Zustand / Tailwind · MS SQL Server · YOLOv8 · Prophet

---

## 1. PERSONA & VAI TRÒ TRỢ LÝ AI

Trợ lý AI trong hệ thống AgriAI đóng **ba vai trò song song**:

| Vai trò | Mô tả | Ràng buộc |
|---|---|---|
| **System Actor (Xử lý ngầm)** | Chạy inference YOLOv8, Prophet, Scikit-learn khi được `<<include>>` từ usecase của Nông dân | Không hiển thị chi tiết kỹ thuật cho Nông dân |
| **Trợ lý hội thoại** | Trả lời câu hỏi kỹ thuật nông nghiệp qua AIConversations (Gemini API + 3-layer RAG) | Phân loại topic theo enum cố định |
| **Engine nghiệp vụ** | Tính toán giá đề xuất, gợi ý kênh bán hàng, kiểm tra cảnh báo | Dùng dữ liệu thực từ DB, không mock |

**Người dùng chính (Actor):**
- **Nông dân** — nhập liệu, nhận kết quả dự báo/phân loại/giá
- **Quản trị viên** — quản lý tài khoản, giám sát các module AI
- **Hệ thống AI** — xử lý ngầm được gọi qua `<<include>>`

---

## 2. PHẠM VI DỮ LIỆU (PHẢI TUÂN THỦ)

### 2.1 Danh sách 51 loại nông sản được hỗ trợ

#### Lúa gạo (4 loại)
| CropName | CropNameEN | Chu kỳ (ngày) | Giá điển hình (VNĐ/kg) |
|---|---|---|---|
| Lúa | Rice | 105 | 6.000 – 12.000 |
| Ngô | Corn | 90 | 4.000 – 9.000 |
| Đậu tương | Soybean | 95 | 12.000 – 22.000 |
| Đậu phộng | Peanut | 120 | 20.000 – 40.000 |

#### Rau củ (27 loại)
| CropName | CropNameEN | Chu kỳ (ngày) | Giá điển hình (VNĐ/kg) |
|---|---|---|---|
| Cà chua | Tomato | 75 | 5.000 – 40.000 |
| Rau muống | Water Spinach | 30 | 4.000 – 18.000 |
| Khoai lang | Sweet Potato | 100 | 6.000 – 30.000 |
| Rau cải | Mustard Green | 35 | 4.000 – 30.000 |
| Cải bắp | Cabbage | 70 | 3.000 – 20.000 |
| Cải thảo | Chinese Cabbage | 65 | 4.000 – 25.000 |
| Xà lách | Lettuce | 40 | 6.000 – 50.000 |
| Hành lá | Spring Onion | 35 | 8.000 – 60.000 |
| Hành tây | Onion | 60 | 5.000 – 40.000 |
| Tỏi | Garlic | 90 | 20.000 – 120.000 |
| Gừng | Ginger | 240 | 12.000 – 80.000 |
| Nghệ | Turmeric | 270 | 10.000 – 60.000 |
| Cà rốt | Carrot | 100 | 5.000 – 35.000 |
| Khoai tây | Potato | 90 | 8.000 – 35.000 |
| Su hào | Kohlrabi | 65 | 3.000 – 20.000 |
| Củ cải | Radish | 70 | 4.000 – 25.000 |
| Bí đỏ | Pumpkin | 80 | 4.000 – 30.000 |
| Bí xanh | Winter Melon | 80 | 3.000 – 20.000 |
| Bầu | Bottle Gourd | 75 | 3.000 – 22.000 |
| Mướp | Luffa | 70 | 4.000 – 28.000 |
| Khổ qua | Bitter Melon | 70 | 6.000 – 50.000 |
| Đậu cove | French Bean | 65 | 8.000 – 50.000 |
| Đậu đũa | Yard-long Bean | 65 | 6.000 – 40.000 |
| Ớt | Chili | 90 | 10.000 – 120.000 |
| Mồng tơi | Malabar Spinach | 35 | 4.000 – 22.000 |
| Rau cần | Celery | 70 | 8.000 – 50.000 |
| Ngó sen | Lotus Root | 120 | 20.000 – 80.000 |

#### Trái cây (13 loại)
| CropName | CropNameEN | Chu kỳ (ngày) | Ghi chú |
|---|---|---|---|
| Sầu riêng | Durian | **1460** | ~4 năm từ cây giống ghép |
| Xoài | Mango | **1095** | ~3 năm |
| Thanh long | Dragon Fruit | **540** | ~18 tháng |
| Chuối | Banana | 365 | |
| Dứa | Pineapple | 365 | |
| Dưa hấu | Watermelon | 80 | |
| Bơ | Avocado | **1460** | ~4 năm |
| Mít | Jackfruit | **1460** | ~4 năm |
| Nhãn | Longan | 730 | ~2 năm |
| Vải | Lychee | 730 | ~2 năm |
| Cam | Orange | 730 | ~2 năm |
| Bưởi | Pomelo | **1095** | ~3 năm |
| Ổi | Guava | 365 | |

#### Cây công nghiệp (7 loại)
| CropName | CropNameEN | Chu kỳ (ngày) | Giá điển hình (VNĐ/kg) |
|---|---|---|---|
| Cà phê | Coffee | **1095** | 60.000 – 200.000 |
| Hồ tiêu | Black Pepper | **1095** | 40.000 – 180.000 |
| Điều | Cashew | **1460** | 25.000 – 100.000 |
| Mía | Sugarcane | 365 | 700 – 2.500 |
| Chè | Tea | **1095** | 5.000 – 30.000 |
| Cao su | Rubber | **2555** | 25.000 – 60.000 |
| Sắn | Cassava | 270 | 2.000 – 8.000 |

> ⚠️ **Chu kỳ lâu năm**: Sầu riêng, Bơ, Mít, Điều = 4 năm; Cà phê, Hồ tiêu, Bưởi, Xoài = 3 năm. KHÔNG dùng giá trị mặc định 70–120 ngày cho những cây này.

### 2.2 Vùng địa lý được hỗ trợ (10 tỉnh chính, mở rộng)

Hệ thống hỗ trợ crawl giá và thời tiết cho **10 tỉnh chính**:

| Tỉnh/Thành | Tọa độ (lat, lon) | Đặc sản chính |
|---|---|---|
| TP.HCM | 10.82, 106.63 | Trung tâm phân phối |
| Hà Nội | 21.03, 105.85 | Lúa, rau vụ đông |
| Đà Nẵng | 16.05, 108.20 | Rau củ miền Trung |
| Cần Thơ | 10.05, 105.75 | Lúa, trái cây ĐBSCL |
| Đắk Lắk | 12.67, 108.05 | Cà phê, sầu riêng |
| Lâm Đồng | 11.95, 108.44 | Rau Đà Lạt, cà phê |
| Gia Lai | 13.98, 108.00 | Hồ tiêu, cà phê |
| Tiền Giang | 10.36, 106.36 | Sầu riêng, thanh long |
| Long An | 10.54, 106.41 | Lúa, thanh long |
| Bình Thuận | 10.93, 108.10 | Thanh long |

Ngoài ra còn hỗ trợ các tỉnh mở rộng trong dữ liệu giá: Đồng Tháp, An Giang, Bình Phước, Đồng Nai, Khánh Hòa, Bắc Giang, Hải Dương, v.v.

### 2.3 Enum toàn hệ thống (BẮT BUỘC dùng đúng giá trị ASCII)

```
QualityGrade   : 'Loai 1' | 'Loai 2' | 'Loai 3'
MarketType     : 'Ban buon' | 'Ban le' | 'Xuat khau'
Category       : 'Lua gao' | 'Trai cay' | 'Rau cu' | 'Cong nghiep' | 'Khac'
Status         : 'Dang trong' | 'Sap thu hoach' | 'Da thu hoach' | 'That mua'
PriceTrend     : 'Tang' | 'Giam' | 'On dinh'
AlertType      : 'Tren' | 'Duoi' | 'Thay doi'
NotifyMethod   : 'Email' | 'SMS' | 'Zalo' | 'App'
SendStatus     : 'Pending' | 'Sent' | 'Failed'
Topic (AI)     : 'Gia ca' | 'Thu hoach' | 'Chat luong' | 'Thoi tiet' | 'Dich benh' | 'Khac'
Channel        : 'Thuong lai' | 'Cho dau moi' | 'Xuat khau'
Role           : 'farmer' | 'admin' | 'expert'
```

> ⚠️ **Lý do:** SQL Server dùng ASCII CHECK constraint để tránh lỗi VARCHAR vs NVARCHAR khi Python/pyodbc INSERT dữ liệu. Không được thay thế bằng tiếng Việt có dấu trong enum.

---

## 3. KIẾN TRÚC CRAWLER (asyncio, không dùng Celery)

### 3.1 Background task

Crawler chạy như **asyncio background task** trong FastAPI lifespan — **không dùng Celery**.  
File: `app/tasks/crawler_tasks.py`

```
Khởi động server
    → auto_crawl_loop() (asyncio.create_task)
        → seed_7_days_on_startup()
            → Bước 0: seed_crops() — bổ sung 51 cây vào CropTypes
            → Bước 1: _scrape_web() — cào giá hôm nay từ 10 nguồn
            → Bước 2: _generate_historical_prices() — sinh 6 ngày trước (random-walk ±1.5%)
            → Bước 3: _save_market_prices_force() — ghi đè MarketPrices
            → Bước 4: _aggregate_history_range(7) — tổng hợp PriceHistory
            → Bước 5: _fetch_all_weather(7) — cào thời tiết 10 tỉnh × 7 ngày
        → sleep(CRAWL_INTERVAL) → run_price_crawler() [lặp lại mỗi 3600s]
```

### 3.2 Nguồn dữ liệu giá (theo độ ưu tiên)

| Nguồn | Priority | Loại |
|---|---|---|
| bachhoaxanh.com | **1** | Siêu thị bán lẻ — giá chính xác nhất |
| winmart.vn | **1** | Siêu thị bán lẻ |
| giacaphe.com | **2** | Chuyên cà phê |
| giatieu.com | **2** | Chuyên hồ tiêu |
| nongnghiep.vn | **3** | Báo nông nghiệp |
| gia.vn | **3** | Cổng giá tổng hợp |
| vigen.net.vn | **4** | Tổng hợp |
| cadulo.com | **4** | Tổng hợp |
| simulation | **99** | Fallback — chỉ dùng khi web không phản hồi |

> Quy tắc upsert: priority thấp hơn = uy tín cao hơn. Chỉ ghi đè nếu nguồn mới có `priority ≤ priority` nguồn cũ.

### 3.3 Pre-filter pipeline (trước khi INSERT vào DB)

```
raw_items
    → validate (thiếu crop_name / region / price → bỏ)
    → range_check (giá nằm ngoài _PRICE_RANGE → bỏ)
    → deduplicate by source priority (cùng crop+region: giữ nguồn uy tín nhất)
    → filtered_items → _save_market_prices() hoặc _save_market_prices_force()
```

### 3.4 Nguồn dữ liệu thời tiết

**Open-Meteo API** (miễn phí, không cần API key):
```
GET https://api.open-meteo.com/v1/forecast
    ?latitude={lat}&longitude={lon}
    &daily=temperature_2m_max,temperature_2m_min,precipitation_sum,
           relative_humidity_2m_max,sunshine_duration,weather_code
    &timezone=Asia/Ho_Chi_Minh
    &past_days=6&forecast_days=1
```
Lưu vào `WeatherData`: TempMin, TempMax, Humidity, Rainfall, SunshineHours, WeatherDesc.

---

## 4. MODULE 1 — DỰ BÁO THỜI TIẾT & CẢNH BÁO THỜI TIẾT

### 4.1 Nguồn dữ liệu thời tiết
Bảng `WeatherData` lưu trữ theo `(Region, RecordDate)` — unique constraint.  
Được **cào tự động từ Open-Meteo API** mỗi lần server khởi động (7 ngày × 10 tỉnh) và cập nhật định kỳ mỗi 3600s.

**Trường dữ liệu:**
```
TempMin / TempMax  : Nhiệt độ (°C)
Humidity           : Độ ẩm (%)
Rainfall           : Lượng mưa (mm)
SunshineHours      : Số giờ nắng
WeatherDesc        : Mô tả (NVARCHAR — cho phép tiếng Việt)
```

### 4.2 Quy trình xử lý cảnh báo thời tiết

```
Bước 1: Hệ thống đọc WeatherData theo Region & ngày hiện tại
Bước 2: So khớp với ngưỡng cảnh báo của từng loại cây (CropTypes)
Bước 3: Nếu điều kiện bất lợi → ghi vào HarvestForecastResults.WeatherWarning
Bước 4: Kích hoạt thông báo qua NotifyMethod đã đăng ký
```

### 4.3 Ràng buộc
- Dữ liệu thời tiết phải tồn tại trong `WeatherData` trước khi chạy Harvest Predictor
- Cảnh báo thời tiết được nhúng vào `HarvestForecastResults.WeatherWarning` (NVARCHAR MAX)
- Không gửi thông báo nếu `AlertSubscriptions.IsActive = 0`

---

## 5. MODULE 2 — ĐỊNH GIÁ SẢN PHẨM THEO THỜI TIẾT

### 5.1 Nguyên tắc
Thời tiết ảnh hưởng đến **chất lượng** → chất lượng ảnh hưởng đến **giá**. Pipeline:

```
WeatherData (Region, Date)
        ↓
[quality_service.py] → đánh giá tác động thời tiết đến chất lượng
        ↓
QualityGrade: 'Loai 1' | 'Loai 2' | 'Loai 3'
        ↓
[pricing_service.py] → tra cứu MarketPrices theo CropID + Region + QualityGrade
        ↓
SuggestedPriceMin / SuggestedPriceMax
```

### 5.2 Ràng buộc
- `pricing_service.py` **phải dùng dữ liệu thực từ DB**, không dùng giá hardcode hay mock
- Nếu không có `MarketPrices` cho ngày hiện tại → dùng record gần nhất theo index `IDX_MarketPrices_Crop_Region`
- Giá chuẩn được tính theo endpoint `/api/crawler/standard-price`: trung bình có trọng số (market 60% + history 40%)

---

## 6. MODULE 3 — ĐỊNH GIÁ NÔNG SẢN QUA HÌNH ẢNH (Computer Vision)

### 6.1 Công nghệ
Model: **YOLOv8** — Object Detection, phân loại chất lượng và phát hiện sâu bệnh.

### 6.2 Quy trình từng bước

```
Bước 1: Nông dân tải ảnh lên hệ thống
         → Hành động này <<include>> "Nhận diện chất lượng (YOLOv8)"

Bước 2: quality_service.py xử lý:
   2a. Lưu ảnh vào storage → ghi đường dẫn vào QualityRecords.ImagePath
   2b. Gọi YOLOv8 detector → nhận AIGrade + ConfidenceScore
   2c. Trích xuất DetectedIssues (danh sách sâu bệnh nếu có)
   2d. Gọi logic định giá (pricing_service.py)

Bước 3: pricing_service.py trả về:
   → SuggestedPriceMin
   → SuggestedPriceMax
   → Recommendation (khuyến nghị xử lý)

Bước 4: Ghi toàn bộ vào bảng QualityRecords
Bước 5: API trả về cho Nông dân: AIGrade + giá đề xuất + khuyến nghị
```

### 6.3 Schema đầu ra (bảng QualityRecords)

| Trường | Kiểu | Mô tả |
|---|---|---|
| `ImagePath` | NVARCHAR(500) | Đường dẫn ảnh đã lưu |
| `AIGrade` | NVARCHAR(20) | `'Loai 1'` / `'Loai 2'` / `'Loai 3'` |
| `ConfidenceScore` | FLOAT | Độ tin cậy của model (0–1) |
| `DetectedIssues` | NVARCHAR(MAX) | Danh sách sâu bệnh phát hiện được |
| `SuggestedPriceMin` | DECIMAL(18,2) | Giá tối thiểu đề xuất (VNĐ/kg) |
| `SuggestedPriceMax` | DECIMAL(18,2) | Giá tối đa đề xuất (VNĐ/kg) |
| `Recommendation` | NVARCHAR(MAX) | Khuyến nghị xử lý |

### 6.4 Ràng buộc
- `AIGrade` phải là một trong 3 giá trị ASCII: `'Loai 1'`, `'Loai 2'`, `'Loai 3'`
- `ConfidenceScore` cần được lưu để theo dõi độ chính xác theo thời gian
- `DetectedIssues` lưu dạng JSON string hoặc text mô tả — không có schema cứng

---

## 7. MODULE 4 — DỰ BÁO GIÁ TRONG 7 NGÀY

### 7.1 Công nghệ
Model: **Prophet** (Facebook) hoặc **ARIMA** / **Moving Average** (từ Scikit-learn).  
Tác vụ: **Time Series Forecasting** trên bảng `PriceHistory`.

### 7.2 Quy trình từng bước

```
Bước 1: Nông dân chọn loại nông sản + vùng → gọi "Xem giá hiện tại"
         → <<include>> "Dự báo giá (Scikit-learn)"

Bước 2: price_forecast predictor đọc PriceHistory:
   - Lọc theo CropID + Region
   - Sắp xếp theo RecordDate ASC
   - Tối thiểu cần 7 ngày lịch sử (seed 7 ngày từ startup)

Bước 3: Chạy model dự báo → sinh N bản ghi (7 ngày hoặc tối đa 30 ngày)
   Mỗi bản ghi gồm:
   - ForecastDate
   - PredictedPrice
   - ConfidenceLow / ConfidenceHigh (khoảng tin cậy)
   - PriceTrend: 'Tang' | 'Giam' | 'On dinh'

Bước 4: Lưu vào bảng PriceForecastResults (ghi ModelVersion)
Bước 5: API trả về danh sách 7 ngày dự báo cho Nông dân
         → vẽ biểu đồ phân tích xu hướng giá (Frontend React)
```

### 7.3 Schema đầu ra (bảng PriceForecastResults)

| Trường | Kiểu | Mô tả |
|---|---|---|
| `CropID` | INT | FK → CropTypes |
| `Region` | NVARCHAR(100) | Vùng địa lý |
| `ForecastDate` | DATE | Ngày dự báo |
| `PredictedPrice` | DECIMAL(18,2) | Giá dự báo (VNĐ/kg) |
| `ConfidenceLow` | DECIMAL(18,2) | Biên dưới khoảng tin cậy |
| `ConfidenceHigh` | DECIMAL(18,2) | Biên trên khoảng tin cậy |
| `PriceTrend` | NVARCHAR(20) | `'Tang'` / `'Giam'` / `'On dinh'` |
| `ModelVersion` | NVARCHAR(50) | Phiên bản model đã dùng |

### 7.4 Ràng buộc
- Khoảng dự báo mặc định: **7 ngày**, tối đa: **30 ngày**
- `PriceTrend` phải là enum ASCII — không dùng `'Tăng'`, `'Giảm'` có dấu
- Index `IDX_PriceForecast_Crop_Region` đảm bảo query nhanh

---

## 8. MODULE 5 — GỢI Ý THU HOẠCH (Harvest Predictor)

### 8.1 Công nghệ
Model: **Prophet model** trong `harvest_service.py` — gọi `harvest_forecast predictor`.

### 8.2 Đầu vào cần thiết (Nông dân nhập)

| Trường | Bảng | Bắt buộc |
|---|---|---|
| `CropID` | HarvestSchedule | ✓ |
| `PlantingDate` | HarvestSchedule | ✓ |
| `AreaSize` (ha) | HarvestSchedule | ✓ |
| `Region` | HarvestSchedule | ✓ |
| `FertilizerUsed` | HarvestSchedule | ✓ |
| `PesticideUsed` | HarvestSchedule | ✓ |

### 8.3 Quy trình từng bước

```
Bước 1: Nông dân nhập thông tin mùa vụ → ghi vào HarvestSchedule
         Status ban đầu: 'Dang trong'

Bước 2: <<include>> Harvest Predictor
   2a. Đọc GrowthDurationDays từ CropTypes (theo CropID)
       ⚠️ Lưu ý chu kỳ thực tế: sầu riêng=1460 ngày, cà phê=1095 ngày (KHÔNG phải 70-120 ngày)
   2b. Đọc WeatherData theo Region trong khoảng PlantingDate → nay
   2c. Tính ExpectedHarvestDate = PlantingDate + GrowthDurationDays (±điều chỉnh thời tiết)
   2d. Tính EstimatedYieldKg = AreaSize × năng suất trung bình × hệ số thời tiết

Bước 3: Ghi kết quả vào HarvestForecastResults:
   - ExpectedHarvestDate
   - ConfidenceScore
   - WeatherWarning (nếu có rủi ro)
   - LaborRecommendation
   - TransportRecommendation
   - ModelVersion

Bước 4: Cập nhật HarvestSchedule.ExpectedHarvestDate
Bước 5: Cập nhật Status theo tiến độ:
   'Dang trong' → 'Sap thu hoach' (khi còn ≤ 7 ngày) → 'Da thu hoach' / 'That mua'
```

### 8.4 Gợi ý thu hoạch trả về cho Nông dân

```json
{
  "expected_harvest_date": "2026-04-25",
  "confidence_score": 0.87,
  "estimated_yield_kg": 12500,
  "weather_warning": "Dự báo mưa lớn 18-20/04 — khuyến nghị thu hoạch sớm",
  "labor_recommendation": "Cần 5 nhân công trong 3 ngày",
  "transport_recommendation": "Liên hệ xe tải trước 3 ngày"
}
```

### 8.5 Ràng buộc
- `harvest_service.py` phải **import được predictor** từ module `ai_models/harvest_forecast`
- Phải tách riêng 3 module: `harvest_forecast`, `price_forecast`, `quality_check` — độc lập nhau
- WeatherData phải tồn tại cho Region + ngày cần tính trước khi gọi predictor

---

## 9. MODULE 6 — HỆ THỐNG CẢNH BÁO GIÁ

### 9.1 Quy trình từng bước

```
Bước 1: Nông dân đăng ký cảnh báo → ghi vào AlertSubscriptions:
   - CropID, Region, TargetPrice
   - AlertType: 'Tren' (giá vượt ngưỡng) | 'Duoi' (giá dưới ngưỡng) | 'Thay doi'
   - NotifyMethod: 'Email' | 'SMS' | 'Zalo' | 'App'
   - IsActive: 1

Bước 2: asyncio background task (chạy sau mỗi CRAWL_INTERVAL giây):
   2a. Crawler cập nhật MarketPrices từ 8 nguồn web + simulation fallback
   2b. _check_and_trigger_alerts() đọc tất cả AlertSubscriptions có IsActive = 1
   2c. So sánh giá thị trường hiện tại với TargetPrice theo AlertType

Bước 3: Nếu điều kiện thỏa mãn:
   3a. Ghi vào AlertNotifications (CurrentPrice, Message, NotifyMethod)
   3b. SendStatus = 'Pending'
   3c. Gửi thông báo → cập nhật SendStatus = 'Sent' hoặc 'Failed'
   3d. Ghi AlertSubscriptions.LastTriggered = GETDATE()

Bước 4: Nông dân <<extend>> "Xem lịch sử cảnh báo" nếu muốn
```

### 9.2 Ràng buộc
- Không gửi thông báo nếu `IsActive = 0`
- `alert_service.py` chỉ **phát hiện điều kiện** — việc gửi thực tế do notification service xử lý
- Task chạy định kỳ mỗi `CRAWL_INTERVAL` giây (mặc định 3600s, cấu hình qua env var)

---

## 10. MODULE 7 — PHÂN TÍCH THỊ TRƯỜNG & GỢI Ý KÊNH BÁN HÀNG

### 10.1 Quy trình từng bước

```
Bước 1: Nông dân chọn "Phân tích xu hướng"
         → <<include>> "Xem lịch sử giá" (PriceHistory)
         → <<include>> "Gợi ý kênh bán hàng"

Bước 2: Đọc PriceHistory 7-30 ngày gần nhất theo CropID + Region
Bước 3: Chạy dự báo (tương tự Module 4) → xác định PriceTrend

Bước 4: Dựa trên PriceTrend + QualityGrade → quyết định RecommendedChannel:
   'Loai 1' + 'Tang' → 'Xuat khau' hoặc 'Cho dau moi'
   'Loai 2' + 'On dinh' → 'Thuong lai'
   'Loai 3' / 'Giam' → 'Thuong lai' (nhanh nhất)

Bước 5: Ghi vào MarketSuggestions:
   - RecommendedChannel: 'Thuong lai' | 'Cho dau moi' | 'Xuat khau'
   - EstimatedProfit
   - Reason (giải thích)
   - Warning (rủi ro nếu có)
```

### 10.2 Endpoint thực tế
- `GET /api/crawler/standard-price?crop_name=Sầu riêng&region=Đắk Lắk` — giá chuẩn tổng hợp
- `GET /api/crawler/summary?days=7` — thống kê avg/min/max theo crop+region
- `GET /api/crawler/latest-crawled-data?days=7&crop_name=...&region=...` — dữ liệu thô

---

## 11. MODULE 8 — CRAWLER THU THẬP GIÁ THỊ TRƯỜNG

### 11.1 Nguồn dữ liệu mục tiêu (ưu tiên cao → thấp)
1. `bachhoaxanh.com` (rau-cu-qua, trai-cay) — priority 1
2. `winmart.vn` (rau-cu-qua, trai-cay) — priority 1
3. `giacaphe.com` — priority 2 (chuyên cà phê)
4. `giatieu.com` — priority 2 (chuyên hồ tiêu)
5. `nongnghiep.vn` — priority 3
6. `gia.vn` — priority 3
7. `vigen.net.vn` — priority 4
8. `cadulo.com` — priority 4
9. `simulation` — priority 99 (fallback)

### 11.2 Định dạng đầu ra chuẩn (BẮT BUỘC cố định)

```python
{
    "crop_name": str,      # Tên nông sản → map sang CropID qua _CROP_ALIAS
    "region":    str,      # Vùng địa lý → chuẩn hóa qua _REGION_ALIAS
    "price_per_kg": float, # Đã quy đổi về VNĐ/kg
    "source":    str,      # "bachhoaxanh.com" / "simulation" / ...
    "date":      str,      # ISO date "YYYY-MM-DD"
    "url":       str,      # URL nguồn
}
```

### 11.3 Xử lý đơn vị giá (BachHoaXanh/WinMart)
- Giá `/100g` → nhân ×10 để ra VNĐ/kg
- Giá `/200g` → nhân ×5
- Giá `/500g` → nhân ×2
- Giá `/tấn` → chia 1000
- Giá `/tạ` → chia 100

### 11.4 Ràng buộc
- Format đầu ra **phải nhất quán** giữa tất cả parsers
- Dữ liệu crawler INSERT vào `MarketPrices` — phải dùng ASCII enum
- Task chạy **asyncio background** (không dùng Celery) — cài đặt qua env var `CRAWL_INTERVAL_SECONDS`
- Nếu crawler thất bại → ghi log, không crash toàn hệ thống, fallback sang simulation

---

## 12. MODULE 9 — TRỢ LÝ ẢO AI (AIConversations)

### 12.1 Công nghệ
**Gemini API** (`gemini-2.5-flash`) với Google Search grounding, được cấu hình trong `app/integrations/gemini_client.py`.  
Prompt system: "chuyên gia nông nghiệp 20 năm kinh nghiệm".

### 12.2 3-layer RAG (Retrieval-Augmented Generation)

```
Câu hỏi người dùng
    ↓
[Phát hiện keyword]
    ↓ _PRICE_KEYWORDS → RAG 1: Top 20 MarketPrices gần nhất từ DB
    ↓ _CROP_KEYWORDS / _PEST_KEYWORDS → RAG 2: CropTypes (chu kỳ sinh trưởng, giá)
    ↓ _PRICE_KEYWORDS → RAG 3: PriceHistory 7 ngày (avg/min/max)
    ↓
[Context tổng hợp] + [Câu hỏi] → Gemini API → Phản hồi
```

### 12.3 Phân loại hội thoại

Mỗi tin nhắn phải được gán `Topic` theo enum:

| Topic (ASCII) | Ví dụ câu hỏi |
|---|---|
| `'Gia ca'` | "Giá lúa hôm nay bao nhiêu?" |
| `'Thu hoach'` | "Khi nào nên thu hoạch sầu riêng?" |
| `'Chat luong'` | "Ảnh này cà chua bị gì vậy?" |
| `'Thoi tiet'` | "Thời tiết Cần Thơ tuần này thế nào?" |
| `'Dich benh'` | "Cà phê bị rỉ sắt thì xử lý ra sao?" |
| `'Khac'` | Các câu hỏi khác |

### 12.4 Schema lưu trữ (AIConversations)

| Trường | Ghi chú |
|---|---|
| `UserID` | FK → Users (nullable nếu chưa đăng nhập) |
| `SessionID` | NVARCHAR(100) — nhóm các lượt chat trong 1 phiên |
| `UserMessage` | NVARCHAR MAX |
| `AIResponse` | NVARCHAR MAX |
| `Topic` | Enum ASCII bắt buộc |
| `RelatedCropID` | FK → CropTypes (nullable) |

---

## 13. QUY TẮC KỸ THUẬT VÀ RÀNG BUỘC CHUNG

### 13.1 Phân tách module (BẮT BUỘC)
```
ai_models/
  ├── harvest_forecast/   → HarvestPredictor
  ├── price_forecast/     → PriceForecastPredictor
  └── quality_check/      → YOLOv8Detector
```
Ba module phải độc lập — **import được từ service layer**.

### 13.2 API Contract
- Tuân thủ tuyệt đối **Pydantic schemas** do Người 1 (Backend Lead) thiết kế
- Không sửa `app/api/`, `app/models/`, `app/schemas/` nếu chưa thống nhất
- Git branch: `feature/person2-ai-crawler-services`
- Thay thế toàn bộ **hàm mock** trong Service Layer bằng logic thực

### 13.3 Database
- CSDL: `NongNghiepAI` trên MS SQL Server
- ORM: SQLAlchemy (kết nối qua pyodbc)
- **Không dùng tiếng Việt có dấu trong giá trị enum** — dùng ASCII mapping đã định nghĩa
- Tất cả query quan trọng đã có index — ưu tiên dùng index có sẵn

### 13.4 Index quan trọng cần biết

| Index | Bảng | Dùng khi |
|---|---|---|
| `IDX_MarketPrices_Crop_Region` | MarketPrices | Query giá theo cây + vùng + ngày |
| `IDX_PriceHistory_Crop_Region` | PriceHistory | Lấy lịch sử giá cho dự báo |
| `IDX_PriceForecast_Crop_Region` | PriceForecastResults | Đọc kết quả dự báo đã lưu |
| `IDX_HarvestSchedule_User` | HarvestSchedule | Lọc lịch mùa vụ theo user + status |
| `IDX_QualityRecords_User` | QualityRecords | Lịch sử kiểm tra chất lượng |
| `IDX_AlertSubscriptions_Active` | AlertSubscriptions | Task kiểm tra cảnh báo |

### 13.5 Background Tasks (asyncio — không dùng Celery)
```
auto_crawl_loop()          → Chạy seed 7 ngày khi startup, sau đó cập nhật định kỳ
seed_7_days_on_startup()   → Seed crops + giá 7 ngày + thời tiết 7 ngày
run_price_crawler()        → Cào giá mới nhất + cập nhật thời tiết hôm nay
_check_and_trigger_alerts()→ Kiểm tra AlertSubscriptions, gửi thông báo
```

### 13.6 Biến môi trường quan trọng
```
CRAWL_INTERVAL_SECONDS  : Chu kỳ cập nhật giá (mặc định: 3600)
GEMINI_API_KEY          : API key cho Gemini (gemini-2.5-flash)
DATABASE_URL            : Chuỗi kết nối SQL Server
ADMIN_NOTIFICATION_EMAIL: Email nhận cảnh báo hệ thống
```

---

## 14. CHECKLIST TRƯỚC KHI PHÁT SINH KẾT QUẢ

Trước mỗi lần AI tạo output nghiệp vụ, kiểm tra:

- [ ] Enum value có đúng ASCII không? (Không dùng `'Loại 1'` — phải dùng `'Loai 1'`)
- [ ] CropName có nằm trong danh sách 51 loại được hỗ trợ không?
- [ ] Chu kỳ sinh trưởng có đúng không? (sầu riêng=1460 ngày, không phải 120 ngày)
- [ ] Region có thuộc các vùng được hỗ trợ không?
- [ ] Dữ liệu đầu vào có đủ (WeatherData, PriceHistory) trước khi gọi predictor không?
- [ ] pricing_service có đang dùng data thực từ DB không (không mock)?
- [ ] Kết quả có được lưu vào đúng bảng (QualityRecords / PriceForecastResults / HarvestForecastResults) không?
- [ ] Topic trong AIConversations có được gán đúng enum không?
- [ ] Nguồn crawler có đúng priority không? (bachhoaxanh=1, simulation=99)

---

*Tài liệu này được tổng hợp từ: Đề án chuyên đề (NongNghiep.docx), Nhiệm vụ chi tiết Người 2 (Nhiệm_vụ_chi_tiết_Người_2.docx), Schema cơ sở dữ liệu (docs/database/NongNghiepAI_Full.sql), và codebase thực tế (crawler_tasks.py, seed_db.py, chat.py). Nhóm 22 — Đại học Sư phạm Kỹ thuật Đà Nẵng — 05/2026.*
