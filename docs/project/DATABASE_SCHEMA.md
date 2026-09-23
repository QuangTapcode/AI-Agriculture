# 🗄️ Database Schema - NongNghiepAI

**Database:** SQL Server  
**Tên Database:** NongNghiepAI  
**Số lượng bảng:** 10 tables  
**File SQL:** [`../database/NongNghiepAI_Full.sql`](../database/NongNghiepAI_Full.sql)

---

## 📊 Danh sách 10 Bảng

### 1. **Users** - Người dùng
Quản lý thông tin người dùng (nông dân, admin, chuyên gia)

**Columns:**
- `UserID` (PK) - ID người dùng
- `FullName` - Họ tên
- `Email` - Email (unique)
- `PhoneNumber` - Số điện thoại
- `ZaloID` - ID Zalo (để gửi thông báo)
- `PasswordHash` - Mật khẩu đã hash
- `Role` - Vai trò: farmer, admin, expert
- `Region` - Tỉnh/thành phố
- `IsActive` - Trạng thái hoạt động
- `IsVerified` - Đã xác thực email
- `CreatedAt`, `UpdatedAt` - Thời gian

**Python Model:** `backend/app/models/user.py`

---

### 2. **CropTypes** - Loại nông sản
Danh mục các loại nông sản

**Columns:**
- `CropID` (PK) - ID nông sản
- `CropName` - Tên tiếng Việt (unique)
- `CropNameEN` - Tên tiếng Anh
- `Category` - Danh mục: Rau củ, Trái cây, Lúa gạo, Công nghiệp, Khác
- `GrowthDurationDays` - Số ngày từ gieo đến thu hoạch
- `HarvestSeason` - Mùa vụ thu hoạch
- `TypicalPriceMin`, `TypicalPriceMax` - Giá thông thường (VNĐ/kg)
- `Description` - Mô tả
- `ImageURL` - Link ảnh
- `CreatedAt` - Thời gian tạo

**Python Model:** `backend/app/models/crop.py`

---

### 3. **WeatherData** ⭐ MỚI - Dữ liệu thời tiết
Lưu trữ dữ liệu thời tiết theo khu vực

**Columns:**
- `WeatherID` (PK) - ID bản ghi
- `Region` - Khu vực
- `RecordDate` - Ngày ghi nhận
- `TempMin`, `TempMax` - Nhiệt độ thấp/cao nhất (°C)
- `Humidity` - Độ ẩm (%)
- `Rainfall` - Lượng mưa (mm)
- `SunshineHours` - Số giờ nắng
- `WeatherDesc` - Mô tả thời tiết
- `CreatedAt` - Thời gian tạo

**Python Model:** `backend/app/models/weather.py`

**Unique Constraint:** (Region, RecordDate)

---

### 4. **HarvestSchedule** - Lịch trình thu hoạch
Quản lý lịch trình trồng và thu hoạch của nông dân

**Columns:**
- `ScheduleID` (PK) - ID lịch trình
- `UserID` (FK) - ID người dùng
- `CropID` (FK) - ID nông sản
- `PlantingDate` - Ngày gieo trồng
- `AreaSize` - Diện tích (ha)
- `Region` - Khu vực
- `ExpectedHarvestDate` - Ngày thu hoạch dự kiến (AI tính)
- `ActualHarvestDate` - Ngày thu hoạch thực tế
- `EstimatedYieldKg` - Sản lượng ước tính (kg)
- `ActualYieldKg` - Sản lượng thực tế (kg)
- `FertilizerUsed` - Phân bón đã dùng
- `PesticideUsed` - Thuốc BVTV đã dùng
- `Status` - Trạng thái: Đang trồng, Sắp thu hoạch, Đã thu hoạch, Thất mùa
- `Notes` - Ghi chú
- `CreatedAt`, `UpdatedAt` - Thời gian

**Python Model:** `backend/app/models/crop.py`

---

