"""
Weather Pricing Service
Tính toán hệ số điều chỉnh giá dựa trên dự báo thời tiết 7 ngày tới.

Logic:
  Mưa lớn kéo dài → khan hàng → giá TĂNG
  Hạn hán/nóng cực → chất lượng giảm → giá GIẢM
  Thời tiết tốt → giá ổn định
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

# ─── Hệ số tác động thời tiết theo nhóm cây ─────────────────────────────────
# Giá trị dương = giá tăng (khan hàng), âm = giá giảm (chất lượng kém / ế)
_CATEGORY_FACTORS: Dict[str, Dict[str, float]] = {
    "Rau cu": {
        "extreme_rain": +0.25,   # mưa > 40mm/ngày — rau úng, mất mùa cục bộ
        "heavy_rain":   +0.18,   # mưa > 20mm/ngày — vận chuyển khó, khan hàng
        "rainy":        +0.06,   # mưa 10-20mm — ảnh hưởng nhẹ
        "extreme_heat": +0.20,   # nhiệt > 38°C — rau héo nhanh, hao hụt lớn
        "drought":      -0.14,   # khô + nóng > 34°C — rau cháy, chất lượng kém
        "optimal":       0.0,
    },
    "Lua gao": {
        "extreme_rain": +0.15,   # mưa lớn mùa thu hoạch — lúa đổ, khó gặt
        "heavy_rain":   +0.08,
        "rainy":        +0.02,
        "extreme_heat": +0.10,   # lúa lép hạt
        "drought":      -0.08,
        "optimal":       0.0,
    },
    "Trai cay": {
        "extreme_rain": +0.20,   # nứt trái, thối — cung giảm mạnh
        "heavy_rain":   +0.12,
        "rainy":        +0.04,
        "extreme_heat": +0.16,   # trái chin ép, thời gian thu hoạch ngắn
        "drought":      -0.10,   # trái nhỏ, chất lượng giảm
        "optimal":       0.0,
    },
    "Cong nghiep": {
        "extreme_rain": +0.10,
        "heavy_rain":   +0.06,
        "rainy":        +0.02,
        "extreme_heat": +0.08,
        "drought":      -0.10,   # cà phê, hồ tiêu rụng trái non
        "optimal":       0.0,
    },
    "Khac": {
        "extreme_rain": +0.10,
        "heavy_rain":   +0.06,
        "rainy":        +0.02,
        "extreme_heat": +0.08,
        "drought":      -0.06,
        "optimal":       0.0,
    },
}

# Ngưỡng phân loại thời tiết
_EXTREME_RAIN_MM  = 40.0   # mm/ngày
_HEAVY_RAIN_MM    = 20.0
_RAINY_MM         = 10.0
_DROUGHT_MM       = 1.0    # < 1mm coi là không mưa
_EXTREME_HEAT_C   = 38.0
_DROUGHT_HEAT_C   = 34.0   # nóng + không mưa = hạn


def _classify_day(rainfall: Optional[float], temp_max: Optional[float]) -> str:
    rain = rainfall or 0.0
    temp = temp_max or 30.0
    if rain >= _EXTREME_RAIN_MM:
        return "extreme_rain"
    if rain >= _HEAVY_RAIN_MM:
        return "heavy_rain"
    if rain >= _RAINY_MM:
        return "rainy"
    if temp >= _EXTREME_HEAT_C:
        return "extreme_heat"
    if rain < _DROUGHT_MM and temp >= _DROUGHT_HEAT_C:
        return "drought"
    return "optimal"


def get_weather_forecast(
    db: Session,
    region: str,
    days: int = 7,
) -> List[Dict]:
    """Đọc dự báo thời tiết từ WeatherData cho N ngày tới."""
    from app.models.weather import WeatherData

    today = date.today()
    until = today + timedelta(days=days - 1)

    rows = (
        db.query(WeatherData)
        .filter(
            WeatherData.Region == region,
            WeatherData.RecordDate >= today,
            WeatherData.RecordDate <= until,
        )
        .order_by(WeatherData.RecordDate)
        .all()
    )
    return [
        {
            "date":         r.RecordDate.isoformat(),
            "temp_min":     r.TempMin,
            "temp_max":     r.TempMax,
            "humidity":     r.Humidity,
            "rainfall":     r.Rainfall,
            "sunshine_h":   r.SunshineHours,
            "weather_desc": r.WeatherDesc,
            "condition":    _classify_day(r.Rainfall, r.TempMax),
        }
        for r in rows
    ]


def calculate_weather_factor(
    forecast: List[Dict],
    crop_category: str,
) -> Tuple[float, str, str]:
    """
    Tính hệ số điều chỉnh giá từ dự báo thời tiết.

    Returns:
        factor       : hệ số nhân (1.0 = không đổi, 1.15 = tăng 15%, 0.90 = giảm 10%)
        summary      : mô tả ngắn điều kiện thời tiết chung
        explanation  : giải thích tác động đến giá
    """
    if not forecast:
        return 1.0, "Không có dữ liệu thời tiết", "Giá ổn định (không có dữ liệu thời tiết)"

    factors = _CATEGORY_FACTORS.get(crop_category, _CATEGORY_FACTORS["Khac"])

    # Đếm ngày theo điều kiện
    condition_counts: Dict[str, int] = {}
    for day in forecast:
        cond = day.get("condition", "optimal")
        condition_counts[cond] = condition_counts.get(cond, 0) + 1

    n_days = len(forecast)
    avg_rain = sum(d.get("rainfall") or 0 for d in forecast) / n_days
    avg_temp = sum(d.get("temp_max") or 30 for d in forecast) / n_days

    # Tính factor tổng hợp: trung bình có trọng số theo số ngày
    raw_factor = sum(
        factors.get(cond, 0.0) * count / n_days
        for cond, count in condition_counts.items()
    )

    # Cực đoan: ≥ 4 ngày liên tiếp bất lợi → tăng cường tác động
    bad_days = sum(
        condition_counts.get(c, 0)
        for c in ("extreme_rain", "heavy_rain", "extreme_heat", "drought")
    )
    if bad_days >= 4:
        raw_factor *= 1.3  # tăng cường tác động khi thời tiết xấu kéo dài

    # Làm tròn, giới hạn ±30%
    factor = round(max(0.70, min(1.30, 1.0 + raw_factor)), 3)

    # Tóm tắt điều kiện chính
    dominant = max(condition_counts, key=condition_counts.get)
    _condition_vi = {
        "extreme_rain": f"Mưa cực lớn ({avg_rain:.0f}mm/ngày TB)",
        "heavy_rain":   f"Mưa nhiều ({avg_rain:.0f}mm/ngày TB)",
        "rainy":        f"Mưa vừa ({avg_rain:.0f}mm/ngày TB)",
        "extreme_heat": f"Nắng nóng cực độ ({avg_temp:.0f}°C TB)",
        "drought":      f"Hạn hán, khô nóng ({avg_temp:.0f}°C, mưa < 1mm)",
        "optimal":      f"Thời tiết thuận lợi ({avg_temp:.0f}°C, mưa {avg_rain:.0f}mm)",
    }
    summary = _condition_vi.get(dominant, "Thời tiết bình thường")

    # Giải thích tác động.
    #
    # Bản cũ chỉ nhìn DẤU của factor rồi dán nhãn cứng "Thời tiết bất lợi",
    # sau đó nhét `summary` vào giữa ngoặc — mà `summary` mô tả ngày phổ biến
    # nhất. Kết quả là những câu tự cãi nhau:
    #
    #   "Thời tiết bất lợi (thời tiết thuận lợi (30°c, mưa 19mm)) dự kiến
    #    làm giảm nguồn cung, giá có thể tăng ~3.7%"
    #
    # Vừa "bất lợi" vừa "thuận lợi", lại còn "30°c" viết thường vì `.lower()`
    # quét cả đơn vị. Nay mô tả đúng cái đang đo: bao nhiêu ngày trên tổng số
    # là bất lợi, và điều đó đẩy giá về hướng nào.
    pct = round((factor - 1.0) * 100, 1)

    _DIEU_KIEN_XAU = ("extreme_rain", "heavy_rain", "extreme_heat", "drought")
    _TEN_NGAN = {
        "extreme_rain": "mưa cực lớn",
        "heavy_rain": "mưa lớn",
        "rainy": "mưa vừa",
        "extreme_heat": "nắng nóng gay gắt",
        "drought": "khô hạn",
    }
    ngay_xau = bad_days
    xau_nhat = max(
        (c for c in _DIEU_KIEN_XAU if condition_counts.get(c)),
        key=lambda c: condition_counts[c],
        default=None,
    )

    # Dưới 1% là nhiễu làm tròn, không đáng dựng thành câu cảnh báo — trước
    # đây +0.3% cũng bị gọi là "thời tiết bất lợi" dù 6/7 ngày đẹp trời.
    if abs(pct) < 1.0:
        explanation = (
            f"Thời tiết {n_days} ngày tới về cơ bản thuận lợi ({summary}), "
            f"giá **ổn định**."
        )
    elif pct > 0:
        # Mô tả chính điều kiện xấu, không lồng `summary` của ngày đẹp vào —
        # đó là nguồn gốc của những câu "bất lợi (thuận lợi)".
        ly_do = (
            f"{ngay_xau}/{n_days} ngày tới có {_TEN_NGAN.get(xau_nhat, 'thời tiết cực đoan')}"
            if xau_nhat
            else f"Thời tiết {n_days} ngày tới kém thuận lợi cho thu hoạch"
        )
        explanation = (
            f"{ly_do}, dự kiến làm giảm nguồn cung, "
            f"giá có thể **tăng ~{pct}%** so với mức cơ sở."
        )
    else:
        so_ngay_kho = condition_counts.get("drought", 0)
        ly_do = (
            f"{so_ngay_kho}/{n_days} ngày khô hạn"
            if so_ngay_kho
            else f"Điều kiện {n_days} ngày tới"
        )
        explanation = (
            f"{ly_do} có thể làm giảm chất lượng sản phẩm, "
            f"giá dự kiến **giảm ~{abs(pct)}%** so với mức cơ sở."
        )

    return factor, summary, explanation


def get_weather_adjusted_pricing(
    db: Session,
    crop_name: str,
    region: str,
    base_price: float,
    forecast_days: int = 7,
) -> Dict:
    """
    Pipeline đầy đủ: đọc thời tiết → tính factor → trả về giá điều chỉnh.

    Args:
        base_price: giá thị trường hiện tại (VNĐ/kg)

    Returns dict:
        weather_factor       : hệ số (float)
        adjusted_price       : giá sau điều chỉnh
        price_change_pct     : % thay đổi
        weather_summary      : tóm tắt điều kiện
        weather_explanation  : giải thích tác động
        forecast             : danh sách chi tiết từng ngày
    """
    from app.models.crop import CropType

    # Lấy category của cây trồng
    crop = (
        db.query(CropType)
        .filter(CropType.CropName == crop_name)
        .first()
        or db.query(CropType)
        .filter(CropType.CropName.ilike(f"%{crop_name}%"))
        .first()
    )
    category = getattr(crop, "Category", "Khac") if crop else "Khac"

    forecast = get_weather_forecast(db, region, days=forecast_days)
    factor, summary, explanation = calculate_weather_factor(forecast, category)

    adjusted = round(base_price * factor, -2)  # làm tròn 100 VNĐ
    pct = round((factor - 1.0) * 100, 1)

    return {
        "weather_factor":      factor,
        "adjusted_price":      adjusted,
        "base_price":          base_price,
        "price_change_pct":    pct,
        "weather_summary":     summary,
        "weather_explanation": explanation,
        "crop_category":       category,
        "forecast_days":       len(forecast),
        "forecast":            forecast,
    }
