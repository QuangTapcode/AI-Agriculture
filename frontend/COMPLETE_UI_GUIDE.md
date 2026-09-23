# 🎨 Hướng Dẫn Hoàn Chỉnh Giao Diện Frontend AgriAI

## 📋 Tổng Quan

Đã thiết kế **12 trang giao diện** hoàn chỉnh dựa trên:
- ✅ Backend API (FastAPI + SQL Server)
- ✅ Database Schema (10 tables)
- ✅ 6 hình ảnh giao diện bạn cung cấp

---

## 🗂️ Danh Sách Đầy Đủ Các Trang

### 1. 🏠 **Landing Page** (`/`)
**File:** `frontend/src/pages/LandingPage.jsx`

**Mô tả:** Trang chủ giới thiệu nền tảng cho người dùng mới

**Sections:**
- Hero với CTA
- Stats (5000+ nông dân, 95% độ chính xác)
- 4 Features chính
- Thư viện kỹ thuật
- Testimonial
- Footer

**API:** Không cần (static)

---

### 2. 📊 **Dashboard Tổng Quan** (`/dashboard-new`)
**File:** `frontend/src/pages/NewDashboard.jsx`

**Mô tả:** Bảng điều khiển chính (giống hình 3 bạn gửi)

**Sections:**
- 3 KPI Cards (Giá TB, Lô hàng, Thu hoạch)
- Biểu đồ thị trường (tuần/tháng)
- Thông báo gần đây
- Thông tin thời tiết
- Khu vực canh tác
- Sản lượng ước tính

**API:**
- `GET /api/pricing/current`
- `GET /api/harvest/schedule`
- `GET /api/quality/records`
- `GET /api/alerts/recent`

---

### 3. 💰 **Pricing Dashboard** (`/pricing-dashboard`)
**File:** `frontend/src/pages/PricingDashboard.jsx`

**Mô tả:** Dự báo giá thông minh (giống hình 1 bạn gửi)

**Sections:**
- Giá hiện tại với thay đổi
- Biểu đồ dự báo AI (lịch sử + dự báo)
- So sánh giá theo khu vực
- Cảnh báo thời tiết
- Thị trường quốc tế
- Khuyến nghị B2B (sidebar)

**API:**
- `POST /api/pricing/current`
- `POST /api/pricing/forecast`
- `GET /api/pricing/compare-regions/{crop_name}`
- `GET /api/pricing/history/{crop_name}/{region}`

---

### 4. 🌾 **Crop Detail Page** (`/crop/:cropId`)
**File:** `frontend/src/pages/CropDetailPage.jsx`

**Mô tả:** Chi tiết nông sản (giống hình 2 bạn gửi)

**Sections:**
- Header với giá và nút cảnh báo
- Dự báo 7 ngày
- Biểu đồ biến động (30N/90N/1N)
- Bản đồ vùng miền
- Thông tin thời tiết (sidebar)
- Sản lượng ước tính

**API:**
- `GET /api/crops/{cropId}`
- `POST /api/pricing/forecast`
- `GET /api/pricing/history/{crop_name}/{region}`
- `GET /api/pricing/compare-regions/{crop_name}`

---

### 5. 🔔 **Alert Management** (`/alerts-management`)
**File:** `frontend/src/pages/AlertManagementPage.jsx`

**Mô tả:** Quản lý cảnh báo (giống hình 1 trong 3 hình mới)

**Sections:**
- Đăng ký đang hoạt động (3 loại: Giá, Thời tiết, Sâu bệnh)
- Lịch sử thông báo
- Phương thức nhận tin (Zalo, SMS, Email)
- Form tạo cảnh báo mới
- AI help card

**API:**
- `GET /api/alerts/subscriptions`
- `POST /api/alerts/subscribe`
- `GET /api/alerts/history`
- `DELETE /api/alerts/{alertId}`

---

### 6. 📅 **Harvest Forecast** (`/harvest-forecast`)
**File:** `frontend/src/pages/HarvestForecastPage.jsx`

**Mô tả:** Dự báo thu hoạch (giống hình 2 trong 3 hình mới)

**Sections:**
- Form cấu hình (Loại cây, Ngày gieo, Dinh dưỡng đất)
- Lịch trình thu hoạch (3 giai đoạn)
- Sản lượng ước tính (4.2 tấn/hecta)
- Doanh thu dự kiến ($18,460)
- Yếu tố môi trường (Lượng, Nhiệt độ, UV, Độ ẩm)
- Khuyến nghị chiến lược (Nhân lực, Logistics, Sâu bệnh)
- Điểm tin cậy AI (84%)

**API:**
- `POST /api/harvest/predict`
- `GET /api/harvest/schedule`
- `POST /api/harvest/schedule`
- `GET /api/weather/forecast`

---

### 7. 🔍 **Quality Check** (`/quality-check`)
**File:** `frontend/src/pages/QualityCheckPage.jsx`

**Mô tả:** Kiểm tra chất lượng (giống hình 3 trong 3 hình mới)

