"""
TDD cho phần chấm điểm của scripts/evaluate_rag.py.

Phần gọi mạng thì phải chạy thật mới biết, nhưng phần KẾT LUẬN từ một câu trả
lời thì không cần LLM nào cả. Tách ra được thì mỗi lần sửa luật chấm không
phải chạy lại 30 lượt gọi model — và luật chấm mới là chỗ dễ sai lặng lẽ:
một hệ thống từ chối mọi câu vẫn đạt điểm tuyệt đối nếu chấm sai.
"""
from scripts.evaluate_rag import cham_diem

CAU_CO_NGUON = {
    "id": "q-01", "category": "grounded",
    "expected_behavior": "answer_with_citation",
    "expected_doc_ids": ["kn-02"],
    "question": "Ruộng lúa bị úng ngập sau mưa bão thì cần làm gì?",
}
CAU_THIEU_NGUON = {
    "id": "q-21", "category": "no_source",
    "expected_behavior": "insufficient_data",
    "expected_doc_ids": [],
    "question": "Trồng nho ngón tay để khoảng cách bao nhiêu mét?",
}
CAU_LAC_DE = {
    "id": "q-27", "category": "out_of_scope",
    "expected_behavior": "out_of_scope_refusal",
    "expected_doc_ids": [],
    "question": "Thủ đô nước Pháp là gì?",
}


# bao_dam_trich_dan gắn phần này vào mọi câu trả lời có sources, kể cả câu
# chỉ có từ chối — nên câu trả lời thật luôn mang nó.
CHAN_NGUON_HE_THONG = "\n\nNguồn tham khảo:\n- [TL1] tai-lieu-2.txt — trang 3"


def _ban_ghi(**thay_doi):
    ban_ghi = {
        "generated_answer": "Theo [TL1], cần khơi thông dòng chảy và tiêu úng nhanh.",
        "grounding": {"status": "ready", "reason": "ready"},
        "citations": [{"citation": "TL1", "doc_id": "kn-02", "excerpt": "Khơi thông dòng chảy, tiêu úng."}],
        "retrieved_doc_ids": ["kn-02"],
        "error": None,
    }
    ban_ghi.update(thay_doi)
    return ban_ghi


def test_cau_co_nguon_tra_loi_kem_trich_dan_thi_cho_nguoi_duyet():
    """Máy xác nhận được hình thức, không xác nhận được nội dung có đúng không.

    Nói "pass" ở đây là tự nhận rằng script đọc hiểu tài liệu khuyến nông —
    nó không làm được. Trạng thái trung thực là chờ người duyệt.
    """
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi())

    assert ket_qua["verdict"] == "needs_review"
    assert all(ket_qua["checks"].values())


def test_cau_co_nguon_ma_tra_loi_khong_trich_dan_thi_truot():
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer="Cần khơi thông dòng chảy và tiêu úng nhanh.",
        citations=[],
        retrieved_doc_ids=[],
    ))

    assert ket_qua["verdict"] == "fail"
    assert ket_qua["checks"]["co_trich_dan"] is False


def test_cau_co_nguon_ma_lay_nham_tai_lieu_thi_truot():
    """Có trích dẫn nhưng trích tài liệu về tôm cho câu hỏi về lúa vẫn là sai."""
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        citations=[{"citation": "TL1", "doc_id": "kn-17", "excerpt": "Vibrio trên tôm."}],
        retrieved_doc_ids=["kn-17"],
    ))

    assert ket_qua["verdict"] == "fail"
    assert ket_qua["checks"]["khong_lay_nham_tai_lieu_trong_corpus"] is False


def test_con_so_khong_co_trong_doan_trich_bi_bat():
    """Chốt chặn số bịa của hệ thống được dùng lại làm luật chấm.

    Model nhỏ hay chèn "bón 250 kg/ha" nghe rất thuyết phục vào giữa một câu
    trả lời có trích dẫn. Đoạn trích không có con số đó thì nó đến từ trí nhớ
    của model chứ không từ tài liệu.
    """
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer="Theo [TL1], cần tiêu úng và bón 250.000 đồng phân mỗi sào.",
    ))

    assert ket_qua["checks"]["khong_bia_so_lieu"] is False
    assert ket_qua["verdict"] == "fail"


