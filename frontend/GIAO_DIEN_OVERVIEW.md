# Tổng Quan Các Giao Diện Frontend

## 📋 Danh Sách Các Trang Đã Thiết Kế

Dựa trên backend API và database schema, đã thiết kế các giao diện sau:

---

## 1. 🏠 Landing Page (`/`)
**File:** `frontend/src/pages/LandingPage.jsx`

### Mô tả:
Trang chủ giới thiệu nền tảng AgriAI cho người dùng mới

### Các phần chính:
- **Header/Navigation**: Logo, menu, nút đăng nhập/đăng ký
- **Hero Section**: Tiêu đề chính, CTA buttons, hình ảnh ruộng lúa
- **Stats Section**: 5000+ nông dân, 95% độ chính xác, 20% tăng năng suất
- **Features Section**: 4 tính năng chính (Dự báo, Định giá, Kiểm tra, AI Chat)
- **Articles Section**: Thư viện kỹ thuật canh tác
- **Testimonial**: Phản hồi từ nông dân
- **CTA Section**: Kêu gọi hành động cuối trang
- **Footer**: Thông tin công ty, links

### API sử dụng:
- Không cần API (static content)

---

## 2. 📊 Dashboard Tổng Quan (`/dashboard-new`)
**File:** `frontend/src/pages/NewDashboard.jsx`

### Mô tả:
Bảng điều khiển chính hiển thị tổng quan canh tác (giống hình 3 bạn gửi)

### Các phần chính:
- **3 KPI Cards**:
  - Giá thị trường trung bình: 18,500 VNĐ/kg (+12.4%)
  - Lô hàng chờ kiểm định: 08 lô
  - Ngày thu hoạch tiếp theo: 07 Th11 (Lúa Jasmine)

- **Biểu đồ Tổng Quan Thị Trường**:
  - Hiển thị xu hướng giá theo tuần/tháng
  - So sánh nhiều loại lúa (Jasmine 85, OM 5451)

- **Thông Báo Gần Đây**:
  - Cảnh báo thời tiết
  - Cảnh báo giá
  - Kiểm định hoàn tất

- **Thông Tin Thời Tiết**:
  - Độ ẩm đất: 32%
  - Nhiệt độ: 28°C

- **Khu Vực Canh Tác**:
  - Hiển thị các khu vực với hình ảnh
  - Trạng thái và tiến độ

- **Nguy Cơ Sâu Bệnh & Sản Lượng Ước Tính**

### API sử dụng:
- `GET /api/pricing/current` - Giá hiện tại
- `GET /api/harvest/schedule` - Lịch thu hoạch
- `GET /api/quality/records` - Lô hàng chờ kiểm định
- `GET /api/alerts/recent` - Thông báo gần đây
- `GET /api/weather/current` - Thời tiết

---

## 3. 💰 Pricing Dashboard (`/pricing-dashboard`)
**File:** `frontend/src/pages/PricingDashboard.jsx`

### Mô tả:
Trang dự báo giá thông minh (giống hình 1 bạn gửi)

### Các phần chính:
- **Header với Giá Hiện Tại**:
  - Cà phê Robusta: 42,500 VNĐ/kg
  - Thay đổi: +14.2%
  - Cập nhật thực tiếp

- **Biểu Đồ Dự Báo Giá**:
  - Lịch sử 4 tháng
  - Dự báo AI 3 tháng tới
  - Độ tin cậy: 92%
  - Lợi nhuận dự kiến: +14.2%

- **So Sánh Giá Theo Khu Vực**:
  - Đắk Lắk: 42,800 VNĐ/kg (+1.2%)
  - Lâm Đồng: 43,100 VNĐ/kg (+0.8%)
  - Long An: 41,500 VNĐ/kg (0.0%)
  - Mức tồn kho: CAO, RẤT CAO, BÌNH THƯỜNG

- **Cảnh Báo Thời Tiết**:
  - Tác động thời tiết đến giá
  - Dự báo mưa khô

- **Thị Trường Quốc Tế**:
  - London Robusta (LCE): $2,450/tấn (+2%)
  - Brazilian Conillon: $2,100/tấn (-1%)

- **Khuyến Nghị B2B** (Sidebar):
  - Xuất khẩu B2B trực tiếp
  - Giá hợp đồng: 46,200 VNĐ/kg
  - Lợi nhuận: +4,500 VNĐ/kg

### API sử dụng:
- `POST /api/pricing/current` - Giá hiện tại
- `POST /api/pricing/forecast` - Dự báo giá
- `GET /api/pricing/compare-regions/{crop_name}` - So sánh khu vực
- `GET /api/pricing/history/{crop_name}/{region}` - Lịch sử giá
- `GET /api/weather/forecast` - Dự báo thời tiết

