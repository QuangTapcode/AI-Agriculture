"""
TDD: HSV sanity check — "quả tươi không thể là hỏng".

If HSV freshness is high (vibrant color, few dark spots),
the model cannot correctly classify it as "damaged".
This is domain knowledge, not a model fix.
"""
from ai_models.fruit_quality_pipeline import apply_hsv_sanity


# ── Tươi + model nói Hỏng → override Loại 2 ──────────────────────────────

def test_fresh_color_overrides_damaged():
    """HSV tươi 0.75 + grade=damaged → Loại 2 (override)."""
    result = apply_hsv_sanity(grade="damaged", hsv_freshness=0.75, defect_ratio=0.02)
    assert result == "grade_2", f"Expected grade_2, got {result}"


def test_moderately_fresh_overrides_damaged():
    """HSV tươi 0.65 + grade=damaged → Loại 2."""
    result = apply_hsv_sanity(grade="damaged", hsv_freshness=0.65, defect_ratio=0.05)
    assert result == "grade_2"


# ── Thực sự hỏng → giữ nguyên ─────────────────────────────────────────────

def test_dark_image_keeps_damaged():
    """HSV tối 0.2 + nhiều vùng tối → giữ damaged."""
    result = apply_hsv_sanity(grade="damaged", hsv_freshness=0.20, defect_ratio=0.45)
    assert result == "damaged"


def test_high_defect_ratio_keeps_damaged():
    """Defect ratio cao 0.35 → giữ damaged dù freshness OK."""
    result = apply_hsv_sanity(grade="damaged", hsv_freshness=0.60, defect_ratio=0.35)
    assert result == "damaged"


# ── Non-damaged grades không bị đụng ──────────────────────────────────────

def test_grade1_unchanged():
    assert apply_hsv_sanity("grade_1", 0.80, 0.01) == "grade_1"

def test_grade2_unchanged():
    assert apply_hsv_sanity("grade_2", 0.55, 0.10) == "grade_2"

def test_grade3_unchanged():
    assert apply_hsv_sanity("grade_3", 0.40, 0.20) == "grade_3"


# ── Biên giới ──────────────────────────────────────────────────────────────

def test_boundary_exactly_at_threshold():
    """Ngưỡng: freshness >= 0.60 AND defect_ratio <= 0.25 → override."""
    assert apply_hsv_sanity("damaged", 0.60, 0.25) == "grade_2"
    assert apply_hsv_sanity("damaged", 0.59, 0.25) == "damaged"   # just below threshold
    assert apply_hsv_sanity("damaged", 0.60, 0.26) == "damaged"   # defect too high
