"""
Gemini Vision Quality Analyzer
Dùng Gemini multimodal để:
1. Tự nhận diện loại nông sản trong ảnh
2. Đánh giá chất lượng dựa trên màu sắc và khuyết tật thực tế
"""
import json
import logging

logger = logging.getLogger(__name__)

_ANALYZE_PROMPT = """Phân tích ảnh nông sản này. Trả về JSON hợp lệ (KHÔNG có markdown, chỉ JSON thuần):
{
  "detected_crop": "tên nông sản tiếng Việt (ví dụ: cà chua, xoài, chuối, ớt, sầu riêng...), hoặc 'không phải nông sản' nếu ảnh không có nông sản",
  "is_produce": true,
  "color_assessment": "mô tả màu sắc quan sát được (tiếng Việt)",
  "ripeness": "chưa chín / chín đều / chín kỹ / quá chín / hỏng",
  "defects": ["danh sách khuyết tật bằng tiếng Việt, mảng rỗng nếu không có"],
  "quality_grade": "grade_1",
  "confidence": 0.9,
  "reasoning": "giải thích ngắn gọn tại sao phân loại như vậy (tiếng Việt)"
}

Tiêu chí phân loại chất lượng:
- grade_1: màu sắc chín đều, không có khuyết tật rõ ràng, hình dạng tốt → xuất khẩu/siêu thị
- grade_2: màu tương đối tốt, có vài khuyết tật nhỏ (đốm nhỏ, lồi lõm nhẹ) → chợ đầu mối
- grade_3: biến màu rõ, bầm dập, thối, nứt nẻ, nấm mốc → bán nhanh hoặc chế biến

Nếu ảnh KHÔNG chứa nông sản: đặt is_produce=false, detected_crop='không phải nông sản', quality_grade='grade_3', confidence=0.0"""


def _build_contents(image_bytes: bytes, mime_type: str):
    """Build Gemini multimodal contents without hard dependency in tests."""
    try:
        from google.genai import types as _types
        return [
            _types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            _ANALYZE_PROMPT,
        ]
    except Exception:
        # Fallback for environments without google.genai installed.
        # Mock clients used in tests only need a contents payload.
        return [image_bytes, _ANALYZE_PROMPT]


class GeminiVisionAnalyzer:
    def __init__(self, client=None):
        self._client = client  # injectable for testing

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from app.integrations.gemini_client import GeminiClient
            gc = GeminiClient()
            return gc.client
        except Exception as e:
            logger.error(f"[VisionQuality] Không khởi tạo được Gemini client: {e}")
            return None

    def analyze(self, image_bytes: bytes) -> dict:
        client = self._get_client()
        if not client:
            return _fallback_result("AI không khả dụng")

        mime_type = _detect_mime(image_bytes)
        contents = _build_contents(image_bytes, mime_type)

        for model_name in [
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
        ]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )
                text = (response.text or "").strip()
                text = _strip_fences(text)
                return json.loads(text)
            except json.JSONDecodeError:
                logger.warning(f"[Vision/{model_name}] JSON không hợp lệ, chuyển tiếp...")
                continue
            except Exception as e:
                err = str(e)
                if any(k in err for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "quota", "404", "NOT_FOUND")):
                    logger.warning(f"[Vision/{model_name}] {err[:60]}, chuyển tiếp...")
                    continue
                logger.error(f"[Vision/{model_name}] Lỗi không xử lý được: {e}")
                return _fallback_result(str(e))

        return _fallback_result("Tất cả model đều bận")


def _strip_fences(text: str) -> str:
    """Xóa markdown code fences nếu có."""
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] = "json\n{...}", parts[1] after first newline = actual json
        inner = parts[1] if len(parts) > 1 else text
        if inner.startswith("json"):
            inner = inner[4:]
        return inner.strip()
    return text


def _detect_mime(image_bytes: bytes) -> str:
    if image_bytes[:2] == b'\xff\xd8':
        return "image/jpeg"
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if image_bytes[:4] == b'RIFF':
        return "image/webp"
    return "image/jpeg"


def _fallback_result(reason: str = "") -> dict:
    return {
        "detected_crop": "không xác định",
        "is_produce": False,
        "color_assessment": reason or "Không thể phân tích ảnh",
        "ripeness": "unknown",
        "defects": [],
        "quality_grade": "grade_2",
        "confidence": 0.0,
        "reasoning": reason or "AI không thể phân tích ảnh này",
    }
