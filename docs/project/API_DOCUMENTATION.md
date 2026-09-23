# API Documentation

Base URL: `http://localhost:8000`

## Authentication
Hiện tại chưa có authentication. Sẽ được thêm trong Phase 2.

## Endpoints

### Health Check

#### GET /health
Kiểm tra trạng thái server

**Response:**
```json
{
  "status": "healthy"
}
```

---

### Quality Check

#### POST /api/quality/check
Kiểm tra chất lượng nông sản qua ảnh

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` (image file)

**Response:**
```json
{
  "quality_grade": "grade_1",
  "confidence": 0.95,
  "defects": [],
  "defect_count": 0,
  "suggested_price_range": {
    "min": 25000,
    "max": 35000
  },
  "recommendations": [
    "Chất lượng tốt - phù hợp xuất khẩu hoặc siêu thị cao cấp",
    "Nên bán sớm để giữ độ tươi"
  ]
}
```

#### GET /api/quality/grades
Lấy danh sách phân loại chất lượng

**Response:**
```json
{
  "grades": [
    {
      "grade": "grade_1",
      "name": "Loại 1",
      "description": "Chất lượng cao, không khuyết tật",
      "price_multiplier": 1.0
    },
    {
      "grade": "grade_2",
      "name": "Loại 2",
      "description": "Chất lượng trung bình, ít khuyết tật",
      "price_multiplier": 0.7
    },
    {
      "grade": "grade_3",
      "name": "Loại 3",
      "description": "Chất lượng thấp, nhiều khuyết tật",
      "price_multiplier": 0.4
    }
  ]
}
```

---

### Pricing

#### POST /api/pricing/current
Lấy giá hiện tại của nông sản

**Request:**
```json
{
  "crop_name": "Cà chua",
  "region": "Hà Nội",
  "quality_grade": "grade_1"
}
```

**Response:**
```json
{
  "crop_name": "Cà chua",
  "region": "Hà Nội",
  "current_price": 20000.0,
  "quality_grade": "grade_1",
  "price_trend": "increasing",
  "last_updated": "2024-01-15T10:30:00"
}
```

#### POST /api/pricing/forecast
Dự báo giá trong N ngày tới

**Request:**
```json
{
  "crop_name": "Cà chua",
  "region": "Hà Nội",
  "days": 7
}
```

**Response:**
```json
{
  "crop_name": "Cà chua",
  "region": "Hà Nội",
  "forecast_data": [
    {
      "date": "2024-01-16",
      "predicted_price": 20500.0,
      "confidence_lower": 18860.0,
      "confidence_upper": 22140.0
    }
  ],
  "trend": "increasing",
  "recommendation": "Giá có xu hướng tăng. Nên giữ hàng thêm vài ngày để bán được giá tốt hơn."
}
```

#### GET /api/pricing/history/{crop_name}/{region}
Lấy lịch sử giá

**Parameters:**
- `crop_name`: Tên nông sản
- `region`: Khu vực
- `days`: Số ngày (query param, default: 30)

**Response:**
```json
{
  "crop_name": "Cà chua",
  "region": "Hà Nội",
  "history": [
    {
      "date": "2024-01-01",
      "avg_price": 19000,
      "min_price": 17000,
      "max_price": 21000
    }
  ]
}
```

#### GET /api/pricing/compare-regions/{crop_name}
So sánh giá giữa các khu vực

**Parameters:**
- `crop_name`: Tên nông sản

**Response:**
```json
{
  "crop_name": "Cà chua",
  "regions": [
    {
      "region": "Hà Nội",
      "price": 20000,
      "date": "2024-01-15"
    },
    {
      "region": "TP.HCM",
      "price": 21000,
      "date": "2024-01-15"
    }
  ]
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid input data"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error message"
}
```

---

## Rate Limiting
Chưa có rate limiting. Sẽ được thêm trong production.

## Versioning
API version: v1.0.0
