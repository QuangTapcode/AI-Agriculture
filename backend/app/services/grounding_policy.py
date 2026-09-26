"""
Cổng grounding: quyết định khi nào trợ lý được phép gọi model, khi nào phải
nói thẳng "chưa đủ dữ liệu".

Vì sao cần một cổng duy nhất: trước đây mỗi intent tự xử lý thiếu nguồn theo
cách riêng (chăn nuôi có câu trả lời riêng, kỹ thuật canh tác có câu khác, số
còn lại không kiểm tra gì cả). Câu hỏi không khớp từ khoá nào rơi vào
general_question và đi thẳng xuống model — chỗ hổng lớn nhất lại là chỗ không
ai canh.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.ai_intent_service import extract_crop_from_message, normalize_user_text

TRANG_THAI_HOP_LE = ("ready", "no_match", "empty", "unavailable")

# Vì sao model bị chặn: "ready" (không chặn), "thieu_nguon" (nông nghiệp
# nhưng kho không có nguồn khớp), "ngoai_pham_vi" (không phải câu hỏi nông
# nghiệp). Hai lý do sau dẫn tới hai câu trả lời khác hẳn nhau.
LY_DO_HOP_LE = ("ready", "thieu_nguon", "ngoai_pham_vi")


@dataclass(frozen=True)
class QuyetDinhGrounding:
    """Kết quả xét grounding cho một câu hỏi."""

    trang_thai: str
    duoc_goi_model: bool
    cau_tra_loi: str
    ly_do: str = "ready"


def chuan_hoa_trang_thai(rag: object) -> str:
    """Quy mọi payload RAG về đúng một trong bốn trạng thái hợp lệ.

    Nhãn đi kèm payload không đủ tin: rag_service có thể trả "ready" trong khi
    sources rỗng, hoặc một nhánh lỗi làm context["rag"] không bao giờ được
    gán. Trạng thái phải suy ra từ thứ thực sự cầm trên tay — có nguồn hay
    không — chứ không phải từ nhãn.
    """
    if not isinstance(rag, dict):
        return "unavailable"
    co_nguon = bool(rag.get("sources"))
    nhan = rag.get("status")
    if nhan not in TRANG_THAI_HOP_LE:
        return "ready" if co_nguon else "unavailable"
    if nhan == "ready" and not co_nguon:
        return "no_match"
    return nhan


_LY_DO_THIEU_NGUON = {
    "no_match": (
        "Kho tài liệu có nội dung nhưng không khớp câu hỏi này, nên tôi chưa "
        "đủ dữ liệu để trả lời.\n\n"
        "Bạn thử nêu rõ cây trồng, giai đoạn và khu vực để lần tra cứu sau "
        "bám sát hơn. Hệ thống cũng đã ghi nhận chủ đề này để đi tìm nguồn."
    ),
    "empty": (
        "Kho tài liệu hiện chưa có tài liệu nào để đối chiếu, nên tôi chưa đủ "
        "dữ liệu để trả lời.\n\n"
        "Bạn hoặc quản trị viên cần nạp tài liệu kỹ thuật vào kho trước, sau "
        "đó hỏi lại để tôi trả lời kèm trích dẫn."
    ),
    # Gộp cả hai nguyên nhân: kho lỗi, và kho bị tắt bằng cấu hình
    # (RAG_ENABLED=false). Cả hai đều dẫn tới cùng một sự thật — không tra cứu
    # được — nên không đổ riêng cho "sự cố" khi có thể là lựa chọn vận hành.
    "unavailable": (
        "Hệ thống tra cứu tài liệu hiện không dùng được nên tôi chưa đủ dữ "
        "liệu để trả lời câu hỏi này.\n\n"
        "Bạn thử lại sau ít phút; nếu vẫn vậy, nhờ quản trị viên kiểm tra kho "
        "tài liệu. Tôi không đoán thay phần chưa tra cứu được."
    ),
}

_KHONG_DUA_RA_LOI_KHUYEN = (
    "Chưa có nguồn thì tôi không đưa liều lượng, thuốc hay lịch chăm sóc cụ "
    "thể — sai một con số là nông dân mất cả vụ."
)

_NGOAI_PHAM_VI = (
    "Câu hỏi này nằm ngoài lĩnh vực nông nghiệp nên tôi không trả lời.\n\n"
    "Tôi hỗ trợ giá nông sản, thời tiết canh tác, mùa vụ và thu hoạch, kỹ "
    "thuật canh tác, chăn nuôi, sâu bệnh và chất lượng nông sản."
)

# Dấu hiệu LẠC ĐỀ. Chỉ dùng cho general_question — các intent khác đã khớp từ
# khoá chuyên ngành ngay ở bước phân loại.
#
# Hướng của luật này quan trọng hơn nội dung của nó. Bản trước bắt câu hỏi
# phải chứng minh mình thuộc nông nghiệp bằng cách khớp một danh sách từ khoá.
# Đo thật ba lần, ba câu nhà nông bị trả lời "ngoài lĩnh vực nông nghiệp":
# tôm thẻ chân trắng, chôm chôm ra hoa trái vụ, nho ngón tay. Danh sách nào
# cũng thiếu — tiếng Việt nông nghiệp quá rộng để liệt kê hết.
#
# Hai kiểu hỏng không ngang nhau. Nói với nông dân rằng câu hỏi nhà nông của
# họ lạc đề là hỏng nặng; trả "chưa đủ dữ liệu" cho một câu lạc đề thật chỉ
# là trả lời hơi lệch. Trợ lý này lại chỉ làm nông nghiệp, nên mặc định đúng
# là coi mọi câu là nông nghiệp và bắt phía lạc đề phải có bằng chứng.
_TU_KHOA_LAC_DE = (
    # Hành chính, tài chính
    "thuế", "vat", "hóa đơn", "kê khai", "bảo hiểm xã hội", "hộ chiếu",
    "căn cước", "chứng khoán", "bitcoin", "tiền ảo", "lãi suất ngân hàng",
    # Công nghệ, lập trình
    "code", "python", "javascript", "lập trình", "phần mềm", "cài win",
    "điện thoại", "laptop", "wifi", "mật khẩu",
    # Giải trí, thể thao, đời sống chung
    "bóng đá", "trận đấu", "tỷ số", "phim", "ca sĩ", "diễn viên", "game",
    "du lịch", "khách sạn", "vé máy bay",
    # Kiến thức phổ thông ngoài ngành
    "thủ đô", "dân số", "lịch sử thế giới", "dịch câu", "toán lớp",
)

# Giữ lại làm lớp khẳng định: câu có dấu hiệu lạc đề NHƯNG cũng có từ khoá
# nông nghiệp thì vẫn thuộc phạm vi — ví dụ "thuế phí xuất khẩu cà phê".
_TU_KHOA_NONG_NGHIEP = (
    # Nghề và nơi sản xuất
    "nong nghiep", "nong san", "nong dan", "nha nong", "trang trai", "nong trai",
    "khuyen nong", "ruong", "vuon", "nuong ray", "thuy loi", "tho nhuong",
    # Trồng trọt
    "cay trong", "canh tac", "gieo trong", "gieo sa", "xuong giong", "hat giong",
    "cay giong", "giong cay", "uom cay", "mat do trong", "khoang cach trong",
    "thu hoach", "mua vu", "vu mua", "vu he thu", "vu dong xuan", "sau thu hoach",
    "bao quan nong san", "sinh truong",
    # Đất và dinh dưỡng
    "dat trong", "dat phen", "dat man", "dat chua", "dat bac mau", "cai tao dat",
    "phen chua", "do ph", "phan bon", "bon phan", "phan dam", "phan lan",
    "phan kali", "npk", "phan chuong", "phan huu co", "voi bot",
    "tuoi tieu", "tuoi nuoc", "he thong tuoi", "thoat nuoc",
    # Sâu bệnh
    "sau benh", "sau hai", "dich hai", "nam benh", "dom la", "vang la",
    "ray nau", "dao on", "thuoc tru sau", "thuoc bao ve thuc vat", "bvtv",
    # Chăn nuôi
    "chan nuoi", "vat nuoi", "gia suc", "gia cam", "chuong trai", "thu y",
    "thuc an chan nuoi", "khau phan an", "nuoi lon", "nuoi heo", "nuoi ga",
    "nuoi vit", "nuoi bo", "nuoi de", "nuoi ong", "nuoi tom", "nuoi ca",
    # Cây trồng có tên đủ dài để không nhầm
    "lua", "ngo", "mia", "ca phe", "cao su", "ho tieu", "sau rieng",
    "thanh long", "ca chua", "dua hau", "khoai lang", "khoai mi", "khoai tay",
    "ca tra", "ca basa", "thuy san", "rau mau", "hat dieu",
)


# Câu hỏi kê đơn: thuốc gì, liều bao nhiêu, trị bệnh thế nào. Số liệu đo được
# (giá, thời tiết) không chứng minh được những điều này, nên dù backend có số
# liệu thì vẫn phải có tài liệu mới được trả lời.
_TU_KHOA_KE_DON = (
    "thuoc gi", "thuoc nao", "phun thuoc", "xit thuoc", "thuoc tru sau",
    "thuoc bao ve thuc vat", "hoat chat", "lieu luong", "lieu bao nhieu",
    "bao nhieu kg", "bao nhieu lit", "bao nhieu gam", "bao nhieu ml",
    "bon bao nhieu", "bon gi", "phan gi", "phan nao", "tri benh", "chua benh",
    "dac tri", "khang sinh", "tiem gi", "vacxin", "vac xin", "khau phan",
    "cho an bao nhieu", "pha ty le", "ty le pha", "cach tri", "cach chua",
)


def _la_cau_hoi_ke_don(cau_hoi: str) -> bool:
    text = normalize_user_text(cau_hoi)
    return any(tu in text for tu in _TU_KHOA_KE_DON)


def _la_cau_hoi_lieu_luong(cau_hoi: str) -> bool:
    text = normalize_user_text(cau_hoi)
    return (
        "lieu luong" in text
        or ("lieu" in text and "bao nhieu" in text)
        or any(
            cum in text
            for cum in (
                "bao nhieu kg", "bao nhieu lit", "bao nhieu gam", "bao nhieu ml",
                "pha ty le", "ty le pha", "nong do bao nhieu",
            )
        )
    )


_MAU_LIEU_LUONG = re.compile(
    r"(?<!\w)\d+(?:[.,]\d+)?\s*(?:ml|l|lit|lít|g|gam|kg|mg|%)(?!\w)",
    re.IGNORECASE,
)


def _nguon_co_lieu_luong(rag: dict | None) -> bool:
    if not isinstance(rag, dict):
        return False
    van_ban = " ".join(
        str(nguon.get(khoa) or "")
        for nguon in (rag.get("sources") or [])
        for khoa in ("name", "source_name", "excerpt")
        if isinstance(nguon, dict)
    )
    text = normalize_user_text(van_ban)
    return (
        "lieu luong" in text
        or "nong do" in text
        or "ty le pha" in text
        or bool(re.search(
            r"(?:thuốc|hoạt chất|phun|pha).{0,80}" + _MAU_LIEU_LUONG.pattern,
            van_ban,
            re.IGNORECASE,
        ))
    )


# Từ khoá còn dấu. Dấu tiếng Việt chính là thứ phân biệt "trồng" với "trong",
# "đấu" với "đậu" — bỏ dấu đi rồi mới so khớp là tự tay vứt thông tin đó. Với
# người gõ đủ dấu (phần lớn, vì giao diện tiếng Việt), lớp này bắt đúng hơn
# hẳn; người gõ không dấu vẫn còn lớp không dấu ở trên đỡ.
_TU_KHOA_CO_DAU = (
    "trồng", "gieo", "bón", "tưới", "giống cây", "hạt giống", "thu hoạch",
    "mùa vụ", "vụ đông", "vụ hè", "sâu bệnh", "phân bón", "nhà màng",
    "nhà kính", "nhà lưới", "thủy canh", "chăn nuôi", "vật nuôi", "nuôi",
    "đất", "cây", "nông", "ruộng", "vườn", "lúa", "rau", "ao nuôi", "thủy sản",
    # Tên con vật: còn dấu thì không nhầm với gì cả ("cá" khác "ca", "bò"
    # khác "bo"). Bỏ chúng ra khỏi danh sách đồng nghĩa với việc nói với
    # người nuôi tôm rằng câu hỏi của họ không thuộc nông nghiệp.
    "tôm", "cá", "gà", "vịt", "lợn", "heo", "bò", "trâu", "dê", "ngan",
    "ong", "tằm", "ếch", "lươn", "cua", "nghêu", "sò", "hàu",
)


def _thuoc_pham_vi_nong_nghiep(cau_hoi: str, crop: str | None) -> bool:
    """Câu hỏi có thuộc phạm vi trợ lý không. Mặc định là CÓ.

    Chỉ trả False khi có dấu hiệu lạc đề rõ ràng và không có dấu hiệu nông
    nghiệp nào để cân lại.
    """
    if crop:
        return True
    co_dau = (cau_hoi or "").lower()
    if not any(re.search(rf"\b{re.escape(tu)}\b", co_dau) for tu in _TU_KHOA_LAC_DE):
        return True
    # Có dấu hiệu lạc đề — chỉ giữ lại nếu câu cũng nói về nông nghiệp
    # ("thuế xuất khẩu cà phê" thuộc phạm vi, "kê khai thuế VAT" thì không).
    if any(
        re.search(rf"\b{re.escape(tu)}\b", co_dau)
        for tu in _TU_KHOA_CO_DAU
    ):
        return True
    text = normalize_user_text(cau_hoi)
    if any(
        re.search(rf"(?<![a-z0-9]){re.escape(tu)}(?![a-z0-9])", text)
        for tu in _TU_KHOA_NONG_NGHIEP
    ):
        return True
    # Danh sách từ khoá ở trên cố tình hẹp để không nhận nhầm. Chỗ nó bỏ sót
    # là câu chỉ nhận ra được nhờ TÊN CÂY: "trồng nho ngón tay ở Ninh Thuận
    # để khoảng cách bao nhiêu mét?" không chứa từ khoá nào trong danh sách.
    # Hệ thống đã có bộ nhận tên cây dùng chung — hỏi nó thay vì chép thêm
    # một danh sách cây thứ hai vào đây rồi để hai bên lệch nhau.
    return bool(extract_crop_from_message(cau_hoi))


# Các intent không khẳng định điều gì về nông nghiệp nên không cần nguồn.
INTENT_KHONG_CAN_NGUON = frozenset({"greeting", "capability_question"})

# Các intent mà nguồn chính là số liệu đo được trong DB (giá, thời tiết, lịch
# mùa vụ), không phải tài liệu kỹ thuật. Số liệu chỉ neo được đúng loại câu
# hỏi mà nó đo — có giá cà phê không cho phép kê thuốc trị rệp sáp.
INTENT_NEO_BANG_SO_LIEU = frozenset({
    "price_analysis",
    "weather_analysis",
    "harvest_analysis",
    "alert_analysis",
    "full_farm_analysis",
})


# Các nhánh context chứa số liệu đo được, không phải văn bản tham khảo.
_KHOA_SO_LIEU = (
    "pricing", "price_history", "price_forecast", "market_analysis",
    "weather", "weather_forecast", "weather_risk",
    "harvest_status", "alerts", "quality_history",
)

_KHOA_SO_LIEU_THEO_INTENT = {
    "price_analysis": ("pricing", "price_history", "price_forecast"),
    "weather_analysis": ("weather", "weather_forecast", "weather_risk"),
    "harvest_analysis": ("harvest_status",),
    "alert_analysis": ("alerts", "weather_risk"),
    "quality_analysis": ("quality_history",),
    "full_farm_analysis": _KHOA_SO_LIEU,
}


def _la_mock(gia_tri: object) -> bool:
    if not isinstance(gia_tri, dict):
        return False
    return bool(gia_tri.get("is_mock")) or gia_tri.get("source_type") == "mock"


def co_du_lieu_so(context: dict | None, intent: str | None = None) -> bool:
    """Backend có số liệu đo được thật cho câu hỏi này hay không.

    Mock không tính. Dữ liệu giả từng đi thẳng vào trường answer như một câu
    trả lời bình thường — nếu nó còn được tính là nguồn thì cổng grounding
    chỉ chặn được đúng những ca vô hại.
    """
    if not isinstance(context, dict):
        return False
    khoa_can_xet = _KHOA_SO_LIEU_THEO_INTENT.get(intent, _KHOA_SO_LIEU if intent is None else ())
    return any(
        context.get(khoa) and not _la_mock(context.get(khoa))
        for khoa in khoa_can_xet
    )


def _la_cau_hoi_du_bao_dinh_luong(cau_hoi: str) -> bool:
    text = normalize_user_text(cau_hoi)
    co_moc_tuong_lai = any(
        cum in text for cum in ("nam toi", "vu toi", "thang toi", "se dat", "du bao", "du kien")
    )
    hoi_con_so = any(
        cum in text
        for cum in ("bao nhieu", "nang suat", "san luong", "tan moi hecta", "tan ha")
    )
    return co_moc_tuong_lai and hoi_con_so


_DANG_TRICH_DAN = re.compile(r"\[\s*TL\s*\d+\s*\]", re.IGNORECASE)


def bao_dam_trich_dan(tra_loi: str, sources: list[dict] | None) -> str:
    """Gắn danh sách nguồn khi câu trả lời dựa trên tài liệu mà không trích dẫn.

    Prompt đã yêu cầu trích dẫn [TL1], [TL2] nhưng model nhỏ bỏ qua thường
    xuyên. Chặn hẳn câu trả lời vì thiếu dấu ngoặc vuông thì quá tay — người
    dùng mất một câu trả lời đúng. Nêu rõ nó dựa trên tài liệu nào thì vừa đủ:
    ai muốn kiểm chứng vẫn lần được về nguồn.
    """
    if not sources or not (tra_loi or "").strip():
        return tra_loi
    if _DANG_TRICH_DAN.search(tra_loi):
        return tra_loi
    dong = []
    for stt, nguon in enumerate(sources, start=1):
        nhan = nguon.get("citation") or f"TL{stt}"
        ten = nguon.get("name") or nguon.get("source_name") or "tài liệu trong kho"
        trang = nguon.get("page")
        dong.append(f"- [{nhan}] {ten}" + (f" — trang {trang}" if trang else ""))
    return f"{tra_loi}\n\nNguồn tham khảo:\n" + "\n".join(dong)


def danh_gia_grounding(
    *,
    cau_hoi: str,
    intent: str,
    rag: dict | None,
    co_du_lieu_so: bool = False,
    crop: str | None = None,
) -> QuyetDinhGrounding:
    trang_thai = chuan_hoa_trang_thai(rag)
    if intent in INTENT_KHONG_CAN_NGUON:
        return QuyetDinhGrounding(trang_thai=trang_thai, duoc_goi_model=True, cau_tra_loi="")
    # Xét phạm vi TRƯỚC khi xét có nguồn. Retrieval luôn trả về đoạn gần nhất
    # trong kho, kể cả khi câu hỏi chẳng liên quan gì tới nông nghiệp — đo
    # thật trên corpus khuyến nông: "Thủ đô nước Pháp là gì?" cho status
    # ready. Xét "có nguồn" trước thì mấy đoạn vô can ấy thành giấy phép.
    if intent == "general_question" and not _thuoc_pham_vi_nong_nghiep(cau_hoi, crop):
        return QuyetDinhGrounding(
            trang_thai=trang_thai,
            duoc_goi_model=False,
            cau_tra_loi=_NGOAI_PHAM_VI,
            ly_do="ngoai_pham_vi",
        )
    if co_du_lieu_so and intent in INTENT_NEO_BANG_SO_LIEU and not _la_cau_hoi_ke_don(cau_hoi):
        return QuyetDinhGrounding(trang_thai=trang_thai, duoc_goi_model=True, cau_tra_loi="")
    # Giá hiện tại là dữ liệu đo theo thời điểm. Một bài viết RAG có nhắc tới
    # giá trong quá khứ không thể thay thế bản ghi giá mới từ backend.
    if intent == "price_analysis" and not co_du_lieu_so:
        return QuyetDinhGrounding(
            trang_thai="no_match",
            duoc_goi_model=False,
            cau_tra_loi=f"{_LY_DO_THIEU_NGUON['no_match']}\n\n{_KHONG_DUA_RA_LOI_KHUYEN}",
            ly_do="thieu_nguon",
        )
    # Câu hỏi xin liều/nồng độ là ca rủi ro cao. Nguồn chỉ nhắc đúng sâu bệnh
    # hoặc cây trồng vẫn chưa đủ: phải có liều, nồng độ hay tỷ lệ pha cụ thể.
    if _la_cau_hoi_lieu_luong(cau_hoi) and not _nguon_co_lieu_luong(rag):
        return QuyetDinhGrounding(
            trang_thai="no_match",
            duoc_goi_model=False,
            cau_tra_loi=f"{_LY_DO_THIEU_NGUON['no_match']}\n\n{_KHONG_DUA_RA_LOI_KHUYEN}",
            ly_do="thieu_nguon",
        )
    if _la_cau_hoi_du_bao_dinh_luong(cau_hoi) and not co_du_lieu_so:
        return QuyetDinhGrounding(
            trang_thai="no_match",
            duoc_goi_model=False,
            cau_tra_loi=f"{_LY_DO_THIEU_NGUON['no_match']}\n\n{_KHONG_DUA_RA_LOI_KHUYEN}",
            ly_do="thieu_nguon",
        )
    if trang_thai == "ready":
        return QuyetDinhGrounding(trang_thai=trang_thai, duoc_goi_model=True, cau_tra_loi="")
    return QuyetDinhGrounding(
        trang_thai=trang_thai,
        duoc_goi_model=False,
        cau_tra_loi=f"{_LY_DO_THIEU_NGUON[trang_thai]}\n\n{_KHONG_DUA_RA_LOI_KHUYEN}",
        ly_do="thieu_nguon",
    )