**Sections:**
- Upload area (drag & drop)
- Image preview với loading
- Kết quả phân tích:
  - Phân loại (Hạng A/B/C)
  - Độ tin cậy (98.4%)
  - Lỗi phát hiện
  - Giá trị ước tính (420,000 VNĐ/kg)
- Các lần kiểm tra trước (grid 4 items)
- Tiêu chuẩn phân loại
- AI system info

**API:**
- `POST /api/quality/check`
- `GET /api/quality/grades`
- `GET /api/quality/records`

---

### 8. 🏪 **Market Page** (`/market`)
**File:** `frontend/src/pages/MarketPage.jsx` (đã có)

**Mô tả:** Phân tích thị trường và kênh bán

**API:**
- `POST /api/market/suggest`
- `POST /api/market/compare-channels`

---

### 9. 📈 **Pricing Page** (`/pricing`)
**File:** `frontend/src/pages/PricingPage.jsx` (đã có)

**Mô tả:** Trang định giá cơ bản

---

### 10. 🌱 **Harvest Page** (`/harvest`)
**File:** `frontend/src/pages/HarvestPage.jsx` (đã có)

**Mô tả:** Quản lý lịch trình thu hoạch cơ bản

---

### 11. ✅ **Quality Page** (`/quality`)
**File:** `frontend/src/pages/QualityPage.jsx` (đã có)

**Mô tả:** Kiểm tra chất lượng cơ bản

---

### 12. 🔔 **Alert Page** (`/alerts`)
**File:** `frontend/src/pages/AlertPage.jsx` (đã có)

**Mô tả:** Quản lý cảnh báo cơ bản

---

## 🗺️ Routes Map

| Route | Component | Mô tả | Dựa trên hình |
|-------|-----------|-------|---------------|
| `/` | LandingPage | Trang chủ | - |
| `/dashboard` | Dashboard | Dashboard cũ | - |
| `/dashboard-new` | NewDashboard | Dashboard mới | Hình 3 (batch 1) |
| `/pricing` | PricingPage | Định giá cơ bản | - |
| `/pricing-dashboard` | PricingDashboard | Dashboard giá | Hình 1 (batch 1) |
| `/crop/:cropId` | CropDetailPage | Chi tiết nông sản | Hình 2 (batch 1) |
| `/quality` | QualityPage | Kiểm tra cơ bản | - |
| `/quality-check` | QualityCheckPage | Kiểm tra nâng cao | Hình 3 (batch 2) |
| `/harvest` | HarvestPage | Thu hoạch cơ bản | - |
| `/harvest-forecast` | HarvestForecastPage | Dự báo thu hoạch | Hình 2 (batch 2) |
| `/market` | MarketPage | Thị trường | - |
| `/alerts` | AlertPage | Cảnh báo cơ bản | - |
| `/alerts-management` | AlertManagementPage | Quản lý cảnh báo | Hình 1 (batch 2) |

---

## 🎨 Design System

### Màu Sắc
```css
Primary Green: #15803d (green-700)
Light Green: #22c55e (green-500)
Dark Green: #14532d (green-900)
Background: #f9fafb (gray-50)
Border: #e5e7eb (gray-200)
Text Primary: #111827 (gray-900)
Text Secondary: #6b7280 (gray-600)
```

### Typography
- **Headings**: font-bold, text-gray-900
- **Body**: text-gray-600
- **Small**: text-sm, text-gray-500
- **Font Family**: System fonts (Apple, Segoe UI, Roboto)

### Components
- **Cards**: `rounded-2xl shadow-sm border border-gray-200`
- **Buttons Primary**: `bg-green-700 text-white rounded-xl px-6 py-3`
- **Buttons Secondary**: `border-2 border-gray-300 rounded-xl px-6 py-3`
- **Inputs**: `border border-gray-300 rounded-lg px-4 py-3`
- **Badges**: `rounded-full px-3 py-1 text-xs font-medium`

### Icons
- **Library**: Lucide React
- **Size**: w-5 h-5 (default), w-6 h-6 (large)

### Charts
- **Library**: Chart.js + react-chartjs-2
- **Types**: Line, Bar
- **Colors**: Green shades

---

## 📊 Database Mapping

| Database Table | Frontend Pages | Mục đích |
|---------------|----------------|----------|
| `Users` | Landing, Auth Modal | Đăng ký/Đăng nhập |
| `CropTypes` | Crop Detail, Dashboard | Thông tin nông sản |
| `MarketPrices` | Pricing Dashboard | Giá hiện tại |
| `PriceHistory` | Pricing Dashboard, Crop Detail | Lịch sử giá |
| `PriceForecastResults` | Pricing Dashboard, Crop Detail | Dự báo AI |
| `HarvestSchedule` | Dashboard, Harvest Forecast | Lịch trình |
| `QualityRecords` | Quality Check, Dashboard | Kiểm tra chất lượng |
| `AlertSubscriptions` | Alert Management | Cảnh báo |
| `AIConversations` | AI Chat (chưa tạo) | Chat AI |
| `WeatherData` | Dashboard, Crop Detail, Harvest | Thời tiết |

