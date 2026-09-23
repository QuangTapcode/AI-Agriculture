# NongNghiepAI - TODO (theo spec anti-timeout + no-mock)

## 1) Loại bỏ mock data public (bắt buộc)
- [x] backend/app/services/market_news_service.py
  - Xóa `_fallback_news`
  - Khi realtime lỗi + DB cache không đủ => trả error:
    - `_api_error: true`, `cache_status: "miss"`, `is_mock: false`, `is_realtime: false`
  - Không lộ mock qua `get_market_trends()` (cưỡng ép `is_mock=false`)
- [x] backend/app/services/weather_service.py
  - Xóa `MOCK_WEATHER`
  - Xóa mọi nhánh trả dữ liệu mock (current/forecast/hourly/agriculture)
  - Khi realtime lỗi:
    - Nếu DB cache hợp lệ chưa quá TTL => trả stale_cache/fresh_cache (is_mock=false)
    - Nếu DB cache hết hạn/không có => trả error `_api_error=true`, `cache_status="miss"`
- [x] backend/app/services/pricing_service.py
  - Xóa `crop_base_prices`
  - Xóa `_mock_price` và mọi nhánh `is_mock=true`
  - `forecast_price/get_price_history`:
    - Nếu không có dữ liệu thật trong DB => trả error `cache_status="miss"` (không synthetic)
  - Đảm bảo mọi response public có đầy đủ metadata:
    - `source_name, source_url, is_realtime, is_mock(false), cache_status, fetched_at, last_updated, data_age_minutes`

## 2) Loại bỏ APIFarmer + Twelve Data khỏi luồng chính
- [ ] Rà soát integrations + services:
  - backend/app/integrations/apifarmer_client.py
  - backend/app/integrations/twelvedata_client.py
  - usage trong pricing/analysis/dashboard/health
- [ ] backend/app/services/data_source_service.py + dashboard realtime status:
  - Không hiển thị APIFarmer/TwelveData

## 3) Crawl official price/news theo TTL + background refresh
- [ ] Đảm bảo crawler lấy từ:
  - https://thitruongnongsan.gov.vn/vn/nguonwmy.aspx
  - https://thitruongnongsan.gov.vn/vn/xc0_tin-tuc.html
- [ ] Tạo/điều chỉnh scheduler để refresh định kỳ và ghi DB cache thật:
  - MarketPrice, MarketNews
  - Metadata: source_url/source_name/fetched_at/is_realtime(false)/is_mock(false)

## 4) Market analysis cache (không block dashboard)
- [ ] Tạo cached MarketAnalysisResult + endpoint GET gần nhất
- [ ] Endpoint refresh async
- [ ] Dashboard card load riêng, nếu analysis đang processing thì trả trạng thái processing

## 5) Frontend card-by-card + skeleton/error
- [ ] Sửa Dashboard.jsx để gọi API riêng cho từng card
- [ ] Hiển thị badge theo cache_status:
  - fresh_cache/stale_cache/live/miss/error
- [ ] Không hiển thị bất kỳ dữ liệu số nào nếu backend cache_status=miss

## 6) Test (không timeout + không mock)
- [ ] Test realtime success (weather/price/news)
- [ ] Test realtime timeout => trả miss/error, không số liệu giả
- [ ] Test dashboard: 1 card lỗi không làm chết toàn trang
