"""
TDD: các module đã chết phải biến mất, và app vẫn khởi động được.

Danh sách này được xác định bằng rà soát import thực tế: 0 chỗ dùng trong
app/, crawler/ hay ai_models/. Giữ lại chỉ tạo hiểu nhầm — nhất là
`price_model.py` chứa `_simple_forecast()` sinh giá bằng random.uniform,
trái spec anti-mock (TOD0 §1).
"""
import importlib
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent

DEAD_FILES = [
    "ai_models/price_forecast/price_model.py",
    "ai_models/harvest_forecast/prophet_model.py",
    "ai_models/yolo_inference.py",
    "ai_models/quality_check/detector.py",
    "app/integrations/gemini_vision_quality.py",
    "app/integrations/apifarmer_client.py",
    "app/integrations/twelvedata_client.py",
    "app/integrations/vietnam_retail_price_client.py",
    "app/integrations/thitruongnongsan_client.py",
    "app/integrations/base_market_client.py",
]


@pytest.mark.parametrize("relative", DEAD_FILES)
def test_dead_module_removed(relative):
    assert not (BACKEND / relative).exists(), f"{relative} vẫn còn"


def test_app_still_imports():
    """Xoá xong app phải vẫn nạp được — bắt import gãy."""
    importlib.import_module("app.main")


def test_no_random_price_generation_left():
    """Không còn chỗ nào sinh giá ngẫu nhiên."""
    offenders = []
    for path in (BACKEND / "ai_models").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "random.uniform" in text or "np.random" in text:
            offenders.append(path.relative_to(BACKEND).as_posix())
    assert not offenders, f"Còn sinh số ngẫu nhiên: {offenders}"
