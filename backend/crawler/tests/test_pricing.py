"""P2-17: Test pricing service, price forecast service và crawler pipeline."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
from unittest.mock import MagicMock, patch


# ------------------------------------------------------------------ #
# Test PricingService
# ------------------------------------------------------------------ #

class TestPricingService:
    def setup_method(self):
        from app.services.pricing_service import PricingService
        self.service = PricingService()

    def _mock_db_with_price(self, price=20000.0):
        db = MagicMock()
        crop = MagicMock()
        crop.CropID = 1
        crop.CropName = "Cà chua"
        crop.TypicalPriceMin = 15000
        crop.TypicalPriceMax = 30000

        price_row = MagicMock()
        price_row.PricePerKg = price
        price_row.PriceDate = MagicMock()
        price_row.Region = "Hà Nội"
        price_row.IsMock = False
        price_row.SourceURL = "http://test.com"
        price_row.SourceName = "Test Source"
        price_row.FetchedAt = MagicMock()

        q = MagicMock()
        q.filter.return_value.first.return_value = crop
        q.filter.return_value.order_by.return_value.first.return_value = price_row
        q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        q.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value = q
        db.rollback = MagicMock()
        return db

    def test_suggest_price_returns_required_fields(self):
        from app.schemas.price_schema import PricingSuggestRequest
        db = self._mock_db_with_price(20000)
        request = PricingSuggestRequest(crop_name="Cà chua", region="Hà Nội", quantity=100, quality_grade="Loại 1")
        result = self.service.suggest_price(db, request)
        for f in ["suggested_price", "min_price", "max_price", "crop_name"]:
            assert f in result, f"Missing: {f}"

    def test_suggest_price_loai1_higher_than_loai3(self):
        from app.schemas.price_schema import PricingSuggestRequest
        db = self._mock_db_with_price(20000)
        r1 = self.service.suggest_price(db, PricingSuggestRequest(crop_name="Cà chua", region="Hà Nội", quantity=100, quality_grade="Loại 1"))
        db2 = self._mock_db_with_price(20000)
        r3 = self.service.suggest_price(db2, PricingSuggestRequest(crop_name="Cà chua", region="Hà Nội", quantity=100, quality_grade="Loại 3"))
        assert r1["suggested_price"] > r3["suggested_price"]

    def test_suggest_price_bulk_discount(self):
        """Số lượng lớn phải có giá đề xuất thấp hơn."""
        from app.schemas.price_schema import PricingSuggestRequest
        db1 = self._mock_db_with_price(20000)
        r_small = self.service.suggest_price(db1, PricingSuggestRequest(crop_name="Cà chua", region="Hà Nội", quantity=10, quality_grade="Loại 1"))
        db2 = self._mock_db_with_price(20000)
        r_large = self.service.suggest_price(db2, PricingSuggestRequest(crop_name="Cà chua", region="Hà Nội", quantity=1000, quality_grade="Loại 1"))
        assert r_large["suggested_price"] <= r_small["suggested_price"]

    def test_suggest_price_min_max_range(self):
        from app.schemas.price_schema import PricingSuggestRequest
        db = self._mock_db_with_price(20000)
        result = self.service.suggest_price(db, PricingSuggestRequest(crop_name="Cà chua", region="Hà Nội", quantity=50, quality_grade="Loại 2"))
        assert result["min_price"] <= result["suggested_price"] <= result["max_price"]

    def test_analyze_trend_with_no_data(self):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        db.query.return_value = q
        trend = self.service.analyze_price_trend(db, "Cà chua", "Hà Nội")
        assert trend == "stable"


# ------------------------------------------------------------------ #
# Test PriceForecastService
# ------------------------------------------------------------------ #

class TestPriceForecastService:
    def setup_method(self):
        from app.services.price_forecast_service import PriceForecastService
        self.service = PriceForecastService()

    def _mock_db(self):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = None   # no crop
        q.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value = q
        return db

    def test_predict_returns_required_fields(self):
        from app.schemas.price_schema import PricePredictionRequest
        db = self._mock_db()
        request = PricePredictionRequest(crop_name="Cà chua", region="Hà Nội", forecast_days=7)
        result = self.service.predict_price(db, request)
        for f in ["crop_name", "region", "forecast_days", "predicted_prices", "trend"]:
            assert f in result, f"Missing: {f}"

    def test_predicted_prices_count(self):
        from app.schemas.price_schema import PricePredictionRequest
        db = self._mock_db()
        request = PricePredictionRequest(crop_name="Cà chua", region="Hà Nội", forecast_days=14)
        result = self.service.predict_price(db, request)
        assert len(result["predicted_prices"]) == 14

    def test_trend_is_valid(self):
        from app.schemas.price_schema import PricePredictionRequest
        db = self._mock_db()
        request = PricePredictionRequest(crop_name="Cà chua", region="Hà Nội", forecast_days=7)
        result = self.service.predict_price(db, request)
        assert result["trend"] in ("increasing", "decreasing", "stable", None)

    def test_best_selling_time_is_date_string(self):
        from app.schemas.price_schema import PricePredictionRequest
        db = self._mock_db()
        request = PricePredictionRequest(crop_name="Cà chua", region="Hà Nội", forecast_days=7)
        result = self.service.predict_price(db, request)
        if result["best_selling_time"]:
            # Phải là ngày hợp lệ
            from datetime import datetime
            datetime.strptime(result["best_selling_time"], "%Y-%m-%d")


# ------------------------------------------------------------------ #
# Test Crawler Pipeline (không cần DB thật)
# ------------------------------------------------------------------ #

class TestDataCleaningPipeline:
    def setup_method(self):
        from crawler.pipelines import DataCleaningPipeline
        self.pipeline = DataCleaningPipeline()
        self.spider = MagicMock()

    def _make_item(self, **kwargs):
        from crawler.items import MarketPriceItem
        item = MarketPriceItem()
        defaults = {
            "crop_name": "Cà chua", "region": "Hà Nội",
            "price_per_kg": 20000, "quality_grade": "grade_1",
            "source": "test", "date": "2024-01-01"
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            item[k] = v
        return item

    def test_valid_item_passes_through(self):
        item = self._make_item()
        result = self.pipeline.process_item(item, self.spider)
        assert result is not None
        assert result["price_per_kg"] == 20000.0

    def test_invalid_price_returns_none(self):
        item = self._make_item(price_per_kg="abc")
        result = self.pipeline.process_item(item, self.spider)
        assert result is None

    def test_quality_grade_normalized(self):
        item = self._make_item(quality_grade="grade_1")
        result = self.pipeline.process_item(item, self.spider)
        assert result["quality_grade"] == "Loại 1"

    def test_crop_name_stripped(self):
        item = self._make_item(crop_name="  Cà chua  ")
        result = self.pipeline.process_item(item, self.spider)
        assert result["crop_name"] == "Cà chua"

    def test_price_too_high_rejected(self):
        item = self._make_item(price_per_kg=999999)
        result = self.pipeline.process_item(item, self.spider)
        assert result is None

    def test_collected_at_added(self):
        item = self._make_item()
        result = self.pipeline.process_item(item, self.spider)
        assert "collected_at" in result and result["collected_at"]