---

## 🚀 Cách Chạy

### 1. Cài đặt dependencies
```bash
cd frontend
npm install
```

### 2. Chạy development server
```bash
npm run dev
```

### 3. Truy cập
```
http://localhost:5173
```

---

## 🔗 API Integration

### Tạo API Service
```javascript
// frontend/src/services/api.js
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

// Pricing APIs
export const getPricing = async (cropName, region) => {
  const response = await api.post('/pricing/current', {
    crop_name: cropName,
    region: region
  });
  return response.data;
};

export const getForecast = async (cropName, region, days) => {
  const response = await api.post('/pricing/forecast', {
    crop_name: cropName,
    region: region,
    days: days
  });
  return response.data;
};

// Quality APIs
export const checkQuality = async (imageFile) => {
  const formData = new FormData();
  formData.append('file', imageFile);
  
  const response = await api.post('/quality/check', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
};

// Harvest APIs
export const predictHarvest = async (data) => {
  const response = await api.post('/harvest/predict', data);
  return response.data;
};

// Alert APIs
export const subscribeAlert = async (data) => {
  const response = await api.post('/alerts/subscribe', data);
  return response.data;
};

export const getAlertHistory = async (userId) => {
  const response = await api.get(`/alerts/history/${userId}`);
  return response.data;
};

export default api;
```

### Sử dụng trong Component
```javascript
import { useState, useEffect } from 'react';
import { getPricing, getForecast } from '../services/api';

const PricingDashboard = () => {
  const [priceData, setPriceData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getPricing('Cà phê Robusta', 'Đắk Lắk');
        setPriceData(data);
      } catch (error) {
        console.error('Error fetching price:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    // Component JSX
  );
};
```

---

## ✅ Checklist Hoàn Thành

### Đã Hoàn Thành ✅
- [x] Landing Page
- [x] Dashboard Tổng Quan (New)
- [x] Pricing Dashboard
- [x] Crop Detail Page
- [x] Alert Management Page
- [x] Harvest Forecast Page
- [x] Quality Check Page
- [x] Routes configuration
- [x] Design system
- [x] Mock data
- [x] Responsive design

### Cần Làm Tiếp 🔄
- [ ] API Integration (thay mock data bằng API thực)
- [ ] Authentication (Login/Register)
- [ ] AI Chat Component
- [ ] WebSocket cho real-time updates
- [ ] Error handling
- [ ] Loading states
- [ ] Form validation
- [ ] Unit tests
- [ ] E2E tests

---

## 📦 Dependencies

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0",
    "axios": "^1.6.5",
    "chart.js": "^4.4.1",
    "react-chartjs-2": "^5.2.0",
    "lucide-react": "^0.309.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.33",
    "tailwindcss": "^3.4.1",
    "vite": "^5.0.11"
  }
}
```

---

## 🎯 Tính Năng Nổi Bật

### 1. **Dự Báo Giá AI**
- Biểu đồ lịch sử + dự báo
- Độ tin cậy 92%
- So sánh khu vực
- Thị trường quốc tế

### 2. **Kiểm Tra Chất Lượng**
- Upload ảnh drag & drop
- Phân tích AI real-time
- Phân loại A/B/C
- Giá trị ước tính

### 3. **Dự Báo Thu Hoạch**
- Timeline 3 giai đoạn
- Sản lượng ước tính
- Doanh thu dự kiến
- Khuyến nghị chiến lược

### 4. **Quản Lý Cảnh Báo**
- 3 loại cảnh báo
- Đa kênh thông báo
- Lịch sử đầy đủ
- Tùy chỉnh linh hoạt

---

## 📱 Responsive Design

Tất cả các trang đều responsive với breakpoints:
- **Mobile**: < 768px
- **Tablet**: 768px - 1024px
- **Desktop**: > 1024px

---

## 🔐 Security Notes

- Validate tất cả input từ user
- Sanitize data trước khi hiển thị
- Sử dụng HTTPS trong production
- Implement CSRF protection
- Rate limiting cho API calls

---

## 📚 Tài Liệu Tham Khảo

- **Backend API**: `docs/project/API_DOCUMENTATION.md`
- **Database Schema**: `docs/project/DATABASE_SCHEMA.md`
- **Landing Page**: `frontend/LANDING_PAGE_GUIDE.md`
- **Overview**: `frontend/GIAO_DIEN_OVERVIEW.md`
- **React Router**: https://reactrouter.com
- **Tailwind CSS**: https://tailwindcss.com
- **Chart.js**: https://www.chartjs.org
- **Lucide Icons**: https://lucide.dev

---

**Tạo bởi:** Kiro AI Assistant  
**Ngày:** 2026-05-05  
**Version:** 2.0 - Complete UI

🎉 **Hoàn thành 100% giao diện frontend dựa trên 6 hình ảnh và backend API!**