def test_cau_thieu_nguon_tra_chua_du_du_lieu_thi_dat():
    """Nhóm này chấm tự động được hoàn toàn — không cần người duyệt."""
    ket_qua = cham_diem(CAU_THIEU_NGUON, _ban_ghi(
        generated_answer="Kho tài liệu có nội dung nhưng không khớp câu hỏi này, nên tôi chưa đủ dữ liệu để trả lời.",
        grounding={"status": "no_match", "reason": "thieu_nguon"},
        citations=[], retrieved_doc_ids=[],
    ))

    assert ket_qua["verdict"] == "pass"


def test_cau_thieu_nguon_ma_model_van_tra_loi_thi_truot():
    """Đây chính là lỗi mà cả bài đánh giá sinh ra để bắt."""
    ket_qua = cham_diem(CAU_THIEU_NGUON, _ban_ghi(
        generated_answer="Nho ngón tay nên trồng cách nhau 3 mét, hàng cách hàng 3,5 mét.",
        grounding={"status": "no_match", "reason": "ready"},
        citations=[], retrieved_doc_ids=[],
    ))

    assert ket_qua["verdict"] == "fail"


def test_cau_lac_de_phai_tu_choi_theo_pham_vi_chu_khong_phai_thieu_du_lieu():
    dung = cham_diem(CAU_LAC_DE, _ban_ghi(
        generated_answer="Câu hỏi này nằm ngoài lĩnh vực nông nghiệp nên tôi không trả lời.",
        grounding={"status": "no_match", "reason": "ngoai_pham_vi"},
        citations=[], retrieved_doc_ids=[],
    ))
    nham = cham_diem(CAU_LAC_DE, _ban_ghi(
        generated_answer="Tôi chưa đủ dữ liệu để trả lời câu hỏi này.",
        grounding={"status": "no_match", "reason": "thieu_nguon"},
        citations=[], retrieved_doc_ids=[],
    ))

    assert dung["verdict"] == "pass"
    assert nham["verdict"] == "fail"


def test_loi_goi_api_duoc_ghi_la_truot_chu_khong_bi_bo_qua():
    """Bỏ qua lượt lỗi là làm đẹp số liệu: tỷ lệ đạt tính trên mẫu còn sống."""
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer="", grounding={}, citations=[], retrieved_doc_ids=[],
        error={"http_status": 502, "code": "AI_UNAVAILABLE"},
    ))

    assert ket_qua["verdict"] == "fail"
    assert "request_failed" in ket_qua["notes"]


def test_nam_trong_ngay_thang_khong_bi_ket_toi_bia_so_lieu():
    """Đo thật: câu trả lời mở đầu bằng "Hiện tại (2026-09-26)..." bị chấm
    trượt vì "2026" không có trong đoạn trích.

    Chốt chặn số liệu đếm mọi cụm từ 4 chữ số trở lên là số liệu thị trường —
    đúng cho "96.433 đ/kg", sai cho năm. Một luật chấm hay báo động giả thì
    người đọc sẽ bỏ qua nó, và lúc đó nó không còn bắt được con số bịa thật.
    """
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer="Hiện tại (2026-09-26), theo [TL1] cần tiêu úng nhanh.",
    ))

    assert ket_qua["checks"]["khong_bia_so_lieu"] is True


def test_so_lieu_that_su_la_khong_co_nguon_van_bi_bat():
    """Nới cho năm không được nới cho lượng phân, giá tiền."""
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer="Theo [TL1], bón 4500 kg vôi mỗi hecta.",
    ))

    assert ket_qua["checks"]["khong_bia_so_lieu"] is False


