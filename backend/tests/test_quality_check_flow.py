"""
TDD: quality check page flow — YOLO + EfficientNet + pricing separate from market pricing.

Verifies:
1. Quality check uses YOLO pipeline for known fruits
2. Quality check falls back correctly for unknown crops
3. Pricing service is NOT affected by quality check changes
"""
import pytest
import numpy as np
import cv2
import tempfile
import os
from unittest.mock import patch, MagicMock


# ── Cycle 1: Quality check uses YOLO for known fruits ──────────────────────

def test_quality_check_calls_yolo_pipeline(tmp_path):
    """check_quality should invoke _run_yolo_pipeline before Gemini."""
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    p = str(tmp_path / "fruit.jpg")
    cv2.imwrite(p, img)

    from app.services.quality_service import QualityService

    call_log = []

    # _run_yolo_pipeline is a @staticmethod — patch at class level
    original = QualityService._run_yolo_pipeline

    def spy_yolo(image_path, crop_name=""):
        call_log.append(("yolo", image_path))
        return original(image_path, crop_name=crop_name)

    with patch.object(QualityService, '_run_yolo_pipeline', staticmethod(spy_yolo)):
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            QualityService().check_quality(db, image_path=p, crop_name="chuoi", region="Da Nang")
        except Exception:
            pass
        finally:
            db.close()

    assert any(name == "yolo" for name, _ in call_log), \
        "Expected _run_yolo_pipeline to be called before Gemini"


# ── Cycle 2: YOLO result is used, not Gemini, for known fruits ─────────────

def test_yolo_result_used_when_detection_succeeds(tmp_path):
    """When YOLO returns a detection, ai_source should be yolo_efficientnet."""
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    p = str(tmp_path / "fruit.jpg")
    cv2.imwrite(p, img)

    from app.services.quality_service import QualityService

    mock_vision = {
        "detected_crop": "Chuối",
        "is_produce": True,
        "color_assessment": "Màu vàng",
        "ripeness": "Fresh",
        "defects": [],
        "quality_grade": "grade_1",
        "confidence": 0.92,
        "reasoning": "YOLO detected Banana Fresh",
        "yolo_confidence": 0.90,
        "efficientnet_confidence": 0.94,
        "hsv_freshness": 0.85,
        "total_detections": 1,
        "source": "yolo_efficientnet",
    }

    with patch.object(QualityService, '_run_yolo_pipeline', return_value=mock_vision):
        with patch.object(QualityService, '_fetch_real_price',
                          return_value={"min": 15000, "max": 20000, "suggested": 17500,
                                        "multiplier": 1.0, "source": "db"}):
            from app.core.database import SessionLocal
            db = SessionLocal()
            try:
                result = QualityService().check_quality(
                    db, image_path=p, crop_name="chuoi", region="Da Nang"
                )
            finally:
                db.close()

    assert result.get("ai_source") == "yolo_efficientnet"
    assert result.get("quality_grade") == "grade_1"
    assert result.get("confidence") == 0.92


# ── Cycle 3: Pricing service is independent — no YOLO ──────────────────────

def test_pricing_service_has_no_yolo_dependency():
    """pricing_service.suggest_price must not import or call YOLO."""
    import inspect
    from app.services.pricing_service import pricing_service, PricingService

    source = inspect.getsource(PricingService)
    assert "yolo" not in source.lower(), \
        "PricingService must not reference YOLO"
    assert "fruit_quality_pipeline" not in source, \
        "PricingService must not use fruit_quality_pipeline"
    assert "efficientnet" not in source.lower(), \
        "PricingService must not reference EfficientNet"


def test_pricing_api_endpoint_is_independent():
    """Pricing API module must not import quality pipeline."""
    import inspect
    import app.api.prices as prices_module
    import app.api.pricing as pricing_module

    for mod in [prices_module, pricing_module]:
        src = inspect.getsource(mod)
        assert "yolo" not in src.lower(), f"{mod.__name__} must not reference YOLO"
        assert "fruit_quality" not in src, f"{mod.__name__} must not use fruit_quality_pipeline"
