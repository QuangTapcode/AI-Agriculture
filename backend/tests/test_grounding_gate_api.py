"""
TDD: cổng grounding phải chặn TRƯỚC khi model được gọi, không phải sau.

Kiểm tra ở tầng hàm thuần là chưa đủ: chỗ rò rỉ nằm ở endpoint, nơi
general_question và quality_analysis đi thẳng xuống LLM khi kho tài liệu
không khớp. Test này dựng client giả, và mọi lần gọi model đều bị ghi nhận —
nếu model bị gọi trong ca thiếu nguồn thì test đổ.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user, get_optional_current_user
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app


class ModelDaBiGoi(AssertionError):
    pass


@pytest.fixture
def api(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = SimpleNamespace(UserID=2001, Region=None)
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_optional_current_user] = lambda: user
    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    # Context thật gọi ra API thời tiết/giá bên ngoài — test sẽ chập chờn theo
    # mạng. Trả sẵn một context CÓ số liệu thời tiết: đó chính là ca đáng lo,
    # vì số liệu đo được không được phép mở khoá cho model tự kê thuốc.
    monkeypatch.setattr(
        "app.api.ai_chat.ai_context_service.build_ai_context",
        lambda db, **kwargs: {
            "intent": kwargs.get("intent"),
            "region": kwargs.get("region"),
            "crop_name": kwargs.get("crop"),
            "weather": {"temperature": 31.2, "humidity": 78},
            "data_sources": [],
        },
    )
    yield TestClient(app), db, monkeypatch
    app.dependency_overrides = original
    db.close()
    engine.dispose()


def _chan_moi_cuoc_goi_model(monkeypatch):
    """Model nào bị gọi cũng làm test đổ ngay tại chỗ gọi."""
    class ClientCam:
        model = "khong-duoc-goi"

        def complete(self, *args, **kwargs):
            raise ModelDaBiGoi("model bị gọi dù không có nguồn")

    monkeypatch.setattr("app.api.ai_chat.get_ai_client", lambda: ClientCam())


def _rag_tra_ve(monkeypatch, payload):
    monkeypatch.setattr("app.api.ai_chat.rag_service.retrieve",
                        lambda *args, **kwargs: payload)


def test_cau_hoi_sau_benh_khong_co_nguon_thi_khong_goi_model(api):
    client, _db, monkeypatch = api
    _chan_moi_cuoc_goi_model(monkeypatch)
    _rag_tra_ve(monkeypatch, {"status": "no_match", "sources": []})

    r = client.post("/api/ai-chat/message",
                    json={"message": "Cà chua bị đốm lá nên phun thuốc gì?"})

    assert r.status_code == 200
    reply = r.json()["data"]["reply"]
    assert "chưa đủ dữ liệu" in reply.lower()


def test_cau_hoi_chung_ve_nong_nghiep_khong_co_nguon_cung_bi_chan(api):
    """general_question là chỗ mọi câu không khớp từ khoá rơi vào — chỗ hổng lớn nhất."""
    client, _db, monkeypatch = api
    _chan_moi_cuoc_goi_model(monkeypatch)
    _rag_tra_ve(monkeypatch, {"status": "no_match", "sources": []})

    r = client.post("/api/ai-chat/message",
                    json={"message": "Đất phèn thì xử lý ra sao cho hợp lý?"})

    assert r.status_code == 200
    assert "chưa đủ dữ liệu" in r.json()["data"]["reply"].lower()


def test_cau_hoi_ngoai_pham_vi_tu_choi_va_khong_goi_model(api):
    client, _db, monkeypatch = api
    _chan_moi_cuoc_goi_model(monkeypatch)
    _rag_tra_ve(monkeypatch, {"status": "no_match", "sources": []})

    r = client.post("/api/ai-chat/message", json={"message": "Thủ đô nước Pháp là gì?"})

    assert r.status_code == 200
    reply = r.json()["data"]["reply"].lower()
    assert "nông nghiệp" in reply
    assert "paris" not in reply


def test_huong_dan_thue_khong_bi_nhan_nham_la_cau_hoi_kha_nang(api):
    """Từ "hướng dẫn" mô tả yêu cầu, không mặc nhiên hỏi cách dùng trợ lý."""
    client, _db, monkeypatch = api
    _chan_moi_cuoc_goi_model(monkeypatch)
    _rag_tra_ve(monkeypatch, {"status": "no_match", "sources": []})

    r = client.post(
        "/api/ai-chat/message",
        json={"message": "Hướng dẫn kê khai thuế VAT cho doanh nghiệp nhỏ là gì?"},
    )

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["grounding"]["reason"] == "ngoai_pham_vi"
    assert data["model"] == "grounding-gate-scope-v1"


def test_gia_hom_nay_khong_duoc_dung_tai_lieu_cu_thay_du_lieu_hien_tai(api):
    client, _db, monkeypatch = api
    calls = []

    monkeypatch.setattr(
        "app.api.ai_chat.ai_context_service.build_ai_context",
        lambda db, **kwargs: {
            "intent": kwargs.get("intent"),
            "region": kwargs.get("region"),
            "crop_name": kwargs.get("crop"),
            "data_sources": [],
        },
    )
    _rag_tra_ve(monkeypatch, {
        "status": "ready",
        "sources": [{
            "citation": "TL1",
            "name": "Báo cáo cà phê năm 2020",
            "page": 1,
            "excerpt": "Báo cáo mô tả sản xuất cà phê trong năm 2020.",
            "score": 0.91,
        }],
    })

    async def fake_ai(_request, _context):
        calls.append(True)
        return "Giá do model tự đoán.", "test-model"

    monkeypatch.setattr("app.api.ai_chat._chon_provider", lambda: (fake_ai, "ollama"))

    r = client.post(
        "/api/ai-chat/message",
        json={"message": "Giá cà phê hôm nay tại Đắk Lắk là bao nhiêu?"},
    )

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["grounding"]["reason"] == "thieu_nguon"
    assert calls == []


def test_hoi_lieu_thuoc_bi_chan_khi_nguon_chi_noi_bien_phap_phong_tru(api):
    client, _db, monkeypatch = api
    calls = []
    _rag_tra_ve(monkeypatch, {
        "status": "ready",
        "sources": [{
            "citation": "TL1",
            "name": "Quản lý rệp sáp giả hại thanh long",
            "page": 1,
            "excerpt": (
                "Vệ sinh vườn, tỉa cành và dùng sinh vật ký sinh để phòng trừ "
                "rệp sáp giả trên cây thanh long."
            ),
            "score": 0.94,
        }],
    })

    async def fake_ai(_request, _context):
        calls.append(True)
        return "Liều thuốc do model tự đoán.", "test-model"

    monkeypatch.setattr("app.api.ai_chat._chon_provider", lambda: (fake_ai, "ollama"))

    r = client.post(
        "/api/ai-chat/message",
        json={
            "message": (
                "Liều thuốc trừ sâu X cụ thể để diệt rệp sáp giả trên thanh long "
                "là bao nhiêu?"
            )
        },
    )

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["grounding"]["reason"] == "thieu_nguon"
    assert calls == []


def test_du_bao_nang_suat_khong_duoc_neo_bang_du_lieu_thoi_tiet(api):
    client, _db, monkeypatch = api
    calls = []
    _rag_tra_ve(monkeypatch, {
        "status": "ready",
        "sources": [{
            "citation": "TL1",
            "name": "Biện pháp nâng cao năng suất mắc ca",
            "page": 1,
            "excerpt": "Hướng dẫn chăm sóc, bón phân và phòng sâu bệnh cho cây mắc ca.",
            "score": 0.93,
        }],
    })

    async def fake_ai(_request, _context):
        calls.append(True)
        return "Năng suất năm tới do model tự dự báo.", "test-model"

    monkeypatch.setattr("app.api.ai_chat._chon_provider", lambda: (fake_ai, "ollama"))

    r = client.post(
        "/api/ai-chat/message",
        json={
            "message": (
                "Năng suất mắc ca ở Tây Nguyên năm tới sẽ đạt bao nhiêu tấn mỗi hecta?"
            )
        },
    )

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["grounding"]["reason"] == "thieu_nguon"
    assert calls == []


def test_cau_hoi_nho_bi_chan_khi_retrieval_chi_tra_tai_lieu_cay_khac(api):
    client, _db, monkeypatch = api
    _chan_moi_cuoc_goi_model(monkeypatch)
    _rag_tra_ve(monkeypatch, {
        "status": "ready",
        "sources": [{
            "citation": "TL1",
            "name": "Khắc phục cây ăn quả sau bão",
            "page": 1,
            "excerpt": "Nhóm cây ăn quả cần tỉa cành gãy và khơi thông rãnh thoát nước.",
            "crop": "cây trồng",
            "score": 0.81,
        }],
    })

    r = client.post(
        "/api/ai-chat/message",
        json={"message": "Quy trình trồng nho Hạ Đen tại Ninh Thuận trong dataset là gì?"},
    )

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["grounding"]["reason"] == "thieu_nguon"
    assert data["rag"]["sources"] == []


def test_kho_tai_lieu_loi_thi_noi_that_chu_khong_doan(api):
    client, _db, monkeypatch = api
    _chan_moi_cuoc_goi_model(monkeypatch)
    _rag_tra_ve(monkeypatch, {"status": "unavailable", "sources": []})

    r = client.post("/api/ai-chat/message",
                    json={"message": "Cà chua bị đốm lá nên phun thuốc gì?"})

    assert r.status_code == 200
    reply = r.json()["data"]["reply"].lower()
    assert "chưa đủ dữ liệu" in reply
    assert "thử lại" in reply


def test_trang_thai_grounding_duoc_tra_ve_cho_frontend(api):
    """UI cần phân biệt bốn trạng thái để hiển thị đúng, không đoán từ chữ."""
    client, _db, monkeypatch = api
    _chan_moi_cuoc_goi_model(monkeypatch)
    _rag_tra_ve(monkeypatch, {"status": "empty", "sources": []})

    r = client.post("/api/ai-chat/message",
                    json={"message": "Cà chua bị đốm lá nên phun thuốc gì?"})

    data = r.json()["data"]
    assert data["grounding"]["status"] == "empty"
    assert data["grounding"]["reason"] == "thieu_nguon"


def test_co_nguon_thi_model_van_duoc_tra_loi_va_kem_trich_dan(api):
    client, _db, monkeypatch = api
    nguon = [{"citation": "TL1", "document_id": 7, "name": "Quy trình cà chua",
              "page": 3, "chunk": 0, "excerpt": "Đốm lá do nấm Alternaria.",
              "score": 0.91}]
    _rag_tra_ve(monkeypatch, {"status": "ready", "sources": nguon})

    class ClientTra:
        model = "test-model"

        def complete(self, *args, **kwargs):
            return {"answer": "Cắt bỏ lá bệnh và giữ ruộng thông thoáng.",
                    "model": "test-model"}

    monkeypatch.setattr("app.api.ai_chat.get_ai_client", lambda: ClientTra())

    r = client.post("/api/ai-chat/message",
                    json={"message": "Cà chua bị đốm lá nên phun thuốc gì?"})

    assert r.status_code == 200
    reply = r.json()["data"]["reply"]
    assert "Cắt bỏ lá bệnh" in reply
    assert "TL1" in reply and "Quy trình cà chua" in reply


def test_chao_hoi_khong_bi_cong_grounding_chan(api):
    client, _db, monkeypatch = api
    _rag_tra_ve(monkeypatch, {"status": "empty", "sources": []})

    r = client.post("/api/ai-chat/message", json={"message": "Xin chào"})

    assert r.status_code == 200
    assert "chưa đủ dữ liệu" not in r.json()["data"]["reply"].lower()
