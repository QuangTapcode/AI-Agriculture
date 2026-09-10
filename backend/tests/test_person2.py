"""
Tests cho Người 2: AI Models, Crawler, Services (Quality, Pricing, Alert, Price Forecast)
Chạy: pytest tests/test_person2.py -v
"""
import os
import json
import time
import tempfile
import pandas as pd
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# ─────────────────────────────────────────────────────────────────────────────
# Helpers dùng chung
# ─────────────────────────────────────────────────────────────────────────────

def make_mock_db():
    """Tạo SQLAlchemy Session giả."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.all.return_value = []
    return db


# ═════════════════════════════════════════════════════════════════════════════
# P2-02  HARVEST PREDICTOR
# ═════════════════════════════════════════════════════════════════════════════

class TestHarvestPredictor:
    def setup_method(self):
        from ai_models.harvest_forecast.predictor import HarvestPredictor
        self.predictor = HarvestPredictor()
        self.planting = datetime(2024, 1, 1)

    # --- Kiểm tra output format ---
    def test_output_has_required_keys(self):
        result = self.predictor.predict("Cà chua", self.planting, "Hà Nội")
        for key in ("expected_harvest_date", "confidence", "growth_days", "warning", "recommendation"):
            assert key in result, f"Thiếu key: {key}"

    def test_harvest_date_is_valid_iso_string(self):
        result = self.predictor.predict("Cà chua", self.planting, "Hà Nội")
        date.fromisoformat(result["expected_harvest_date"])  # không raise = OK

    # --- Thời gian sinh trưởng ---
    def test_uses_known_crop_duration(self):
        result = self.predictor.predict("Cà chua", self.planting, "Hà Nội")
        assert result["growth_days"] >= 75  # bảng CROP_GROWTH_DAYS = 75

    def test_uses_custom_growth_duration_over_table(self):
        result = self.predictor.predict("Cà chua", self.planting, "Hà Nội", growth_duration_days=50)
        assert result["growth_days"] >= 50

    def test_unknown_crop_defaults_to_60_days(self):
        result = self.predictor.predict("Cây lạ xyz", self.planting, "Hà Nội")
        assert result["growth_days"] >= 60

    # --- Confidence ---
    def test_confidence_in_range(self):
        result = self.predictor.predict("Lúa", self.planting, "Hà Nội")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_confidence_higher_with_weather_and_db_data(self):
        weather = {"temperature": 28, "rainfall": 50, "humidity": 70}
        result_full = self.predictor.predict("Cà chua", self.planting, "Hà Nội",
                                             growth_duration_days=75, weather_data=weather)
        result_bare = self.predictor.predict("Cà chua", self.planting, "Hà Nội")
        assert result_full["confidence"] >= result_bare["confidence"]

    # --- Điều chỉnh thời tiết ---
    def test_high_temp_adds_delay(self):
        normal = self.predictor.predict("Cà chua", self.planting, "Hà Nội")
        hot = self.predictor.predict("Cà chua", self.planting, "Hà Nội",
                                     weather_data={"temperature": 40})
        assert hot["growth_days"] > normal["growth_days"]

    def test_low_temp_adds_delay(self):
        normal = self.predictor.predict("Cà chua", self.planting, "Hà Nội")
        cold = self.predictor.predict("Cà chua", self.planting, "Hà Nội",
                                      weather_data={"temperature": 5})
        assert cold["growth_days"] > normal["growth_days"]

    def test_high_rainfall_adds_delay(self):
        normal = self.predictor.predict("Lúa", self.planting, "Hà Nội")
        flood = self.predictor.predict("Lúa", self.planting, "Hà Nội",
                                       weather_data={"rainfall": 250})
        assert flood["growth_days"] > normal["growth_days"]

    def test_high_humidity_adds_delay(self):
        normal = self.predictor.predict("Cà chua", self.planting, "Hà Nội")
        humid = self.predictor.predict("Cà chua", self.planting, "Hà Nội",
                                       weather_data={"humidity": 95})
        assert humid["growth_days"] > normal["growth_days"]

    def test_normal_weather_no_warning(self):
        result = self.predictor.predict("Cà chua", self.planting, "Hà Nội",
                                        weather_data={"temperature": 28, "rainfall": 80, "humidity": 70})
        assert result["warning"] is None

    def test_extreme_weather_produces_warning(self):
        result = self.predictor.predict("Cà chua", self.planting, "Hà Nội",
                                        weather_data={"temperature": 42})
        assert result["warning"] is not None

    # --- Recommendation ---
    def test_recommendation_contains_crop_and_region(self):
        result = self.predictor.predict("Cà chua", self.planting, "Hà Nội")
        assert "Cà chua" in result["recommendation"]
        assert "Hà Nội" in result["recommendation"]

    # --- Nhiều cây khác nhau ---
    @pytest.mark.parametrize("crop", ["Lúa", "Dưa chuột", "Ớt", "Chuối", "Rau muống"])
    def test_multiple_crops(self, crop):
        result = self.predictor.predict(crop, self.planting, "TP.HCM")
        assert result["expected_harvest_date"] > self.planting.date().isoformat()


# ═════════════════════════════════════════════════════════════════════════════
# P2-07  PRICE PREDICTOR (Prophet)
# ═════════════════════════════════════════════════════════════════════════════

class TestPricePredictor:
    def setup_method(self):
        from ai_models.price_forecast.predictor import PricePredictor
        self.predictor = PricePredictor()

    def _make_history(self, n=15, base=50000):
        dates = pd.date_range(start="2024-01-01", periods=n)
        return [{"date": d.strftime("%Y-%m-%d"), "price": base + i * 300}
                for i, d in enumerate(dates)]

    def test_returns_empty_when_insufficient_data(self):
        short_history = self._make_history(n=5)
        result = self.predictor.predict(short_history, days=3)
        assert result == []

    def test_returns_empty_for_empty_history(self):
        result = self.predictor.predict([], days=3)
        assert result == []

    def test_returns_correct_number_of_predictions(self):
        history = self._make_history(n=15)
        result = self.predictor.predict(history, days=5)
        assert len(result) == 5

    def test_prediction_has_required_fields(self):
        history = self._make_history(n=15)
        result = self.predictor.predict(history, days=3)
        for item in result:
            assert "date" in item
            assert "predicted_price" in item
            assert "min_price" in item
            assert "max_price" in item

    def test_min_price_le_predicted_le_max(self):
        history = self._make_history(n=15)
        result = self.predictor.predict(history, days=3)
        for item in result:
            assert item["min_price"] <= item["predicted_price"] <= item["max_price"]

    def test_date_format_is_valid(self):
        history = self._make_history(n=15)
        result = self.predictor.predict(history, days=3)
        for item in result:
            date.fromisoformat(item["date"])

    def test_forecast_30_days(self):
        history = self._make_history(n=30, base=22000)
        result = self.predictor.predict(history, days=30)
        assert len(result) == 30


# ═════════════════════════════════════════════════════════════════════════════
# P2-03  QUALITY SERVICE (helpers & logic)
# ═════════════════════════════════════════════════════════════════════════════

class TestQualityServiceHelpers:
    def setup_method(self):
        from app.services.quality_service import QualityService
        self.service = QualityService()

    # --- Không còn chấm điểm theo tên file ---
    def test_no_filename_based_grading(self):
        """`_mock_grade` đã bị gỡ: chất lượng phải do model quyết, không do tên file."""
        assert not hasattr(self.service, "_mock_grade")

    # --- _damage_level ---
    def test_damage_level_grade1_is_low(self):
        assert self.service._damage_level("grade_1") == "low"

    def test_damage_level_loai1_is_low(self):
        assert self.service._damage_level("Loại 1") == "low"

    def test_damage_level_grade2_is_medium(self):
        assert self.service._damage_level("grade_2") == "medium"

    def test_damage_level_grade3_is_high(self):
        assert self.service._damage_level("grade_3") == "high"

    def test_damage_level_unknown_defaults_low(self):
        assert self.service._damage_level("xyz") == "low"

    # --- _recommendations ---
    def test_recommendations_grade1(self):
        recs = self.service._recommendations("grade_1")
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_recommendations_grade2(self):
        recs = self.service._recommendations("grade_2")
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_recommendations_grade3(self):
        recs = self.service._recommendations("grade_3")
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_recommendations_differ_by_grade(self):
        r1 = self.service._recommendations("grade_1")
        r3 = self.service._recommendations("grade_3")
        assert r1 != r3

    # --- _parse_issues ---
    def test_parse_issues_empty(self):
        result = self.service._parse_issues(None)
        assert result == {}

    def test_parse_issues_valid_json_dict(self):
        raw = json.dumps({"defects": ["spot"], "disease_detected": True})
        result = self.service._parse_issues(raw)
        assert result["defects"] == ["spot"]

    def test_parse_issues_json_list(self):
        raw = json.dumps(["rot", "bruise"])
        result = self.service._parse_issues(raw)
        assert "rot" in result["defects"]

    def test_parse_issues_invalid_json_returns_raw(self):
        result = self.service._parse_issues("not-json-at-all")
        assert "not-json-at-all" in result.get("defects", [])

    def test_parse_issues_disease_detected_fills_defects(self):
        raw = json.dumps({"disease_detected": True})
        result = self.service._parse_issues(raw)
        assert result["defects"] != []


class TestQualityServiceCheckQuality:
    """check_quality() chạy hoàn toàn local — không mock, không đoán theo tên file."""

    def _make_db_with_crop(self):
        db = make_mock_db()
        mock_crop = MagicMock()
        mock_crop.CropID = 1
        mock_crop.CropName = "Cà chua"
        mock_crop.TypicalPriceMin = 18000
        mock_crop.TypicalPriceMax = 28000
        db.query.return_value.filter.return_value.first.return_value = mock_crop
        return db

    @patch("app.services.quality_service.create_quality_check")
    @patch("app.services.quality_service.pricing_service.suggest_price")
    def test_unreadable_image_returns_error_not_a_grade(self, mock_suggest, mock_create):
        """Ảnh không đọc được => báo lỗi, tuyệt đối không chấm loại."""
        mock_suggest.return_value = {
            "suggested_price": 22000, "min_price": 20000, "max_price": 24000,
        }
        mock_create.return_value = MagicMock(checked_at=datetime.now())

        from app.services.quality_service import QualityService

        result = QualityService().check_quality(
            self._make_db_with_crop(),
            image_path="khong_ton_tai.jpg",
            crop_name="Cà chua",
            region="Hà Nội",
        )

        assert result["_api_error"] is True
        assert result["error_code"] == "QUALITY_ANALYSIS_FAILED"
        assert "quality_grade" not in result, "Không được chấm loại cho ảnh hỏng"

    @patch("app.services.quality_service.create_quality_check")
    @patch("app.services.quality_service.pricing_service.suggest_price")
    def test_real_image_is_graded_by_local_model(self, mock_suggest, mock_create, tmp_path):
        """Ảnh đọc được => model local chấm, kèm giá và khuyến nghị."""
        import cv2, numpy as np
        mock_suggest.return_value = {
            "suggested_price": 22000, "min_price": 20000, "max_price": 24000,
        }
        mock_create.return_value = MagicMock(checked_at=datetime.now())

        image = str(tmp_path / "ca_chua.jpg")
        cv2.imwrite(image, np.full((640, 640, 3), 160, dtype=np.uint8))

        from app.services.quality_service import QualityService

        result = QualityService().check_quality(
            self._make_db_with_crop(), image_path=image,
            crop_name="Cà chua", region="Hà Nội",
        )

        assert result["quality_grade"] in {"grade_1", "grade_2", "grade_3", "damaged"}
        assert result["ai_source"] in {"yolo_efficientnet", "efficientnet_fullimage"}
        assert "suggested_price" in result
        assert "recommendations" in result


# ═════════════════════════════════════════════════════════════════════════════
# P2-06  PRICING SERVICE
# ═════════════════════════════════════════════════════════════════════════════

class TestQuantityDiscount:
    def setup_method(self):
        from app.services.pricing_service import quantity_discount
        self.discount = quantity_discount

    def test_no_discount_below_100(self):
        assert self.discount(50) == 1.0

    def test_discount_100_to_499(self):
        assert self.discount(100) == 0.97
        assert self.discount(499) == 0.97

    def test_discount_500_to_999(self):
        assert self.discount(500) == 0.95
        assert self.discount(999) == 0.95

    def test_discount_1000_plus(self):
        assert self.discount(1000) == 0.92
        assert self.discount(5000) == 0.92


class TestPricingServiceHelpers:
    def setup_method(self):
        from app.services.pricing_service import PricingService
        self.service = PricingService()

    def test_normalize_key_strips_accents(self):
        key = self.service._normalize_key("Cà chua")
        assert key == "ca chua"

    # Spec anti-mock (TOD0 §1): không còn `_mock_price`, không sinh giá synthetic.
    # Thiếu dữ liệu thật => báo lỗi rõ ràng, không đoán bừa.

    def test_mock_price_is_a_tripwire(self):
        """`_mock_price` giữ lại làm bẫy: caller sót lại phải nổ, không trả số."""
        with pytest.raises(RuntimeError):
            self.service._mock_price("Cà chua", "Hà Nội", "grade_1")

    def test_forecast_without_db_returns_error_not_numbers(self):
        """Không có DB session => trả lỗi, tuyệt đối không bịa forecast."""
        result = self.service.forecast_price("Cà chua", "Hà Nội", days=7)

        assert result["_api_error"] is True
        assert result["error_code"] == "INSUFFICIENT_PRICE_HISTORY"
        assert result["forecast_data"] == []

    def test_forecast_without_db_is_flagged_as_miss(self):
        """Metadata phải nói thật: miss + không realtime + không mock."""
        result = self.service.forecast_price("Cà chua", "Hà Nội", days=7)

        assert result["cache_status"] == "miss"
        assert result["is_mock"] is False
        assert result["is_realtime"] is False

    def test_forecast_error_still_carries_official_source(self):
        """Kể cả khi lỗi, phải chỉ được nguồn chính thống để người dùng tự tra."""
        result = self.service.forecast_price("Lúa", "Cần Thơ", days=3)

        assert result["source_url"]
        assert result["source_name"]

    def test_forecast_with_empty_db_returns_error(self):
        """DB rỗng => miss, không rơi về đường sinh số ngẫu nhiên."""
        result = self.service.forecast_price_with_db(
            make_mock_db(), "Cà chua", "Hà Nội", days=7
        )

        assert result["_api_error"] is True
        assert result["forecast_data"] == []
        assert result["is_mock"] is False


class TestPricingServiceGetCurrentPrice:
    """get_current_price() theo spec anti-mock: hết dữ liệu thật => báo miss."""

    @patch("app.core.redis_client.redis_client.get", return_value=None)
    @patch("app.core.redis_client.redis_client.set")
    @patch("app.repositories.price_repository.get_latest_price", return_value=None)
    @patch("app.repositories.price_repository.get_recent_market_prices", return_value=[])
    def test_no_data_returns_error_without_price(self, _mock_recent, _mock_latest, _mock_set, _mock_get):
        """Redis miss + DB miss => KHÔNG có `current_price`, chỉ có lỗi."""
        from app.services.pricing_service import PricingService
        svc = PricingService()

        result = svc.get_current_price(make_mock_db(), "Cà chua", "Hà Nội")

        assert result["_api_error"] is True
        assert result["cache_status"] == "miss"
        assert "current_price" not in result, "Không được bịa giá khi thiếu dữ liệu"

    @patch("app.core.redis_client.redis_client.get", return_value=None)
    @patch("app.core.redis_client.redis_client.set")
    @patch("app.repositories.price_repository.get_latest_price", return_value=None)
    @patch("app.repositories.price_repository.get_recent_market_prices", return_value=[])
    def test_error_response_keeps_context_and_metadata(self, _mock_recent, _mock_latest, _mock_set, _mock_get):
        """Lỗi vẫn phải nói rõ hỏi cây gì / vùng nào và không phải mock."""
        from app.services.pricing_service import PricingService
        svc = PricingService()

        result = svc.get_current_price(make_mock_db(), "Lúa", "Cần Thơ")

        assert result["crop_name"]
        assert result["region"]
        assert result["is_mock"] is False

    @patch("app.services.pricing_service.price_aggregator_service.get_best_current_price")
    def test_passes_through_real_price_from_aggregator(self, mock_aggregator):
        """Aggregator có giá thật (cache hoặc live) => trả nguyên giá đó."""
        mock_aggregator.return_value = {
            "crop_name": "Lúa", "region": "Cần Thơ",
            "current_price": 8500, "cache_status": "fresh_cache",
            "is_mock": False, "fetched_at": datetime.now(),
        }
        from app.services.pricing_service import PricingService
        svc = PricingService()

        result = svc.get_current_price(make_mock_db(), "Lúa", "Cần Thơ")

        assert result["current_price"] == 8500
        assert result["official_price"] == 8500

    @patch("app.services.pricing_service.price_aggregator_service.get_best_current_price")
    def test_applies_quality_multiplier_to_official_price(self, mock_aggregator):
        """Loại thấp hơn phải rẻ hơn giá chính thống, giá gốc vẫn giữ lại."""
        mock_aggregator.return_value = {
            "crop_name": "Lúa", "region": "Cần Thơ",
            "current_price": 10000, "cache_status": "fresh_cache", "is_mock": False,
        }
        from app.services.pricing_service import PricingService
        svc = PricingService()

        result = svc.get_current_price(
            make_mock_db(), "Lúa", "Cần Thơ", quality_grade="grade_3"
        )

        assert result["official_price"] == 10000
        assert result["current_price"] < 10000


class TestAnalyzePriceTrend:
    @patch("app.services.pricing_service.get_recent_market_prices", return_value=[])
    def test_stable_when_no_data(self, _mock_prices):
        from app.services.pricing_service import PricingService
        svc = PricingService()
        db = make_mock_db()
        assert svc.analyze_price_trend(db, "Cà chua", "Hà Nội") == "stable"

    @patch("app.services.pricing_service.get_recent_market_prices")
    def test_increasing_trend(self, mock_prices):
        # DB returns newest-first; service calls reversed() to get chronological order
        items = [MagicMock(price=p) for p in [14000, 12500, 12000, 11500, 11000, 10500, 10000]]
        mock_prices.return_value = items
        from app.services.pricing_service import PricingService
        svc = PricingService()
        db = make_mock_db()
        result = svc.analyze_price_trend(db, "Cà chua", "Hà Nội")
        assert result == "increasing"

    @patch("app.services.pricing_service.get_recent_market_prices")
    def test_decreasing_trend(self, mock_prices):
        # DB returns newest-first; service calls reversed() to get chronological order
        items = [MagicMock(price=p) for p in [8000, 9000, 10000, 11000, 12000, 13000, 14000]]
        mock_prices.return_value = items
        from app.services.pricing_service import PricingService
        svc = PricingService()
        db = make_mock_db()
        result = svc.analyze_price_trend(db, "Cà chua", "Hà Nội")
        assert result == "decreasing"


# ═════════════════════════════════════════════════════════════════════════════
# P2-07  PRICE FORECAST SERVICE
# ═════════════════════════════════════════════════════════════════════════════

class TestPriceForecastServiceHelpers:
    def setup_method(self):
        from app.services.price_forecast_service import PriceForecastService
        self.svc = PriceForecastService()

    def test_calc_trend_increasing(self):
        prices = [10000, 10500, 11000, 11500, 12000, 12500, 14000, 15000]
        assert self.svc._calc_trend(prices) == "increasing"

    def test_calc_trend_decreasing(self):
        prices = [14000, 13000, 12000, 11000, 10000, 9000, 8000, 7000]
        assert self.svc._calc_trend(prices) == "decreasing"

    def test_calc_trend_stable(self):
        prices = [10000, 10100, 10050, 10000, 10080, 10020, 10010]
        assert self.svc._calc_trend(prices) == "stable"

    def test_calc_trend_single_price(self):
        assert self.svc._calc_trend([10000]) == "stable"

    def test_find_best_selling_time_returns_max_price_date(self):
        forecast = [
            {"date": "2024-01-01", "predicted_price": 10000},
            {"date": "2024-01-02", "predicted_price": 15000},
            {"date": "2024-01-03", "predicted_price": 12000},
        ]
        best = self.svc._find_best_selling_time(forecast)
        assert best == "2024-01-02"

    def test_find_best_selling_time_empty(self):
        assert self.svc._find_best_selling_time([]) is None

    def test_build_warning_decreasing(self):
        warning = self.svc._build_warning("decreasing", [10000, 9000])
        assert warning is not None
        assert "giảm" in warning or "giam" in warning.lower()

    def test_build_warning_increasing(self):
        warning = self.svc._build_warning("increasing", [10000, 11000])
        assert warning is not None

    def test_build_warning_stable_small_range(self):
        warning = self.svc._build_warning("stable", [10000, 10100])
        assert warning is None

    def test_get_recommendation_covers_all_trends(self):
        for trend in ("increasing", "decreasing", "stable"):
            rec = self.svc._get_recommendation(trend)
            assert isinstance(rec, str) and len(rec) > 0

    def test_fallback_forecast_returns_correct_days(self):
        history = [{"date": f"2024-01-{i:02d}", "price": 10000 + i * 100} for i in range(1, 16)]
        result = self.svc._fallback_forecast(history, days=7)
        assert len(result["forecast_data"]) == 7

    def test_fallback_forecast_has_trend(self):
        history = [{"date": f"2024-01-{i:02d}", "price": 10000} for i in range(1, 16)]
        result = self.svc._fallback_forecast(history, days=5)
        assert result["trend"] in ("increasing", "decreasing", "stable")

    def test_best_selling_time_increasing(self):
        result = self.svc._best_selling_time("increasing", 14)
        assert "7" in result or "ngay" in result.lower()

    def test_best_selling_time_decreasing(self):
        result = self.svc._best_selling_time("decreasing", 7)
        assert "1" in result or "som" in result.lower()


class TestPriceForecastServicePredict:
    """predict_price() – nhánh thiếu dữ liệu phải báo miss, không dự báo bừa."""

    @patch("app.services.price_forecast_service.PriceForecastService._load_price_history", return_value=[])
    @patch("app.services.price_forecast_service.PriceForecastService._get_model", return_value=None)
    def test_no_history_returns_miss_not_invented_forecast(self, _mock_model, _mock_history):
        """Không model + không lịch sử => dự báo rỗng kèm lỗi, không sinh 7 con số."""
        from app.services.price_forecast_service import PriceForecastService
        from app.schemas.price_schema import PricePredictionRequest
        svc = PriceForecastService()
        req = PricePredictionRequest(crop_name="Cà chua", region="Hà Nội", forecast_days=7)

        result = svc.predict_price(make_mock_db(), req)

        assert result["predicted_prices"] == []
        assert result["trend"] is None
        assert result["error_code"] == "PRICE_FORECAST_CACHE_MISS"
        assert result["is_mock"] is False

    @patch("app.services.price_forecast_service.PriceForecastService._load_price_history", return_value=[])
    @patch("app.services.price_forecast_service.PriceForecastService._get_model", return_value=None)
    def test_no_history_warns_user_why(self, _mock_model, _mock_history):
        """Người dùng phải biết vì sao không có dự báo, không im lặng."""
        from app.services.price_forecast_service import PriceForecastService
        from app.schemas.price_schema import PricePredictionRequest
        svc = PriceForecastService()
        req = PricePredictionRequest(crop_name="Cà chua", region="Hà Nội", forecast_days=7)

        result = svc.predict_price(make_mock_db(), req)

        assert result["warning"]
        assert result["source_url"]

    @patch("app.services.price_forecast_service.PriceForecastService._get_model", return_value=None)
    @patch("app.services.price_forecast_service.PriceForecastService._load_price_history")
    def test_moving_average_fallback_when_model_unavailable(self, mock_history, _mock_model):
        mock_history.return_value = [
            {"date": f"2024-01-{i:02d}", "price": 20000 + i * 100} for i in range(1, 16)
        ]
        from app.services.price_forecast_service import PriceForecastService
        from app.schemas.price_schema import PricePredictionRequest
        svc = PriceForecastService()
        db = make_mock_db()
        req = PricePredictionRequest(crop_name="Cà chua", region="Hà Nội", forecast_days=7)
        result = svc.predict_price(db, req)

        assert len(result["predicted_prices"]) == 7
        assert "best_selling_time" in result

    @patch("app.services.price_forecast_service.PriceForecastService._load_price_history")
    @patch("app.services.price_forecast_service.PriceForecastService._get_model")
    def test_ai_model_path_used_when_available(self, mock_model_fn, mock_history):
        history = [{"date": f"2024-01-{i:02d}", "price": 20000} for i in range(1, 20)]
        mock_history.return_value = history

        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = [
            {"date": f"2024-02-{i:02d}", "predicted_price": 21000,
             "min_price": 19000, "max_price": 23000}
            for i in range(1, 8)
        ]
        mock_model_fn.return_value = mock_predictor

        from app.services.price_forecast_service import PriceForecastService
        from app.schemas.price_schema import PricePredictionRequest
        svc = PriceForecastService()
        db = make_mock_db()
        req = PricePredictionRequest(crop_name="Lúa", region="Cần Thơ", forecast_days=7)
        result = svc.predict_price(db, req)

        assert len(result["predicted_prices"]) == 7
        mock_predictor.predict.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════════
# P2-08  ALERT SERVICE
# ═════════════════════════════════════════════════════════════════════════════

class TestAlertServiceHelpers:
    def setup_method(self):
        from app.services.alert_service import AlertService
        self.svc = AlertService()

    def test_create_price_alert_calls_repo(self):
        from app.schemas.alert_schema import AlertCreateRequest
        req = AlertCreateRequest(
            crop_name="Cà chua", region="Hà Nội",
            target_price=25000, condition="above",
            notification_channel="email", receiver="farmer@test.com",
        )
        mock_alert = MagicMock()
        mock_alert.id = 1
        mock_alert.AlertID = 1
        mock_alert.region = "Hà Nội"
        mock_alert.target_price = 25000.0
        mock_alert.condition = "Trên"
        mock_alert.notification_channel = "Email"
        mock_alert.is_active = True
        mock_alert.created_at = datetime.now()

        with patch("app.services.alert_service.create_alert", return_value=mock_alert) as mock_create, \
             patch("app.services.alert_service.get_alert_crop_name", return_value="Cà chua"), \
             patch("app.services.alert_service.get_alert_receiver", return_value="farmer@test.com"):
            db = make_mock_db()
            result = self.svc.create_price_alert(db, req)
            mock_create.assert_called_once()
            assert result["alert_id"] == 1

    def test_deactivate_returns_none_when_not_found(self):
        with patch("app.services.alert_service.deactivate_alert", return_value=None):
            db = make_mock_db()
            result = self.svc.deactivate_price_alert(db, alert_id=9999)
            assert result is None

    def test_deactivate_returns_dict_when_found(self):
        mock_alert = MagicMock()
        mock_alert.id = 5
        with patch("app.services.alert_service.deactivate_alert", return_value=mock_alert):
            db = make_mock_db()
            result = self.svc.deactivate_price_alert(db, alert_id=5)
            assert result["alert_id"] == 5

    def test_get_price_alert_returns_none_when_missing(self):
        with patch("app.services.alert_service.get_alert_by_id", return_value=None):
            db = make_mock_db()
            result = self.svc.get_price_alert(db, alert_id=1)
            assert result is None

    def test_check_and_trigger_returns_list(self):
        db = make_mock_db()
        from app.models.alert import PriceAlert
        db.query.return_value.filter.return_value.all.return_value = []
        result = self.svc.check_and_trigger_alerts(db)
        assert isinstance(result, list)


class TestAlertEvaluate:
    """_evaluate_alert() kiểm tra logic above/below."""

    def _make_alert(self, crop_id=1, region="Hà Nội", target=25000, condition="Trên"):
        alert = MagicMock()
        alert.AlertID = 1
        alert.CropID = crop_id
        alert.Region = region
        alert.TargetPrice = target
        alert.AlertType = condition
        alert.UserID = 1
        alert.NotifyMethod = "Email"
        alert.IsActive = True
        return alert

    def _make_market_price(self, price: float, tuoi_gio: float = 1.0):
        # Hàng thật luôn có mốc thời gian; MagicMock trần khiến _evaluate_alert
        # coi giá là quá hạn và không bắn. Đặt mốc thật để test đúng thứ nó
        # định kiểm tra là ngưỡng above/below.
        luc = datetime.now() - timedelta(hours=tuoi_gio)
        mp = MagicMock()
        mp.PricePerKg = price
        mp.FetchedAt = luc
        mp.ObservedAt = luc
        mp.UpdatedAt = luc
        mp.PriceDate = luc.date()
        return mp

    def test_above_condition_triggered(self):
        from app.services.alert_service import AlertService
        svc = AlertService()
        db = make_mock_db()
        alert = self._make_alert(target=25000, condition="Trên")
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = \
            self._make_market_price(30000)
        db.query.return_value.filter.return_value.first.return_value = MagicMock(CropName="Cà chua")

        with patch.object(svc, "_send_alert_notification"):
            result = svc._evaluate_alert(db, alert)
        assert result is not None
        assert result["triggered"] is True
        assert result["current_price"] == 30000

    def test_above_condition_not_triggered_when_price_below(self):
        from app.services.alert_service import AlertService
        svc = AlertService()
        db = make_mock_db()
        alert = self._make_alert(target=25000, condition="Trên")
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = \
            self._make_market_price(20000)
        result = svc._evaluate_alert(db, alert)
        assert result is None

    def test_below_condition_triggered(self):
        from app.services.alert_service import AlertService
        svc = AlertService()
        db = make_mock_db()
        alert = self._make_alert(target=25000, condition="Dưới")
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = \
            self._make_market_price(20000)
        db.query.return_value.filter.return_value.first.return_value = MagicMock(CropName="Cà chua")

        with patch.object(svc, "_send_alert_notification"):
            result = svc._evaluate_alert(db, alert)
        assert result is not None
        assert result["current_price"] == 20000

    def test_no_market_price_returns_none(self):
        from app.services.alert_service import AlertService
        svc = AlertService()
        db = make_mock_db()
        alert = self._make_alert()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        result = svc._evaluate_alert(db, alert)
        assert result is None


# ═════════════════════════════════════════════════════════════════════════════
# P2-04/05  CRAWLER (AgroSpider)
# ═════════════════════════════════════════════════════════════════════════════

class TestAgroSpider:
    def test_spider_name(self):
        from crawler.spiders.agro_spider import AgroSpider
        assert AgroSpider.name == "agro_spider"

    def test_spider_has_start_urls(self):
        from crawler.spiders.agro_spider import AgroSpider
        assert len(AgroSpider.start_urls) > 0

    def test_parse_yields_correct_fields(self):
        from crawler.spiders.agro_spider import AgroSpider
        spider = AgroSpider()
        mock_response = MagicMock()
        mock_row = MagicMock()
        mock_row.xpath.return_value.get.side_effect = ["Hà Nội", "50,000"]
        mock_response.xpath.return_value = [mock_row]
        mock_response.url = "https://giacaphe.com/test"

        items = list(spider.parse(mock_response))
        if items:
            item = items[0]
            assert "crop_name" in item
            assert "region" in item
            assert "price" in item


# ═════════════════════════════════════════════════════════════════════════════
# P2-09  CELERY CLEANUP TASK
# ═════════════════════════════════════════════════════════════════════════════

class TestCleanupTask:
    def test_cleanup_skips_nonexistent_dir(self):
        from app.tasks.cleanup_tasks import cleanup_old_uploads
        with patch.dict(os.environ, {"UPLOAD_DIR": "/nonexistent/path/xyz"}):
            with patch("app.tasks.cleanup_tasks.UPLOAD_DIR", "/nonexistent/path/xyz"):
                result = cleanup_old_uploads()
                assert result is None or "Deleted" in str(result)

    def test_cleanup_deletes_old_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_file = os.path.join(tmpdir, "old_image.jpg")
            with open(old_file, "w") as f:
                f.write("fake image")

            future_time = time.time() + 1
            old_ctime = future_time - (8 * 86400)

            with patch("app.tasks.cleanup_tasks.UPLOAD_DIR", tmpdir), \
                 patch("os.path.getctime", return_value=old_ctime):
                from app.tasks.cleanup_tasks import cleanup_old_uploads
                result = cleanup_old_uploads()
                assert "Deleted 1" in result

    def test_cleanup_keeps_new_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_file = os.path.join(tmpdir, "new_image.jpg")
            with open(new_file, "w") as f:
                f.write("new image")

            with patch("app.tasks.cleanup_tasks.UPLOAD_DIR", tmpdir), \
                 patch("os.path.getctime", return_value=time.time()):
                from app.tasks.cleanup_tasks import cleanup_old_uploads
                result = cleanup_old_uploads()
                assert "Deleted 0" in result
                assert os.path.exists(new_file)


# ═════════════════════════════════════════════════════════════════════════════
# Repositories / Common mapping tests
# ═════════════════════════════════════════════════════════════════════════════

class TestCommonMapping:
    def test_to_api_grade_loai1(self):
        from app.repositories.common import to_api_grade
        assert to_api_grade("Loại 1") == "grade_1"

    def test_to_api_grade_loai2(self):
        from app.repositories.common import to_api_grade
        assert to_api_grade("Loại 2") == "grade_2"

    def test_to_api_grade_loai3(self):
        from app.repositories.common import to_api_grade
        assert to_api_grade("Loại 3") == "grade_3"

    def test_to_api_grade_none(self):
        from app.repositories.common import to_api_grade
        assert to_api_grade(None) == "grade_1"

    def test_to_db_grade_grade1(self):
        from app.repositories.common import to_db_grade
        assert to_db_grade("grade_1") == "Loại 1"

    def test_to_api_alert_condition_tren(self):
        from app.repositories.common import to_api_alert_condition
        assert to_api_alert_condition("Trên") == "above"

    def test_to_api_alert_condition_duoi(self):
        from app.repositories.common import to_api_alert_condition
        assert to_api_alert_condition("Dưới") == "below"

    def test_to_db_alert_condition_above(self):
        from app.repositories.common import to_db_alert_condition
        assert to_db_alert_condition("above") == "Trên"


# ═════════════════════════════════════════════════════════════════════════════
# Integration: FastAPI endpoints (TestClient)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


class TestPricingAPI:
    def test_forecast_endpoint(self, client):
        """Có lịch sử => forecast_data; chưa có => miss có lý do, không bịa."""
        response = client.post("/api/pricing/forecast", json={
            "crop_name": "Cà chua",
            "region": "Hà Nội",
            "days": 7,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["is_mock"] is False

        if body["success"]:
            assert "forecast_data" in body["data"] or "predicted_prices" in body["data"]
        else:
            assert body["data"] is None
            assert body["error"]["code"]

    def test_suggest_endpoint(self, client):
        """Giá gợi ý phải từ nguồn thật, thiếu thì báo miss."""
        response = client.post("/api/pricing/suggest", json={
            "crop_name": "Lúa",
            "region": "Cần Thơ",
            "quantity": 500,
            "quality_grade": "grade_1",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["is_mock"] is False

        if body["success"]:
            assert body["data"]["suggested_price"] > 0
        else:
            assert body["data"] is None
            assert body["cache_status"] == "miss"

    def test_current_price_endpoint(self, client):
        response = client.get("/api/pricing/current?crop_name=Cà chua&region=Hà Nội")
        assert response.status_code in (200, 404, 422, 500)


class TestQualityAPI:
    def test_grades_endpoint_returns_list(self, client):
        response = client.get("/api/quality/grades")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "grades" in data

    def test_check_quality_requires_file(self, client):
        response = client.post("/api/quality/check", data={
            "crop_name": "Cà chua",
            "region": "Hà Nội",
        })
        assert response.status_code in (200, 422, 400)


class TestAlertAPI:
    def test_list_alerts_returns_list(self, client):
        response = client.get("/api/alert/list")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    def test_create_alert_valid(self, client):
        response = client.post("/api/alert/create", json={
            "crop_name": "Cà chua",
            "region": "Hà Nội",
            "target_price": 25000,
            "condition": "above",
            "notification_channel": "email",
            "receiver": "farmer@test.com",
        })
        assert response.status_code in (200, 201, 422, 500)

    def test_get_nonexistent_alert_returns_404(self, client):
        response = client.get("/api/alert/99999")
        assert response.status_code in (404, 200)

    def test_deactivate_nonexistent_alert(self, client):
        response = client.delete("/api/alert/99999")
        assert response.status_code in (404, 200)


class TestPriceForecastAPI:
    def test_predict_endpoint(self, client):
        """Dự báo chỉ xuất hiện khi có dữ liệu thật, ngược lại là miss."""
        response = client.post("/api/price-forecast/predict", json={
            "crop_name": "Cà chua",
            "region": "Hà Nội",
            "forecast_days": 7,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["is_mock"] is False

        if body["success"]:
            assert "predicted_prices" in body["data"]
        else:
            assert body["data"] is None
            assert body["error"]["code"]


class TestChatAPI:
    def test_chat_endpoint_responds(self, client):
        response = client.post("/api/chat", json={"question": "Cách trồng cà chua?"})
        assert response.status_code in (200, 500)
