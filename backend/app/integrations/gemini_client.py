import asyncio
import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class AIUnavailableError(RuntimeError):
    """AI chưa cấu hình hoặc không gọi được.

    Ném lỗi thay vì trả chuỗi giả: chuỗi giả đi thẳng vào trường `answer` như
    một câu trả lời bình thường, không cờ nào phân biệt, nên nông dân không
    thể biết đó là bịa (TOD0 §1 cấm dữ liệu giả lọt ra API công khai).
    """
  # noqa

# Tìm và đọc file .env một cách tường minh từ thư mục gốc của dự án (backend)
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)


class GeminiClient:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        # Thêm log gỡ lỗi để kiểm tra trực tiếp trên terminal
        if api_key:
            masked_key = api_key[:7] + '...' + api_key[-4:]
            logger.info(f"GEMINI_API_KEY loaded: {masked_key}")
        else:
            logger.warning("GEMINI_API_KEY not found in environment.")

        if not api_key:
            logger.warning("GEMINI_API_KEY is not set. Gemini AI will not work.")
            self.client = None
        else:
            genai.configure(api_key=api_key)
            self.client = genai
            self.model_fallbacks = [
                'gemini-2.5-flash-lite',  # free tier quota cao, nhanh
                'gemini-2.0-flash-lite',
                'gemini-2.0-flash',
                'gemini-2.5-flash',
                'gemini-3-flash-preview',
                'gemini-3.1-flash-lite',
            ]
            logger.info("Gemini client configured successfully.")

    async def get_price_answer(self, question: str, region: str, context_data: str = "") -> str:
        """Trả lời ngắn gọn về giá nông sản — không lải nhải."""
        if not self.client:
            raise AIUnavailableError(
                "Trợ lý AI chưa được cấu hình (thiếu GEMINI_API_KEY). "
                "Vui lòng liên hệ quản trị viên."
            )

        system_instruction = (
            f"Bạn là hệ thống thông tin giá nông sản tự động tại Việt Nam.\n"
            f"Vùng người dùng quan tâm: {region}.\n"
            "QUY TẮC NGHIÊM NGẶT:\n"
            "- Trả lời TỐI ĐA 12 dòng, KHÔNG có lời dẫn, KHÔNG chào hỏi.\n"
            "- Bắt đầu NGAY bằng số liệu giá cụ thể (VNĐ/kg).\n"
            "- Dùng bảng Markdown hoặc bullet ngắn với số liệu thực.\n"
            "- Ghi rõ tên vùng và ngày của mỗi dòng giá.\n"
            "- Nếu có lịch sử 7 ngày: thêm 1 dòng xu hướng (tăng/giảm/ổn định).\n"
            f"- QUAN TRỌNG: Nếu {region} không có dữ liệu cho loại nông sản được hỏi, "
            "PHẢI hiển thị giá từ mục 'Giá toàn quốc' trong dữ liệu, ghi rõ tên vùng đó. "
            "KHÔNG ĐƯỢC nói 'không có dữ liệu' nếu mục toàn quốc có thông tin.\n"
            "- KHÔNG giải thích nguyên nhân, KHÔNG liệt kê khuyến nghị dài."
        )
        prompt = (
            f"Dữ liệu thực tế:\n{context_data or 'Không có dữ liệu.'}\n\n"
            f"Câu hỏi: {question}\n\n"
            "Trả lời ngắn gọn với số liệu cụ thể."
        )

        for model_name in self.model_fallbacks:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_instruction
                )
                response = await asyncio.wait_for(
                    asyncio.to_thread(model.generate_content, prompt),
                    timeout=settings.AI_TIMEOUT_SECONDS,
                )
                return response.text or ""
            except Exception as e:
                error_msg = str(e)
                if any(k in error_msg for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "quota", "404", "NOT_FOUND")):
                    logger.warning(f"[price/{model_name}] {error_msg[:60]}..., chuyển tiếp...")
                    continue
                return f"Lỗi AI: {error_msg}"

        return "Xin lỗi, hệ thống AI đang bận. Vui lòng thử lại sau ít phút."

    _TOPIC_PROMPTS: dict = {
        "price": (
            "Bạn là hệ thống thông tin giá nông sản tự động tại Việt Nam.\n"
            "QUY TẮC: Tối đa 12 dòng. Bắt đầu NGAY bằng số liệu. Không chào hỏi.\n"
            "Nếu vùng được hỏi không có dữ liệu, dùng dữ liệu vùng khác gần nhất. KHÔNG nói 'không có dữ liệu'."
        ),
        "weather": (
            "Bạn là chuyên gia khí tượng nông nghiệp Việt Nam.\n"
            "QUY TẮC: Tối đa 15 dòng. Ưu tiên cảnh báo nguy hiểm lên đầu. Ghi rõ vùng và ngày dự báo.\n"
            "Đưa ra khuyến cáo CỤ THỂ cho nông dân: tránh trú bão, thu hoạch sớm, điều chỉnh tưới tiêu.\n"
            "Phân tích tác động thời tiết lên cây trồng phổ biến tại vùng đó."
        ),
        "soil_salinity": (
            "Bạn là chuyên gia đất đai nông nghiệp, chuyên về đất mặn và xâm nhập mặn ĐBSCL.\n"
            "QUY TẮC: Tối đa 15 dòng. Đưa ra giải pháp THỰC TẾ với liều lượng và thời gian cụ thể.\n"
            "Ưu tiên giải pháp tiết kiệm chi phí. Gợi ý giống cây chịu mặn phù hợp."
        ),
        "soil_acidity": (
            "Bạn là chuyên gia đất đai nông nghiệp, chuyên về đất phèn ĐBSCL.\n"
            "QUY TẮC: Tối đa 15 dòng. Đưa ra quy trình CẢI TẠO cụ thể: liều lượng vôi, thời gian xả phèn.\n"
            "Gợi ý phân bón phù hợp đất phèn và cây trồng thích nghi."
        ),
        "pest": (
            "Bạn là chuyên gia bảo vệ thực vật Việt Nam.\n"
            "QUY TẮC: Tối đa 15 dòng. Cấu trúc: Chẩn đoán → Nguyên nhân → Giải pháp IPM → Phòng ngừa.\n"
            "Ghi tên hoạt chất thuốc và liều lượng cụ thể. Ưu tiên phòng trừ sinh học."
        ),
        "cultivation": (
            "Bạn là kỹ sư nông nghiệp tư vấn trồng trọt tại Việt Nam.\n"
            "QUY TẮC: Tối đa 15 dòng. Cung cấp quy trình CỤ THỂ: mật độ gieo trồng, lượng phân, thời điểm.\n"
            "Điều chỉnh khuyến cáo theo vùng và mùa vụ nếu có thông tin."
        ),
        "general": (
            "Bạn là chuyên gia nông nghiệp tư vấn toàn diện tại Việt Nam.\n"
            "QUY TẮC: Tối đa 15 dòng. Trả lời THỰC CHẤT với số liệu cụ thể. Không chào hỏi. Không giải thích dài dòng.\n"
            "Ưu tiên thông tin thực tiễn, có thể áp dụng ngay."
        ),
    }

    async def get_agri_answer(self, question: str, topic: str = "general", region: str = "", context_data: str = "") -> str:
        """Trả lời nông nghiệp với system prompt phù hợp theo chủ đề."""
        if not self.client:
            raise AIUnavailableError(
                "Trợ lý AI chưa được cấu hình (thiếu GEMINI_API_KEY). "
                "Vui lòng liên hệ quản trị viên."
            )

        sys_prompt = self._TOPIC_PROMPTS.get(topic, self._TOPIC_PROMPTS["general"])
        if region:
            sys_prompt += f"\nVùng người dùng quan tâm: {region}."

        prompt = (
            f"Dữ liệu thực tế:\n{context_data or 'Không có dữ liệu.'}\n\n"
            f"Câu hỏi: {question}\n\nTrả lời ngắn gọn, cụ thể:"
        )

        for model_name in self.model_fallbacks:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=sys_prompt
                )
                response = await asyncio.wait_for(
                    asyncio.to_thread(model.generate_content, prompt),
                    timeout=settings.AI_TIMEOUT_SECONDS,
                )
                return response.text or ""
            except Exception as e:
                error_msg = str(e)
                if any(k in error_msg for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "quota", "404", "NOT_FOUND")):
                    logger.warning(f"[agri/{topic}/{model_name}] {error_msg[:60]}..., chuyển tiếp...")
                    continue
                return f"Lỗi AI: {error_msg}"

        return "Xin lỗi, hệ thống AI đang bận. Vui lòng thử lại sau ít phút."

    async def get_farming_advice(self, question: str, context_data: str = "") -> str:
        if not self.client:
            raise AIUnavailableError(
                "Trợ lý AI chưa được cấu hình (thiếu GEMINI_API_KEY). "
                "Vui lòng liên hệ quản trị viên."
            )

        system_instruction = """Bạn là chuyên gia nông nghiệp hàng đầu Việt Nam với 20 năm kinh nghiệm thực tiễn,
am hiểu sâu về: kỹ thuật canh tác, sinh lý cây trồng, bảo vệ thực vật, thổ nhưỡng, thủy lợi,
thị trường nông sản và chính sách nông nghiệp Việt Nam.

NGUYÊN TẮC TRẢ LỜI:
1. Dựa trên dữ liệu hệ thống được cung cấp để trả lời chính xác nhất có thể.
2. Trả lời CỤ THỂ cho vùng/địa phương được hỏi (nếu có), không trả lời chung chung.
3. Cung cấp số liệu kỹ thuật chính xác: liều lượng phân bón, nồng độ thuốc, thời điểm xử lý.
4. Phân tích NGUYÊN NHÂN sâu xa của vấn đề, không chỉ mô tả triệu chứng.
5. Đưa ra GIẢI PHÁP CỤ THỂ, có thể thực hiện ngay được, theo thứ tự ưu tiên.
6. Cảnh báo RỦI RO và sai lầm phổ biến liên quan đến câu hỏi.
7. Kết thúc bằng 1-2 câu khuyến nghị hành động ngay cho nông dân.

ĐỊNH DẠNG: Sử dụng tiêu đề rõ ràng, bullet points khi liệt kê, in đậm các thông tin quan trọng."""

        prompt = f"""--- DỮ LIỆU HỆ THỐNG (ngữ cảnh) ---
{context_data if context_data else "Không có dữ liệu bổ sung."}

--- CÂU HỎI CỦA NÔNG DÂN ---
{question}

--- YÊU CẦU ---
Hãy phân tích kỹ và trả lời đầy đủ, chuyên sâu dựa trên dữ liệu bên trên. Nếu câu hỏi liên quan đến:
- Giá cả/thị trường: Phân tích giá trong dữ liệu, so sánh xu hướng, dự báo ngắn hạn.
- Kỹ thuật trồng trọt: Đưa quy trình đầy đủ, thông số kỹ thuật cụ thể.
- Bệnh/sâu hại: Mô tả triệu chứng, nguyên nhân, biện pháp phòng trừ tổng hợp (IPM).
- Thời điểm thu hoạch: Xác định đúng giai đoạn chín, dấu hiệu nhận biết cụ thể."""

        for model_name in self.model_fallbacks:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_instruction
                )
                response = await asyncio.wait_for(
                    asyncio.to_thread(model.generate_content, prompt),
                    timeout=settings.AI_TIMEOUT_SECONDS,
                )
                if model_name != self.model_fallbacks[0]:
                    logger.info(f"Dùng model fallback thành công: {model_name}")
                return response.text or ""
            except Exception as e:
                error_msg = str(e)
                is_quota   = "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower()
                is_overload = "503" in error_msg or "UNAVAILABLE" in error_msg or "high demand" in error_msg
                is_not_found = "404" in error_msg or "NOT_FOUND" in error_msg
                if is_quota or is_overload or is_not_found:
                    logger.warning(f"[{model_name}] không khả dụng ({error_msg[:60]}...), chuyển tiếp...")
                    continue
                else:
                    logger.error(f"Gemini API lỗi không xử lý được ({model_name}): {e}")
                    return f"Lỗi từ Gemini API: {error_msg}"

        # Tất cả Gemini model đều quá tải → thử Claude fallback
        try:
            from app.integrations.claude_client import ClaudeClient
            claude = ClaudeClient()
            if claude.client:
                logger.info("Gemini quá tải, chuyển sang Claude fallback...")
                return await claude.get_farming_advice(question, context_data)
        except Exception as e:
            logger.error(f"Claude fallback cũng lỗi: {e}")

        return "Xin lỗi, hệ thống AI đang bận. Vui lòng thử lại sau ít phút."