### 5. **MarketPrices** - Giá thị trường hiện tại
Giá nông sản hiện tại từ các nguồn (web crawling)

**Columns:**
- `PriceID` (PK) - ID giá
- `CropID` (FK) - ID nông sản
- `Region` - Khu vực
- `PricePerKg` - Giá/kg (VNĐ)
- `QualityGrade` - Loại: Loại 1, Loại 2, Loại 3
- `MarketType` - Loại thị trường: Bán buôn, Bán lẻ, Xuất khẩu
- `SourceURL` - URL nguồn dữ liệu
- `SourceName` - Tên nguồn (agro.gov.vn, gia.vn, ...)
- `PriceDate` - Ngày ghi nhận giá
- `UpdatedAt` - Thời gian cập nhật

**Python Model:** `backend/app/models/price.py`

---

### 6. **PriceHistory** - Lịch sử biến động giá
Lịch sử giá theo ngày (dùng cho AI dự báo)

**Columns:**
- `HistoryID` (PK) - ID lịch sử
- `CropID` (FK) - ID nông sản
- `Region` - Khu vực
- `AvgPrice` - Giá trung bình ngày (VNĐ)
- `MinPrice` - Giá thấp nhất ngày
- `MaxPrice` - Giá cao nhất ngày
- `Volume` - Sản lượng giao dịch (tấn)
- `RecordDate` - Ngày ghi nhận
- `CreatedAt` - Thời gian tạo

**Python Model:** `backend/app/models/price.py`

**Unique Constraint:** (CropID, Region, RecordDate)

---

### 7. **PriceForecastResults** ⭐ MỚI - Kết quả dự báo giá
Lưu kết quả dự báo giá từ AI Model

**Columns:**
- `ForecastID` (PK) - ID dự báo
- `CropID` (FK) - ID nông sản
- `Region` - Khu vực
- `ForecastDate` - Ngày được dự báo
- `PredictedPrice` - Giá dự báo (VNĐ)
- `ConfidenceLow` - Khoảng tin cậy thấp
- `ConfidenceHigh` - Khoảng tin cậy cao
- `PriceTrend` - Xu hướng: Tăng, Giảm, Ổn định
- `ModelVersion` - Phiên bản AI model
- `GeneratedAt` - Thời gian tạo dự báo

**Python Model:** `backend/app/models/price.py`

---

### 8. **QualityRecords** - Kết quả kiểm tra chất lượng
Kết quả kiểm tra chất lượng nông sản bằng AI (YOLOv8)

**Columns:**
- `RecordID` (PK) - ID bản ghi
- `ScheduleID` (FK) - ID lịch trình (optional)
- `UserID` (FK) - ID người dùng
- `CropID` (FK) - ID nông sản
- `ImagePath` - Đường dẫn ảnh upload
- `AIGrade` - Phân loại: Loại 1, Loại 2, Loại 3
- `ConfidenceScore` - Độ tin cậy (0.0 - 1.0)
- `DetectedIssues` - Bệnh/sâu hại phát hiện (JSON)
- `SuggestedPriceMin`, `SuggestedPriceMax` - Giá đề xuất (VNĐ)
- `Recommendation` - Khuyến nghị xử lý
- `CheckDate` - Thời gian kiểm tra

**Python Model:** `backend/app/models/crop.py`

---

### 9. **AlertSubscriptions** - Đăng ký cảnh báo giá
Quản lý đăng ký nhận cảnh báo khi giá thay đổi

**Columns:**
- `AlertID` (PK) - ID cảnh báo
- `UserID` (FK) - ID người dùng
- `CropID` (FK) - ID nông sản
- `Region` - Khu vực
- `TargetPrice` - Giá mục tiêu (VNĐ)
- `AlertType` - Loại: Trên, Dưới, Thay đổi
- `NotifyMethod` - Phương thức: Email, SMS, Zalo, App
- `IsActive` - Trạng thái hoạt động
- `LastTriggered` - Lần cuối gửi cảnh báo
- `CreatedAt` - Thời gian tạo

