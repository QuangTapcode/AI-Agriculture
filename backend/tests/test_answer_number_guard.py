"""
TDD: chặn con số không có trong dữ liệu lọt vào câu trả lời.

Đo thực tế với qwen2.5:3b — ràng buộc bằng prompt KHÔNG đủ:

  Lượt trước: "Cà phê Đắk Lắk 96.433 đ/kg"
  Hỏi:        "Còn Gia Lai thì sao?"
  Trả lời:    "Giá cà phê tại Gia Lai hôm nay cũng là 96.433 đ/kg"   <-- bịa

Đã thêm quy tắc cấm suy số liệu vào SYSTEM_RULES, model vẫn vi phạm. Model
nhỏ không tuân thủ lệnh cấm một cách đáng tin — phải chặn ở tầng code.

Nguyên tắc: mọi con số dạng GIÁ trong câu trả lời phải xuất hiện trong phần
dữ liệu đưa vào. Không có thì câu trả lời không đáng tin.
"""
import pytest

from app.integrations.ai_grounding import so_lieu_khong_co_trong_nguon


DU_LIEU = "Cà phê Đắk Lắk: 96.433 đ/kg. Cập nhật 22/08/2026."


def test_phat_hien_gia_bia():
    tra_loi = "Giá cà phê tại Gia Lai hôm nay là 95.200 đ/kg."
    assert so_lieu_khong_co_trong_nguon(tra_loi, DU_LIEU) == ["95.200"]


def test_gia_co_trong_nguon_thi_khong_bao():
    tra_loi = "Cà phê Đắk Lắk đang ở mức 96.433 đ/kg, nên cân nhắc bán."
    assert so_lieu_khong_co_trong_nguon(tra_loi, DU_LIEU) == []


def test_bo_qua_so_nho_khong_phai_gia():
    """"5 ngày", "2 lần", "tháng 10" là diễn đạt bình thường, không phải giá."""
    tra_loi = "Nên tưới 2 lần mỗi ngày, theo dõi trong 5 ngày tới."
    assert so_lieu_khong_co_trong_nguon(tra_loi, DU_LIEU) == []


def test_khong_co_du_lieu_thi_moi_con_so_gia_deu_dang_ngo():
    tra_loi = "Giá khoảng 80.000 đ/kg."
    assert so_lieu_khong_co_trong_nguon(tra_loi, "") == ["80.000"]


def test_chap_nhan_khac_dinh_dang_phan_cach():
    """Nguồn ghi 96.433, model có thể viết 96,433 hoặc 96433 — vẫn là một số."""
    for cach_viet in ("96,433", "96433", "96.433"):
        tra_loi = f"Giá là {cach_viet} đ/kg."
        assert so_lieu_khong_co_trong_nguon(tra_loi, DU_LIEU) == [], cach_viet


# ── Nối vào client: câu trả lời bịa số không được lọt ra ─────────────────

@pytest.mark.asyncio
async def test_client_chan_cau_tra_loi_bia_so():
    """Model bịa giá => trả lời trung thực thay vì đưa số sai cho nông dân."""
    import json

    import httpx

    from app.integrations.ollama_client import OllamaClient

    def handler(request):
        return httpx.Response(200, json={
            "message": {"content": "Giá cà phê tại Gia Lai hôm nay là 95.200 đ/kg."}
        })

    client = OllamaClient(transport=httpx.MockTransport(handler))
    tra_loi = await client.get_farming_advice(
        "Còn Gia Lai thì sao?", context_data="Cà phê Đắk Lắk: 96.433 đ/kg"
    )

    assert "95.200" not in tra_loi, f"Số bịa vẫn lọt ra: {tra_loi!r}"
    assert "chưa có dữ liệu" in tra_loi.lower()


@pytest.mark.asyncio
async def test_client_giu_nguyen_cau_tra_loi_dung():
    """Số khớp nguồn => giữ nguyên, không chặn nhầm."""
    import httpx

    from app.integrations.ollama_client import OllamaClient

    def handler(request):
        return httpx.Response(200, json={
            "message": {"content": "Cà phê Đắk Lắk đang 96.433 đ/kg, nên bán."}
        })

    client = OllamaClient(transport=httpx.MockTransport(handler))
    tra_loi = await client.get_farming_advice(
        "Giá cà phê?", context_data="Cà phê Đắk Lắk: 96.433 đ/kg"
    )

    assert "96.433" in tra_loi