---

## 4. 🌾 Crop Detail Page (`/crop/:cropId`)
**File:** `frontend/src/pages/CropDetailPage.jsx`

### Mô tả:
Trang chi tiết về một loại nông sản (giống hình 2 bạn gửi)

### Các phần chính:
- **Header**:
  - Tên nông sản: Lúa OM 5451
  - Vị trí: Ô Cần Thơ, Việt Nam
  - Giá hiện tại: 18,500 VNĐ/kg
  - Thay đổi: +2.4% (+450 VNĐ)
  - Nút "Đặt Cảnh Báo Giá"

- **Dự Báo 7 Ngày**:
  - Ngày 18: 18,750 VNĐ (+250)
  - Ngày 19: 19,100 VNĐ (+350)
  - Ngày 20: 19,050 VNĐ (-50)
  - Độ tin cậy cao/trung bình

- **Biểu Đồ Biến Động Giá**:
  - Tab: 30N, 90N, 1N
  - Line chart xu hướng
  - Bar chart so sánh

- **Bản Đồ Vùng Miền**:
  - Hiển thị giá theo khu vực trên bản đồ Việt Nam
  - Hà Nội: 18,900 VNĐ/kg
  - Cần Thơ: 18,500 VNĐ/kg
  - Đắk Lắk: 17,200 VNĐ/kg

- **Thông Tin Thời Tiết** (Sidebar):
  - Độ ẩm đất: 32%
  - Nhiệt độ: 28°C
  - Thời tiết sắp tới
  - Nguy cơ sâu bệnh
  - Sản lượng ước tính: 12.2t

### API sử dụng:
- `GET /api/crops/{cropId}` - Thông tin nông sản
- `POST /api/pricing/forecast` - Dự báo 7 ngày
- `GET /api/pricing/history/{crop_name}/{region}` - Lịch sử giá
- `GET /api/pricing/compare-regions/{crop_name}` - So sánh vùng miền
- `GET /api/weather/current` - Thời tiết hiện tại

---

## 5. 🔍 Quality Check Page (`/quality`)
**File:** `frontend/src/pages/QualityPage.jsx`

### Mô tả:
Trang kiểm tra chất lượng nông sản bằng AI

### Các phần chính:
- Upload hình ảnh nông sản
- Kết quả phân tích AI:
  - Phân loại: Loại 1, 2, 3
  - Độ tin cậy
  - Bệnh/sâu hại phát hiện
  - Giá đề xuất
  - Khuyến nghị xử lý

### API sử dụng:
- `POST /api/quality/check` - Kiểm tra chất lượng
- `GET /api/quality/grades` - Danh sách phân loại

---

## 6. 📅 Harvest Page (`/harvest`)
**File:** `frontend/src/pages/HarvestPage.jsx`

### Mô tả:
Trang quản lý lịch trình thu hoạch

### Các phần chính:
- Form nhập thông tin canh tác
- Dự báo ngày thu hoạch
- Ước tính sản lượng
- Lịch sử thu hoạch

### API sử dụng:
- `POST /api/harvest/predict` - Dự báo thu hoạch
- `GET /api/harvest/schedule` - Lịch trình
- `POST /api/harvest/schedule` - Tạo lịch trình mới

---

## 7. 🏪 Market Page (`/market`)
**File:** `frontend/src/pages/MarketPage.jsx`

### Mô tả:
Trang phân tích thị trường và kênh bán hàng

### Các phần chính:
- So sánh kênh bán (bán buôn, bán lẻ, xuất khẩu)
- Gợi ý thị trường tốt nhất
- Xu hướng cung cầu

### API sử dụng:
- `POST /api/market/suggest` - Gợi ý thị trường
- `POST /api/market/compare-channels` - So sánh kênh

---

## 8. 🔔 Alerts Page (`/alerts`)
**File:** `frontend/src/pages/AlertPage.jsx`

### Mô tả:
Trang quản lý cảnh báo giá

### Các phần chính:
- Đăng ký cảnh báo giá
- Lịch sử cảnh báo
- Cài đặt thông báo

### API sử dụng:
- `POST /api/alerts/subscribe` - Đăng ký cảnh báo
- `GET /api/alerts/history` - Lịch sử cảnh báo
- `DELETE /api/alerts/{alertId}` - Xóa cảnh báo

---

## 9. 💬 AI Chat (Component)
**File:** `frontend/src/components/AIChat.jsx` (cần tạo)

### Mô tả:
Chat với AI Claude để tư vấn nông nghiệp

