# AgriAI Frontend

Giao diện React cho hệ thống **AgriAI** — nền tảng hỗ trợ nông nghiệp thông minh sử dụng AI, bao gồm dự báo giá, kiểm tra chất lượng sản phẩm, dự báo thu hoạch và tư vấn thị trường.

## Tech Stack

| Công nghệ | Phiên bản | Vai trò |
|-----------|-----------|---------|
| React | 18.2.0 | UI framework |
| Vite | 5.0.11 | Build tool & dev server |
| Tailwind CSS | 3.4.1 | Styling |
| React Router DOM | 6.21.0 | Client-side routing |
| Axios | 1.6.5 | HTTP client |
| Zustand | 4.4.7 | State management |
| Chart.js + react-chartjs-2 | 4.4.1 / 5.2.0 | Biểu đồ |
| Lucide React | 0.309.0 | Icons |

## Cài đặt & Chạy

### Yêu cầu
- Node.js >= 18
- npm >= 9
- Backend AgriAI đang chạy tại `http://localhost:8001`

### Bước 1: Cài dependencies
```bash
cd frontend
npm install
```

### Bước 2: Cấu hình môi trường
```bash
cp .env.example .env
```

Chỉnh sửa `.env`:
```env
VITE_API_URL=http://localhost:8001
```

### Bước 3: Khởi động dev server
```bash
npm run dev
```

Ứng dụng chạy tại: `http://localhost:5173`

## Scripts

| Lệnh | Mô tả |
|------|-------|
| `npm run dev` | Dev server (hot-reload) |
| `npm run build` | Build production |
| `npm run preview` | Preview bản build |

## Cấu trúc thư mục

```
frontend/
├── public/                    # Static assets
├── src/
│   ├── main.jsx               # Entry point
│   ├── App.jsx                # Routing chính
│   ├── index.css              # Global styles
│   ├── components/            # Reusable UI components
│   │   ├── Auth/              # ProtectedRoute
│   │   ├── Layout/            # Navbar, Sidebar
│   │   ├── UI/                # LoadingSpinner, StatusState, ...
│   │   ├── Alert/             # Alert components
│   │   ├── HarvestForecast/   # Harvest components
│   │   ├── Market/            # Market components
│   │   ├── Pricing/           # Pricing components
│   │   └── QualityCheck/      # Quality components
│   ├── contexts/
│   │   └── AuthContext.jsx    # Quản lý xác thực (JWT)
│   ├── hooks/
│   │   ├── useHarvest.js      # Harvest forecast hook
│   │   ├── usePriceData.js    # Price data hook
│   │   └── useWebSocket.js    # WebSocket hook (Phase 2)
│   ├── pages/                 # 27 trang ứng dụng
│   │   ├── (public)           # LandingPage, LoginPage, ...
│   │   └── (protected)        # Dashboard, PricingPage, ...
│   └── services/              # API clients
│       ├── api.js             # Axios instance + interceptors
│       ├── authApi.js
│       ├── cropsApi.js
│       ├── pricingApi.js
│       ├── harvestApi.js
│       ├── qualityApi.js
│       ├── alertApi.js
│       ├── weatherApi.js
│       ├── aiApi.js
│       └── marketApi.js
├── .env.example               # Template biến môi trường
├── package.json
├── tailwind.config.js
└── vite.config.js
```

## Trang & Routing

### Trang công khai (không cần đăng nhập)
| Route | Trang |
|-------|-------|
| `/` | Landing page |
| `/features` | Tính năng |
| `/articles` | Bài viết |
| `/pricing-plans` | Gói dịch vụ |
| `/contact` | Liên hệ |
| `/login` | Đăng nhập |
| `/register` | Đăng ký |

### Trang bảo vệ (yêu cầu đăng nhập)
| Route | Trang |
|-------|-------|
| `/dashboard` | Tổng quan |
| `/pricing` | Giá cả hiện tại |
| `/crop/:cropId` | Chi tiết loại cây |
| `/quality` | Kết quả kiểm tra chất lượng |
| `/weather` | Thời tiết & Dự báo |
| `/season-management` | Quản lý mùa vụ |
| `/alerts` | Cảnh báo giá |
| `/reports` | Báo cáo |
| `/ai-chat` | Tư vấn AI |
| `/notifications` | Thông báo |
| `/settings` | Cài đặt |
| `/profile` | Hồ sơ cá nhân |

Các URL cũ `/pricing-dashboard`, `/quality-check`, `/harvest`, `/harvest-forecast`,
`/market`, `/market-strategy` và `/alerts-management` được redirect về route chuẩn
tương ứng để giữ liên kết cũ hoạt động.

## Kết nối Backend

### Cấu hình
- **Base URL**: `VITE_API_URL` trong `.env` (mặc định: `http://localhost:8001`)
- **Auth**: Bearer token lưu trong `localStorage['token']`
- **Timeout**: 15 giây

### Luồng xác thực
1. Người dùng đăng nhập → `POST /api/auth/login`
2. Backend trả về `{ access_token, user }`
3. Token lưu vào `localStorage['token']`
4. Mọi request tiếp theo tự động gắn `Authorization: Bearer {token}`
5. Khi token hết hạn (401) → tự động chuyển về `/login`

### Các API endpoint chính

| Service | Endpoint |
|---------|----------|
| Đăng nhập | `POST /api/auth/login` |
| Đăng ký | `POST /api/auth/register` |
| Giá hiện tại | `GET /api/pricing/current` |
| Dự báo giá | `POST /api/pricing/forecast` |
| Lịch sử giá | `GET /api/pricing/history/{crop}/{region}` |
| Kiểm tra chất lượng | `POST /api/quality/check` |
| Dự báo thu hoạch | `POST /api/harvest/forecast` |
| Thời tiết | `GET /api/weather/current/{region}` |
| Cảnh báo giá | `POST /api/alert/create` |
| AI chat | `POST /api/chat` |
| Danh sách cây trồng | `GET /api/crops` |

Swagger UI: [http://localhost:8001/docs](http://localhost:8001/docs)

## Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `VITE_API_URL` | `http://localhost:8001` | URL của backend API |

## CORS

Backend cho phép requests từ:
- `http://localhost:5173` (Vite dev server)
- `http://localhost:3000`
- `http://127.0.0.1:5173`
- `http://127.0.0.1:3000`
