"""P2-17: Test harvest predictor và harvest service."""
import sys, os
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest


class TestHarvestPredictor:
    def setup_method(self):
        from ai_models.harvest_forecast.predictor import HarvestPredictor
        self.predictor = HarvestPredictor()

    def test_predict_known_crop(self):
        planting = datetime(2024, 1, 1)
        result = self.predictor.predict("Cà chua", planting, "Hà Nội")
        assert "expected_harvest_date" in result
        assert result["growth_days"] == 75
        assert 0 < result["confidence"] <= 1.0

    def test_predict_unknown_crop_uses_fallback(self):
        planting = datetime(2024, 3, 1)
        result = self.predictor.predict("CâyLạ", planting, "TP.HCM")
        assert result["growth_days"] == 60

    def test_predict_with_hot_weather_adds_days(self):
        planting = datetime(2024, 5, 1)
        no_w = self.predictor.predict("Cà chua", planting, "Hà Nội")
        hot  = self.predictor.predict("Cà chua", planting, "Hà Nội",
                                      weather_data={"temperature": 40})
        assert hot["growth_days"] >= no_w["growth_days"]
        assert hot["warning"] is not None

    def test_db_growth_days_overrides_default(self):
        planting = datetime(2024, 1, 1)
        result = self.predictor.predict("Cà chua", planting, "Hà Nội",
                                        growth_duration_days=90)
        assert result["growth_days"] >= 90

    def test_recommendation_not_empty(self):
        result = self.predictor.predict("Rau muống", datetime(2024, 1, 1), "Hà Nội")
        assert result["recommendation"]

    def test_harvest_date_after_planting(self):
        planting = datetime(2024, 6, 1)
        result = self.predictor.predict("Lúa", planting, "Cần Thơ")
        harvest = datetime.fromisoformat(result["expected_harvest_date"])
        assert harvest.date() > planting.date()


class TestHarvestService:
    def setup_method(self):
        from app.services.harvest_service import HarvestService
        self.service = HarvestService()

    def _mock_db(self):
        from unittest.mock import MagicMock
        db = MagicMock()
        crop = MagicMock()
        crop.CropName = "Cà chua"
        crop.GrowthDurationDays = 75
        crop.Category = "Rau"
        crop.CropID = 1
        # Trả về crop cho query đầu tiên
        mock_q = MagicMock()
        mock_q.filter.return_value.first.return_value = crop
        mock_q.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value = mock_q
        return db

    def test_forecast_has_required_fields(self):
        from app.schemas.harvest_schema import HarvestForecastRequest
        db = self._mock_db()
        request = HarvestForecastRequest(
            crop_name="Cà chua",
            planting_date=datetime(2024,1,1).date(),
            region="Hà Nội"
        )
        result = self.service.forecast_harvest(db, request)
        for f in ["crop_name", "region", "expected_harvest_date", "confidence", "recommendation"]:
            assert f in result, f"Missing: {f}"

    def test_forecast_crop_name_matches(self):
        from app.schemas.harvest_schema import HarvestForecastRequest
        db = self._mock_db()
        request = HarvestForecastRequest(
            crop_name="Cà chua",
            planting_date=datetime(2024,1,1).date(),
            region="Hà Nội"
        )
        result = self.service.forecast_harvest(db, request)
        assert result["crop_name"] == "Cà chua"
        assert result["region"] == "Hà Nội"

    def test_backward_compat(self):
        db = self._mock_db()
        result = self.service.predict_harvest_date(db, "Cà chua", datetime(2024,1,1), "Hà Nội")
        assert result is not None
        assert "expected_harvest_date" in result