**Python Model:** `backend/app/models/alert.py`

---

### 10. **AIConversations** ⭐ MỚI - Lịch sử hội thoại AI
Lưu trữ lịch sử chat với Claude AI

**Columns:**
- `ConvID` (PK) - ID hội thoại
- `UserID` (FK) - ID người dùng
- `SessionID` - ID phiên trò chuyện
- `UserMessage` - Câu hỏi của nông dân
- `AIResponse` - Trả lời của AI
- `Topic` - Chủ đề: Giá cả, Thu hoạch, Chất lượng, Thời tiết, Dịch bệnh, Khác
- `RelatedCropID` (FK) - ID nông sản liên quan
- `CreatedAt` - Thời gian tạo

**Python Model:** `backend/app/models/conversation.py`

---

## 📈 Indexes

Các index được tạo để tăng tốc truy vấn:

```sql
CREATE INDEX IDX_MarketPrices_Crop_Region    ON MarketPrices    (CropID, Region, PriceDate DESC);
CREATE INDEX IDX_PriceHistory_Crop_Region    ON PriceHistory    (CropID, Region, RecordDate DESC);
CREATE INDEX IDX_PriceForecast_Crop_Region   ON PriceForecastResults (CropID, Region, ForecastDate);
CREATE INDEX IDX_HarvestSchedule_User        ON HarvestSchedule (UserID, Status);
CREATE INDEX IDX_QualityRecords_User         ON QualityRecords  (UserID, CheckDate DESC);
CREATE INDEX IDX_AlertSubscriptions_Active   ON AlertSubscriptions (IsActive, CropID);
CREATE INDEX IDX_AIConversations_User        ON AIConversations (UserID, CreatedAt DESC);
```

---

## 🔗 Relationships

```
Users (1) ----< (N) HarvestSchedule
Users (1) ----< (N) QualityRecords
Users (1) ----< (N) AlertSubscriptions
Users (1) ----< (N) AIConversations

CropTypes (1) ----< (N) HarvestSchedule
CropTypes (1) ----< (N) MarketPrices
CropTypes (1) ----< (N) PriceHistory
CropTypes (1) ----< (N) PriceForecastResults
CropTypes (1) ----< (N) QualityRecords
CropTypes (1) ----< (N) AlertSubscriptions
CropTypes (1) ----< (N) AIConversations

HarvestSchedule (1) ----< (N) QualityRecords
```

---

## 📊 Seed Data

File `../database/NongNghiepAI_Full.sql` bao gồm dữ liệu mẫu:

- **5 Users** (4 farmers + 1 admin)
- **10 CropTypes** (Lúa, Ngô, Cà phê, Sầu riêng, Xoài, Thanh long, Rau muống, Cà chua, Khoai lang, Hồ tiêu)
- **8 WeatherData** records
- **5 HarvestSchedule** records
- **8 MarketPrices** records
- **31 PriceHistory** records (30 ngày cho Lúa - Hà Nội)

---

## 🚀 Setup

### 1. Chạy SQL Script
```sql
-- Trong SQL Server Management Studio (SSMS)
-- Mở file: docs/database/NongNghiepAI_Full.sql
-- Nhấn F5 để chạy
```

### 2. Test Connection
```bash
cd backend
pytest tests/test_api.py
```

### 3. Kết quả mong đợi
```
✓ All 10 models imported successfully
✓ Database connection successful!
✓ 10 tables with data
```

---

## 📝 Notes

- Tất cả bảng sử dụng **PascalCase** cho tên cột (theo chuẩn SQL Server)
- Python models có **property aliases** để tương thích snake_case
- Foreign keys có **ON DELETE** constraints phù hợp
- Unique constraints đảm bảo tính toàn vẹn dữ liệu
- Indexes được tối ưu cho các truy vấn thường dùng

---

**File SQL đầy đủ:** `docs/database/NongNghiepAI_Full.sql`
**Python Models:** `backend/app/models/`
