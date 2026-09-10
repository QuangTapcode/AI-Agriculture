"""
Price Forecast Service - merged Tien (schema/API) + Quang (AI model + rich analysis)
- API endpoint dùng: predict_price(db, request: PricePredictionRequest)
- Thử AI model trước, fallback về moving average, rồi về mock
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.real_data import OFFICIAL_AGRI_SOURCE_NAME, OFFICIAL_PRICE_URL, realtime_error
from app.schemas.price_schema import PricePredictionRequest
from app.services.pricing_service import pricing_service  # kept for legacy test monkeypatch compatibility


class PriceForecastService:
    """Service dự báo giá nông sản 7-30 ngày."""

    @staticmethod
    def _get_model():
        """Lazy import AI price forecast model (Quang)."""
        try:
            from ai_models.price_forecast.predictor import PricePredictor
            return PricePredictor()
        except ImportError:
            return None

    # ------------------------------------------------------------------ #
    # API interface
    # ------------------------------------------------------------------ #

    def predict_price(self, db: Session, request: PricePredictionRequest) -> dict:
        """
        Dự báo giá:
        1. Thử AI model (Quang's price_forecast model)
        2. Fallback về moving average từ DB history
        3. Hết dữ liệu thật: trả lỗi cache miss, không bịa số
        """
        crop_name = request.crop_name
        region = request.region
        forecast_days = request.forecast_days

        # Tải lịch sử giá từ DB để sử dụng cho cả AI model hoặc fallback
        price_history = self._load_price_history(db, crop_name, region, days=60)
        now = datetime.now()

        # 1. Thử AI model
        model = self._get_model()
        if model and price_history:
            try:
                predicted_prices = model.predict(historical_data=price_history, days=forecast_days)
                if predicted_prices:
                    trend = self._calc_trend([p["predicted_price"] for p in predicted_prices])
                    return {
                        "crop_name": crop_name,
                        "region": region,
                        "forecast_days": forecast_days,
                        "predicted_prices": predicted_prices,
                        "trend": trend,
                        "best_selling_time": self._find_best_selling_time(predicted_prices),
                        "warning": self._build_warning(trend, [p["predicted_price"] for p in predicted_prices]),
                        "recommendation": self._get_recommendation(trend),
                        "source_name": "Price forecast model",
                        "source_url": OFFICIAL_PRICE_URL,
                        "is_realtime": False,
                        "is_mock": False,
                        "cache_status": "fresh_cache",
                        "fetched_at": now,
                        "last_updated": now,
                        "data_age_minutes": 0,
                    }
            except Exception:
                pass

        # 2. Fallback: lịch sử giá từ DB + moving average
        if price_history:
            raw = self._fallback_forecast(price_history, forecast_days)
            predicted_prices = raw.get("forecast_data", [])
            trend = raw.get("trend", "stable")
            return {
                "crop_name": crop_name,
                "region": region,
                "forecast_days": forecast_days,
                "predicted_prices": predicted_prices,
                "trend": trend,
                "best_selling_time": self._find_best_selling_time(predicted_prices),
                "warning": self._build_warning(trend, [p["predicted_price"] for p in predicted_prices]),
                "recommendation": raw.get("recommendation", self._get_recommendation(trend)),
                "source_name": "PriceHistory DB",
                "source_url": OFFICIAL_PRICE_URL,
                "is_realtime": False,
                "is_mock": False,
                "cache_status": "fresh_cache",
                "fetched_at": now,
                "last_updated": now,
                "data_age_minutes": 0,
            }

        # 3. Hết đường: báo miss. Anti-mock (TOD0 §1) — không sinh giá synthetic.
        payload = realtime_error(
            code="PRICE_FORECAST_CACHE_MISS",
            message="Price forecast cache/history miss. Background refresh has not fetched enough real data yet.",
            source_name=OFFICIAL_AGRI_SOURCE_NAME,
            source_url=OFFICIAL_PRICE_URL,
        )
        payload.update(
            {
                "crop_name": crop_name,
                "region": region,
                "forecast_days": forecast_days,
                "predicted_prices": [],
                "trend": None,
                "best_selling_time": None,
                "warning": payload.get("error_message"),
            }
        )
        return payload

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _load_price_history(self, db: Session, crop_name: str, region: str, days: int = 60) -> List[Dict]:
        """Lấy lịch sử giá: ưu tiên PriceHistory, fallback sang MarketPrices (dữ liệu cào)."""
        try:
            from app.models.crop import CropType
            from app.models.price import MarketPrice, PriceHistory
            crop = db.query(CropType).filter(CropType.CropName == crop_name).first()
            if not crop:
                return []
            start = (datetime.now() - timedelta(days=days)).date()

            rows = (
                db.query(PriceHistory)
                .filter(
                    PriceHistory.CropID == crop.CropID,
                    PriceHistory.Region == region,
                    PriceHistory.RecordDate >= start,
                )
                .order_by(PriceHistory.RecordDate)
                .all()
            )
            if rows:
                return [{"date": r.RecordDate.isoformat(), "price": float(r.AvgPrice)} for r in rows]

            # Fallback: dùng MarketPrices (dữ liệu cào từ spider)
            market_rows = (
                db.query(MarketPrice)
                .filter(
                    MarketPrice.CropID == crop.CropID,
                    MarketPrice.Region.ilike(f"%{region}%"),
                    MarketPrice.PriceDate >= start,
                    MarketPrice.SourceURL.isnot(None),
                    MarketPrice.SourceName.isnot(None),
                    MarketPrice.FetchedAt.isnot(None),
                    MarketPrice.IsMock == False,  # noqa: E712
                )
                .order_by(MarketPrice.PriceDate)
                .all()
            )
            return [{"date": r.PriceDate.isoformat(), "price": float(r.PricePerKg)} for r in market_rows]
        except Exception:
            return []

    @staticmethod
    def _fallback_forecast(history: List[Dict], days: int) -> Dict:
        """Ngoại suy tuyến tính từ lịch sử thật, không thêm dao động bịa.

        Bản cũ lấy trung bình 7 điểm rồi nhân với một "nhiễu"

            noise = 0.01 * ((i * 7) % 5 - 2) / 5

        vốn chỉ là hàm của chỉ số vòng lặp, không mang tin tức gì. Lịch sử
        phẳng 96.000 vẫn ra [96000, 96384, 96191, 96384, ...] rồi _calc_trend
        đọc chính đường đó và tuyên bố có xu hướng. TOD0 §1 cấm sinh dữ liệu.

        Cần tối thiểu 3 điểm mới nói được xu hướng; ít hơn thì trả rỗng để
        tầng trên báo cache miss.
        """
        gia = [float(h["price"]) for h in history if h.get("price") is not None]
        SO_DIEM_TOI_THIEU = 3
        if len(gia) < SO_DIEM_TOI_THIEU:
            return {"forecast_data": [], "trend": "stable",
                    "recommendation": PriceForecastService._get_recommendation("stable")}

        # Độ dốc trung bình mỗi ngày trên cửa sổ gần nhất.
        cua_so = gia[-7:] if len(gia) >= 7 else gia
        doc = (cua_so[-1] - cua_so[0]) / max(len(cua_so) - 1, 1)
        neo = cua_so[-1]

        # Biên độ lấy từ biến động thật của lịch sử, tối thiểu 3%.
        bien_dong = (max(cua_so) - min(cua_so)) / neo if neo else 0.0
        bien = max(0.03, round(bien_dong, 4))

        forecast_data = []
        for i in range(1, days + 1):
            du_bao = max(0.0, neo + doc * i)
            forecast_data.append({
                "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
                "predicted_price": round(du_bao),
                "min_price": round(du_bao * (1 - bien)),
                "max_price": round(du_bao * (1 + bien)),
            })

        trend = PriceForecastService._calc_trend([f["predicted_price"] for f in forecast_data])
        return {
            "forecast_data": forecast_data,
            "trend": trend,
            "recommendation": PriceForecastService._get_recommendation(trend),
        }

    @staticmethod
    def _calc_trend(prices: List[float]) -> str:
        if len(prices) < 2:
            return "stable"
        mid = max(len(prices) // 2, 1)
        first = sum(prices[:mid]) / mid
        second = sum(prices[mid:]) / max(len(prices) - mid, 1)
        change = ((second - first) / first) * 100
        if change > 5:
            return "increasing"
        if change < -5:
            return "decreasing"
        return "stable"

    @staticmethod
    def _find_best_selling_time(forecast_data: List[Dict]) -> Optional[str]:
        """Tìm ngày có giá dự báo cao nhất."""
        if not forecast_data:
            return None
        best = max(forecast_data, key=lambda x: x.get("predicted_price", 0))
        return best.get("date")

    @staticmethod
    def _best_selling_time(trend: str, forecast_days: int) -> str:
        if trend == "increasing":
            return f"Cân nhắc bán sau {min(forecast_days, 7)} ngày nếu bảo quản tốt."
        if trend == "decreasing":
            return "Nên bán sớm trong 1-2 ngày tới."
        return "Có thể bán bất kỳ thời điểm phù hợp trong kỳ dự báo."

    @staticmethod
    def _build_warning(trend: str, prices: List[float]) -> Optional[str]:
        if trend == "decreasing":
            return "Giá có xu hướng giảm trong thời gian tới. Cân nhắc bán sớm."
        if trend == "increasing":
            return "Giá có xu hướng tăng. Có thể chờ thêm để bán giá tốt hơn."
        if prices and min(prices) > 0 and max(prices) / min(prices) > 1.2:
            return "Giá biến động lớn. Theo dõi thị trường trước khi quyết định."
        return None

    @staticmethod
    def _get_recommendation(trend: str) -> str:
        recs = {
            "increasing": "Giá đang tăng – nên giữ hàng thêm vài ngày để bán được giá tốt hơn.",
            "decreasing": "Giá đang giảm – nên bán sớm để tránh mất giá.",
            "stable": "Giá ổn định – có thể bán bất kỳ lúc nào phù hợp với kế hoạch.",
        }
        return recs.get(trend, "Theo dõi thị trường để chọn thời điểm bán phù hợp.")


price_forecast_service = PriceForecastService()
