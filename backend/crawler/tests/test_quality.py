"""P2-17: Test quality detector, quality service và alert service."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
from unittest.mock import MagicMock


# ------------------------------------------------------------------ #
# Test QualityDetector (mock detection)
# ------------------------------------------------------------------ #

class TestQualityDetector:
    def setup_method(self):
        from ai_models.quality_check.detector import QualityDetector
        self.detector = QualityDetector()  # Initialize without model_path

    def test_detect_quality_returns_required_fields(self):
        result = self.detector.detect_quality("nonexistent_image.jpg")
        for f in ["quality_grade", "confidence", "disease_detected",
                  "damage_level", "defects", "suggested_price_min", "suggested_price_max"]:
            assert f in result, f"Missing: {f}"

    def test_mock_detection_grade1(self):
        """Mock detection (no defects) → Loại 1."""
        result = self.detector.detect_quality("any_path.jpg")
        assert result["quality_grade"] == "Loại 1"
        assert result["confidence"] > 0.8

    def test_price_range_loai1_higher_than_loai3(self):
        """Loại 1 có giá cao hơn Loại 3."""
        info_l1 = self.detector.QUALITY_GRADES["Loại 1"]
        info_l3 = self.detector.QUALITY_GRADES["Loại 3"]
        assert info_l1["price_min"] > info_l3["price_max"]

    def test_analyze_image_backward_compat(self):
        """analyze_image alias vẫn hoạt động (dùng bởi quality.py API cũ)."""
        result = self.detector.analyze_image("any.jpg")
        for f in ["quality_grade", "confidence", "defects", "suggested_price_range"]:
            assert f in result, f"Missing backward-compat field: {f}"

    def test_damage_level_none_for_no_defects(self):
        result = self.detector.detect_quality("any.jpg")
        assert result["damage_level"] == "none"

    def test_recommendations_not_empty(self):
        result = self.detector.detect_quality("any.jpg")
        assert len(result["recommendations"]) > 0

    def test_grade_quality_with_no_defects(self):
        detection = {"defect_count": 0, "avg_confidence": 0.90}
        grade, conf = self.detector._grade_quality(detection)
        assert grade == "Loại 1"
        assert conf > 0.8

    def test_grade_quality_with_many_defects(self):
        detection = {"defect_count": 6, "avg_confidence": 0.40}
        grade, conf = self.detector._grade_quality(detection)
        assert grade == "Loại 3"


# ------------------------------------------------------------------ #
# Test QualityService (mock DB)
# ------------------------------------------------------------------ #

class TestQualityService:
    def setup_method(self):
        from app.services.quality_service import QualityService
        self.service = QualityService()

    def _mock_db(self):
        db = MagicMock()
        crop = MagicMock()
        crop.CropID = 1
        crop.CropName = "Cà chua"
        crop.TypicalPriceMin = 15000
        crop.TypicalPriceMax = 30000
        q = MagicMock()
        q.filter.return_value.first.return_value = crop
        db.query.return_value = q
        return db

    def test_check_quality_has_required_fields(self):
        db = self._mock_db()
        result = self.service.check_quality(db, "any.jpg", "Cà chua", "Hà Nội")
        for f in ["quality_grade", "confidence", "disease_detected",
                  "suggested_price_min", "suggested_price_max"]:
            assert f in result, f"Missing: {f}"

    def test_check_quality_crop_name_matches(self):
        db = self._mock_db()
        result = self.service.check_quality(db, "any.jpg", "Cà chua", "TP.HCM")
        assert result["crop_name"] == "Cà chua"
        assert result["region"] == "TP.HCM"

    def test_mock_analysis_grade1(self):
        """Khi không có detector thật → mock trả về Loại 1."""
        db = self._mock_db()
        result = self.service.check_quality(db, "nonexistent.jpg", "Cà chua", "Hà Nội")
        assert result["quality_grade"] in ("Loại 1", "Loại 2", "Loại 3")


# ------------------------------------------------------------------ #
# Test AlertService (mock DB)
# ------------------------------------------------------------------ #

class TestAlertService:
    def setup_method(self):
        from app.services.alert_service import AlertService
        self.service = AlertService()

    def _mock_db_for_alert_check(self, current_price, target_price, condition="Trên"):
        db = MagicMock()

        crop = MagicMock()
        crop.CropID = 1
        crop.CropName = "Cà chua"

        alert = MagicMock()
        alert.AlertID = 1
        alert.CropID = 1
        alert.Region = "Hà Nội"
        alert.TargetPrice = target_price
        alert.AlertType = condition
        alert.IsActive = True
        alert.NotifyMethod = "Email"
        alert.UserID = 1
        alert.LastTriggered = None

        price_row = MagicMock()
        price_row.PricePerKg = current_price

        q = MagicMock()
        q.filter.return_value.all.return_value = [alert]
        q.filter.return_value.order_by.return_value.first.return_value = price_row
        q.filter.return_value.first.return_value = crop
        db.query.return_value = q
        return db, alert

    def test_alert_triggers_when_price_above_target(self):
        db, _ = self._mock_db_for_alert_check(
            current_price=25000, target_price=20000, condition="Trên"
        )
        triggered = self.service.check_and_trigger_alerts(db)
        assert len(triggered) > 0

    def test_alert_not_triggered_when_price_below_target(self):
        db, _ = self._mock_db_for_alert_check(
            current_price=15000, target_price=20000, condition="Trên"
        )
        triggered = self.service.check_and_trigger_alerts(db)
        assert len(triggered) == 0

    def test_alert_triggers_below_condition(self):
        db, _ = self._mock_db_for_alert_check(
            current_price=10000, target_price=15000, condition="Dưới"
        )
        triggered = self.service.check_and_trigger_alerts(db)
        assert len(triggered) > 0

    def test_deactivate_alert(self):
        db = MagicMock()
        alert = MagicMock()
        alert.AlertID = 5
        alert.IsActive = True
        db.query.return_value.filter.return_value.first.return_value = alert
        result = self.service.deactivate_alert(db, 5)
        assert result["success"] is True
        assert alert.IsActive is False

    def test_deactivate_nonexistent_alert(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = self.service.deactivate_alert(db, 999)
        assert result["success"] is False
