"""
TDD: kiểm định chất lượng chạy hoàn toàn local, không phụ thuộc Gemini.

Trước đây khi YOLO không detect được bbox, nhánh EfficientNet toàn ảnh chỉ
chạy nếu người dùng có chọn loại quả. Không chọn thì rơi sang Gemini Vision —
vốn cần API key, nên thực tế trả grade_2 với confidence 0.0, tức chấm bừa.
"""
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from app.core.database import SessionLocal
from app.services.quality_service import QualityService

LOCAL_SOURCES = {"yolo_efficientnet", "efficientnet_fullimage"}


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def image(tmp_path):
    path = str(tmp_path / "produce.jpg")
    cv2.imwrite(path, np.full((640, 640, 3), 180, dtype=np.uint8))
    return path


def test_no_detection_without_crop_name_uses_local_model(db, image):
    """YOLO không ra bbox + người dùng không chọn loại => vẫn chấm local."""
    with patch.object(QualityService, "_run_yolo_pipeline", return_value=None):
        result = QualityService().check_quality(
            db, image_path=image, crop_name="", region="Ha Noi"
        )

    assert result.get("ai_source") in LOCAL_SOURCES, (
        f"Mong đợi model local, nhận được {result.get('ai_source')!r}"
    )


def test_quality_service_has_no_gemini_dependency():
    """Kiểm định chất lượng không được import/gọi Gemini nữa."""
    import importlib
    import inspect

    module = importlib.import_module("app.services.quality_service")
    source = inspect.getsource(module)
    assert "gemini" not in source.lower(), "quality_service vẫn tham chiếu Gemini"
    assert not hasattr(QualityService, "_get_detector"), "_get_detector vẫn còn"


def test_no_filename_based_grading():
    """`_mock_grade` chấm điểm theo tên file phải biến mất."""
    assert not hasattr(QualityService, "_mock_grade"), (
        "Vẫn còn chấm chất lượng dựa trên tên file"
    )
