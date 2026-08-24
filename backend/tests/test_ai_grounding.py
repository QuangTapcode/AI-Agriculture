"""
TDD: model local chỉ được diễn đạt số liệu có sẵn, không tự tính, không bịa.

Đo thực tế với qwen2.5:3b khi để nó tự do:
  - Sai phép tính tiền: "2 * 1000 * 96.433 = 1928660" (đúng: 192.866.000)
  - Bịa dữ kiện: "Nhu cầu hiện tại thấp hơn" — không ai cung cấp thông tin đó
  - Khuyên ngược chiều dữ liệu: giá giảm nhưng nói "giá có thể tăng"

Không phải lỗi chọn model — LLM nào cũng tính sai tiền. Cách đúng: backend
tính sẵn mọi con số, LLM chỉ viết thành câu.
"""
from app.integrations.ai_grounding import SYSTEM_RULES, build_grounded_prompt


def test_quy_tac_cam_bia_so_lieu():
    rules = SYSTEM_RULES.lower()
    assert "không" in rules and ("bịa" in rules or "tự tính" in rules), (
        "System prompt không cấm bịa/tự tính"
    )


def test_quy_tac_bat_noi_that_khi_thieu_du_lieu():
    assert "chưa có dữ liệu" in SYSTEM_RULES.lower(), (
        "Không hướng dẫn model thừa nhận khi thiếu dữ liệu"
    )


def test_so_lieu_duoc_dinh_dang_san_khong_bat_model_tinh():
    prompt = build_grounded_prompt(
        cau_hoi="Tôi nên bán ngay hay đợi?",
        so_lieu={
            "Giá hôm nay": "96.433 đ/kg",
            "Thành tiền 2 tấn": "192.866.000 đ",
        },
    )
    assert "192.866.000 đ" in prompt, "Số đã tính sẵn không có trong prompt"
    assert "Tôi nên bán ngay hay đợi?" in prompt


def test_thieu_so_lieu_thi_noi_ro_trong_prompt():
    """Không có dữ liệu thì prompt phải nói rõ, tránh model tự lấp chỗ trống."""
    prompt = build_grounded_prompt(cau_hoi="Giá tiêu hôm nay?", so_lieu={})
    assert "chưa có dữ liệu" in prompt.lower()


def test_khong_kem_so_lieu_thua():
    """Chỉ đưa đúng số liệu được cấp — thừa dữ liệu dễ khiến model lẫn."""
    prompt = build_grounded_prompt("Giá cà phê?", {"Giá hôm nay": "96.433 đ/kg"})
    assert "98.200" not in prompt


def test_bat_buoc_chi_tra_loi_tieng_viet():
    """Qwen là model Trung Quốc, có lúc rò ký tự Hán vào câu tiếng Việt.

    Quan sát thật: "chống chịu được bệnh害及虫害" — nông dân không đọc được.
    """
    assert "tiếng việt" in SYSTEM_RULES.lower()
    assert "hán" in SYSTEM_RULES.lower() or "trung" in SYSTEM_RULES.lower(), (
        "Chưa cấm rõ ký tự Hán — chỉ nói 'tiếng Việt' là không đủ với Qwen"
    )


def test_client_dung_system_rules_khi_tu_van():
    """get_farming_advice phải gửi kèm SYSTEM_RULES, không để model tự do."""
    import json
    import httpx
    import asyncio
    from app.integrations.ollama_client import OllamaClient

    nhan = {}

    def handler(request):
        nhan["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    client = OllamaClient(transport=httpx.MockTransport(handler))
    asyncio.run(client.get_farming_advice("Trồng cà chua thế nào?"))

    roles = [m["role"] for m in nhan["body"]["messages"]]
    assert "system" in roles, "Không gửi system prompt — model sẽ bịa tự do"