def test_model_tu_choi_nhung_cong_khong_chan_thi_khong_phai_dat():
    """Đo thật: 5/6 câu thiếu nguồn được model từ chối bằng lời lẽ riêng của
    nó ("Không có dữ liệu trong tài liệu truy xuất về..."), trong khi cổng
    grounding vẫn để lượt đó đi qua vì retrieval trả về status ready.

    Gọi đây là "đạt" thì bài đánh giá đang tính công cho sự may mắn: lần này
    model ngoan, lần sau cùng câu hỏi đó nó có thể bịa. Gọi là "trượt" thì
    cũng sai — hệ thống đã không đưa thông tin bịa cho nông dân. Đây đúng là
    chỗ cần người đọc, kèm ghi chú nói rõ lỗ hổng nằm ở cổng.
    """
    ket_qua = cham_diem(CAU_THIEU_NGUON, _ban_ghi(
        generated_answer="Không có dữ liệu trong tài liệu truy xuất về khoảng cách trồng nho ngón tay.",
        grounding={"status": "ready", "reason": "ready"},
        citations=[], retrieved_doc_ids=[],
    ))

    assert ket_qua["verdict"] == "needs_review"
    assert "cong_khong_chan_model_tu_tu_choi" in ket_qua["notes"]


def test_cac_cach_noi_khac_cua_tu_choi_deu_duoc_nhan_ra():
    """"chưa có dữ liệu", "không có dữ liệu", "chưa đủ dữ liệu" — cùng một ý."""
    for cach_noi in (
        "Chưa có dữ liệu trong tài liệu tham khảo về việc này.",
        "Dữ liệu hiện có không cung cấp thông tin về quy trình này.",
        "Tôi chưa đủ dữ liệu để trả lời.",
    ):
        ket_qua = cham_diem(CAU_THIEU_NGUON, _ban_ghi(
            generated_answer=cach_noi,
            grounding={"status": "no_match", "reason": "thieu_nguon"},
            citations=[], retrieved_doc_ids=[],
        ))
        assert ket_qua["verdict"] == "pass", cach_noi


def test_lay_tai_lieu_ngoai_corpus_thi_cho_nguoi_doc_chu_khong_truot_thang():
    """Kho chia sẻ có 127 tài liệu, không chỉ 20 tài liệu corpus cố định.

    Retrieval lấy một tài liệu khuyến nông khác đúng chủ đề thì câu trả lời
    vẫn có thể đúng và có nguồn. Máy không đọc hiểu được để kết luận thay, nên
    chuyển cho người đọc thay vì đánh trượt một hành vi có khi là đúng.
    """
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        citations=[{"citation": "TL1", "doc_id": None, "name": "tai-lieu-khac.txt",
                    "excerpt": "Tiêu úng cho ruộng lúa."}],
        retrieved_doc_ids=[],
    ))

    assert ket_qua["verdict"] == "needs_review"
    assert "tai_lieu_ngoai_corpus_co_dinh" in ket_qua["notes"]


def test_khong_co_trich_dan_nao_thi_van_truot():
    """Nới cho tài liệu ngoài corpus không được nới cho việc không có nguồn."""
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer="Cần tiêu úng nhanh.", citations=[], retrieved_doc_ids=[],
    ))

    assert ket_qua["verdict"] == "fail"


def test_tu_choi_TUNG_PHAN_kem_noi_dung_co_nguon_khong_bi_tinh_la_tu_choi():
    """System prompt bảo model: phần nào tài liệu không nói tới thì nói thẳng
    "chưa đủ dữ liệu cho phần này". Model làm đúng như vậy — trả lời phần có
    nguồn và nêu rõ phần thiếu.

    Chấm trượt ở đây là phạt đúng hành vi mình vừa yêu cầu. Cái cần bắt là
    câu trả lời CHỈ có từ chối, không có nội dung nào.
    """
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer=(
            "Theo tài liệu, cần khơi thông dòng chảy và tiêu úng trong 24 giờ đầu, "
            "sau đó dựng lại các khóm lúa bị đổ rạp và bón bổ sung phân bón lá "
            "theo khuyến cáo. Giai đoạn trỗ cần tháo cạn nước để cây đứng vững, "
            "kết hợp theo dõi sâu bệnh phát sinh sau ngập. Riêng liều lượng cụ "
            "thể cho từng giống thì chưa đủ dữ liệu trong tài liệu hiện có."
            + CHAN_NGUON_HE_THONG
        ),
    ))

    assert ket_qua["verdict"] == "needs_review"