### Các phần chính:
- Giao diện chat
- Lịch sử hội thoại
- Gợi ý câu hỏi

### API sử dụng:
- `POST /api/chat` - Gửi tin nhắn
- `GET /api/chat/history` - Lịch sử chat
- WebSocket cho real-time chat

---

## 📊 Mapping Backend → Frontend

### Database Tables → Pages:

| Database Table | Frontend Page | Mục đích |
|---------------|---------------|----------|
| `Users` | Landing Page, Auth Modal | Đăng ký/Đăng nhập |
| `CropTypes` | Crop Detail, Dashboard | Hiển thị thông tin nông sản |
| `MarketPrices` | Pricing Dashboard | Giá hiện tại |
| `PriceHistory` | Pricing Dashboard, Crop Detail | Biểu đồ lịch sử giá |
| `PriceForecastResults` | Pricing Dashboard, Crop Detail | Dự báo giá AI |
| `HarvestSchedule` | Dashboard, Harvest Page | Lịch trình thu hoạch |
| `QualityRecords` | Quality Page, Dashboard | Kiểm tra chất lượng |
| `AlertSubscriptions` | Alerts Page | Quản lý cảnh báo |
| `AIConversations` | AI Chat Component | Lịch sử chat |
| `WeatherData` | Dashboard, Crop Detail | Thông tin thời tiết |

---

## 🎨 Design System

### Màu sắc:
- **Primary Green**: `#15803d` (green-700)
- **Light Green**: `#22c55e` (green-500)
- **Dark Green**: `#14532d` (green-900)
- **Background**: `#f9fafb` (gray-50)
- **Border**: `#e5e7eb` (gray-200)

### Typography:
- **Headings**: Font-bold, text-gray-900
- **Body**: text-gray-600
- **Small**: text-sm, text-gray-500

### Components:
- **Cards**: rounded-2xl, shadow-sm, border
- **Buttons**: rounded-lg, px-6 py-3
- **Inputs**: rounded-lg, border-gray-300

---

## 🚀 Cách Chạy

```bash
cd frontend
npm install
npm run dev
```

Truy cập: `http://localhost:5173`

---

## 📝 Routes Summary

| Route | Component | Mô tả |
|-------|-----------|-------|
| `/` | LandingPage | Trang chủ |
| `/dashboard` | Dashboard | Dashboard cũ |
| `/dashboard-new` | NewDashboard | Dashboard mới (giống hình 3) |
| `/pricing` | PricingPage | Trang định giá cũ |
| `/pricing-dashboard` | PricingDashboard | Dashboard giá (giống hình 1) |
| `/crop/:cropId` | CropDetailPage | Chi tiết nông sản (giống hình 2) |
| `/quality` | QualityPage | Kiểm tra chất lượng |
| `/harvest` | HarvestPage | Quản lý thu hoạch |
| `/market` | MarketPage | Phân tích thị trường |
| `/alerts` | AlertPage | Quản lý cảnh báo |

---

## 🔄 Tích Hợp API

Tất cả các trang đã được thiết kế với mock data. Để tích hợp API thực:

1. Tạo file `frontend/src/services/api.js` với axios instance
2. Thay thế mock data bằng API calls
3. Thêm error handling và loading states
4. Thêm authentication headers

Ví dụ:
```javascript
// frontend/src/services/api.js
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

export const getPricing = async (cropName, region) => {
  const response = await api.post('/pricing/current', {
    crop_name: cropName,
    region: region
  });
  return response.data;
};
```

---

## ✅ Checklist Hoàn Thành

- [x] Landing Page
- [x] Dashboard Tổng Quan (New)
- [x] Pricing Dashboard
- [x] Crop Detail Page
- [x] Quality Check Page (đã có)
- [x] Harvest Page (đã có)
- [x] Market Page (đã có)
- [x] Alerts Page (đã có)
- [ ] AI Chat Component (cần tạo)
- [ ] Auth Modal (đã tạo nhưng chưa tích hợp)
- [ ] API Integration
- [ ] Authentication
- [ ] WebSocket cho real-time updates

---

## 📚 Tài Liệu Tham Khảo

- **Backend API**: `docs/project/API_DOCUMENTATION.md`
- **Database Schema**: `docs/project/DATABASE_SCHEMA.md`
- **Landing Page Guide**: `frontend/LANDING_PAGE_GUIDE.md`
- **Component Library**: Lucide React Icons
- **Charts**: Chart.js + react-chartjs-2
- **Routing**: React Router v6
- **Styling**: Tailwind CSS

---

**Tạo bởi:** Kiro AI Assistant
**Ngày:** 2026-05-05