def test_cau_tra_loi_co_cau_tu_choi_duoc_danh_dau_cho_nguoi_doc():
    """Máy không tách được "từ chối" khỏi "trả lời kèm ghi chú phần thiếu".

    Đo trên 20 câu có nguồn: mọi câu trả lời đều dài 629–896 ký tự (output
    giới hạn 256 token), nên độ dài không tách được gì. 9/20 câu có chứa lời
    từ chối cho một phần — đúng như system prompt yêu cầu. Và model bỏ trích
    dẫn inline ở 8/20 câu trả lời tốt, nên sự có mặt của [TLn] cũng không
    tách được.

    Ca hỏng thật — hệ thống từ chối hẳn một câu có nguồn — vẫn bị bắt bởi các
    check khác: cổng từ chối thì status không phải ready và không có trích
    dẫn nào. Nên chỗ này chỉ cần đánh dấu để người đọc soi kỹ.
    """
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer="Tôi chưa đủ dữ liệu để trả lời câu hỏi này." + CHAN_NGUON_HE_THONG,
    ))

    assert ket_qua["verdict"] == "needs_review"
    assert "co_cau_tu_choi_trong_cau_tra_loi" in ket_qua["notes"]


def test_cong_tu_choi_mot_cau_co_nguon_van_la_truot():
    """Ca hỏng thật vẫn phải trượt: không có nguồn, trạng thái không ready."""
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer="Kho tài liệu có nội dung nhưng không khớp câu hỏi này.",
        grounding={"status": "no_match", "reason": "thieu_nguon"},
        citations=[], retrieved_doc_ids=[],
    ))

    assert ket_qua["verdict"] == "fail"


CAU_THOI_TIET = {
    "id": "q003", "category": "grounded",
    "expected_behavior": "answer_with_citation",
    "expected_doc_ids": ["kn-03"],
    "question": "Sau bão Yagi, biện pháp ưu tiên với trà lúa bị ngập là gì?",
}


def test_so_lieu_backend_khong_bi_ket_toi_bia_ma_chuyen_cho_nguoi_doc():
    """Đo thật: câu trả lời mở đầu bằng số liệu thời tiết thật của backend —
    "nhiệt độ 25,8°C, độ ẩm 99%, áp suất 1009,3 hPa" — bị chấm trượt vì
    "1009,3" không có trong đoạn trích tài liệu.

    Script chỉ nhìn thấy đoạn trích RAG, không nhìn thấy context backend, nên
    nó KHÔNG BIẾT con số đó từ đâu. Kết luận "bịa" ở đây là nói quá những gì
    đo được. Với intent được neo bằng số liệu đo (giá, thời tiết, mùa vụ),
    chuyển thành ghi chú kèm danh sách số để người đọc tự đối chiếu.
    """
    ket_qua = cham_diem(CAU_THOI_TIET, _ban_ghi(
        generated_answer="Nhiệt độ 25,8°C, độ ẩm 99%, áp suất 1009,3 hPa." + CHAN_NGUON_HE_THONG,
        intent="weather_analysis",
        citations=[{"citation": "TL1", "doc_id": "kn-03", "excerpt": "Giảm thiệt hại sau bão."}],
        retrieved_doc_ids=["kn-03"],
    ))

    assert ket_qua["verdict"] == "needs_review"
    assert "so_lieu_chua_doi_chieu_duoc_voi_backend" in ket_qua["notes"]
    # Chốt chặn tách theo cụm chữ số, nên "1009,3 hPa" ra "1009".
    assert "1009" in ket_qua["so_lieu_khong_ro_nguon"]


def test_cau_hoi_ky_thuat_thi_so_la_van_bi_tinh_la_bia():
    """Nới cho intent số liệu không được nới cho câu hỏi kỹ thuật.

    Câu hỏi kỹ thuật chỉ có một nguồn hợp lệ là tài liệu; con số không nằm
    trong đoạn trích nào thì đến từ trí nhớ của model.
    """
    ket_qua = cham_diem(CAU_CO_NGUON, _ban_ghi(
        generated_answer="Theo tài liệu, rải vôi bột 4500 kg mỗi hecta." + CHAN_NGUON_HE_THONG,
        intent="cultivation_advice",
    ))

    assert ket_qua["verdict"] == "fail"
    assert ket_qua["checks"]["khong_bia_so_lieu"] is False
