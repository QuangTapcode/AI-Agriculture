"""
TDD: câu hỏi nông nghiệp không có nguồn phù hợp phải trả "chưa đủ dữ liệu".

Trước đây chỉ hai intent (chăn nuôi, kỹ thuật canh tác) bị chặn khi kho tài
liệu không khớp. Mọi intent còn lại — kể cả general_question, là nơi mọi câu
hỏi không khớp từ khoá nào rơi vào — vẫn được đẩy xuống LLM, và system prompt
lại cho phép "dùng kiến thức nông nghiệp phổ thông". Kết quả: trợ lý trả lời
liều lượng phân bón, cách trị sâu bệnh bằng trí nhớ của model, không citation,
không ai kiểm chứng được.

Với nông dân, một câu "chưa đủ dữ liệu" an toàn hơn hẳn một lời khuyên tự tin
mà không có nguồn.
"""
from app.services.grounding_policy import bao_dam_trich_dan, danh_gia_grounding


def test_cau_hoi_nong_nghiep_khong_co_nguon_thi_khong_duoc_goi_model():
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Cà chua bị đốm lá nên phun thuốc gì?",
        intent="quality_analysis",
        rag={"status": "no_match", "sources": []},
    )

    assert quyet_dinh.duoc_goi_model is False
    assert "chưa đủ dữ liệu" in quyet_dinh.cau_tra_loi.lower()


def test_co_nguon_khop_thi_model_duoc_tra_loi():
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Cà chua bị đốm lá nên phun thuốc gì?",
        intent="quality_analysis",
        rag={"status": "ready", "sources": [{"citation": "TL1", "name": "Quy trình cà chua"}]},
    )

    assert quyet_dinh.duoc_goi_model is True
    assert quyet_dinh.cau_tra_loi == ""


def test_quyet_dinh_neu_ro_trang_thai_cua_kho_tai_lieu():
    """Bốn trạng thái phải đi ra ngoài được: UI và log cần phân biệt."""
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Cà chua bị đốm lá nên phun thuốc gì?",
        intent="quality_analysis",
        rag={"status": "no_match", "sources": []},
    )

    assert quyet_dinh.trang_thai == "no_match"


def test_trang_thai_ready_ma_khong_co_nguon_thi_khong_phai_ready():
    """rag_service trả ready kèm sources rỗng là mâu thuẫn — đừng tin nhãn."""
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Cà chua bị đốm lá nên phun thuốc gì?",
        intent="quality_analysis",
        rag={"status": "ready", "sources": []},
    )

    assert quyet_dinh.trang_thai == "no_match"
    assert quyet_dinh.duoc_goi_model is False


def test_payload_la_thi_coi_nhu_kho_tai_lieu_khong_dung_duoc():
    """None, dict rỗng hay nhãn lạ đều không chứng minh được có nguồn."""
    for rag in (None, {}, {"status": "khong_biet", "sources": []}, "hỏng"):
        quyet_dinh = danh_gia_grounding(
            cau_hoi="Cà chua bị đốm lá nên phun thuốc gì?",
            intent="quality_analysis",
            rag=rag,
        )
        assert quyet_dinh.trang_thai == "unavailable", rag
        assert quyet_dinh.duoc_goi_model is False, rag


def _cau_tra_loi(trang_thai):
    return danh_gia_grounding(
        cau_hoi="Cà chua bị đốm lá nên phun thuốc gì?",
        intent="quality_analysis",
        rag={"status": trang_thai, "sources": []},
    ).cau_tra_loi.lower()


def test_kho_rong_va_kho_loi_duoc_phan_biet_voi_khong_khop():
    """Ba lý do khác nhau, ba hành động khác nhau cho người dùng.

    Kho rỗng thì phải nạp tài liệu; kho lỗi thì hỏi lại sau; không khớp thì
    mô tả câu hỏi rõ hơn. Gộp chung thành một câu là bắt nông dân tự đoán.
    """
    assert "chưa có tài liệu nào" in _cau_tra_loi("empty")
    assert "thử lại" in _cau_tra_loi("unavailable")
    assert "không khớp" in _cau_tra_loi("no_match")


def test_moi_trang_thai_thieu_nguon_deu_noi_chua_du_du_lieu():
    for trang_thai in ("no_match", "empty", "unavailable"):
        assert "chưa đủ dữ liệu" in _cau_tra_loi(trang_thai), trang_thai


def test_chao_hoi_va_hoi_nang_luc_khong_bi_chan():
    """Chặn grounding là để chặn NHẬN ĐỊNH SAI, không phải chặn giao tiếp.

    "Xin chào" hay "bạn làm được gì?" không khẳng định điều gì về nông nghiệp
    nên không cần nguồn. Bắt chúng trả "chưa đủ dữ liệu" chỉ làm trợ lý trông
    như hỏng.
    """
    for intent in ("greeting", "capability_question"):
        quyet_dinh = danh_gia_grounding(
            cau_hoi="Xin chào, bạn làm được gì?",
            intent=intent,
            rag={"status": "empty", "sources": []},
        )
        assert quyet_dinh.duoc_goi_model is True, intent


def test_cau_hoi_gia_co_so_lieu_backend_thi_duoc_tra_loi():
    """Nguồn của câu hỏi giá là bảng giá trong DB, không phải kho tài liệu.

    Ép câu hỏi giá phải có tài liệu PDF mới được trả lời thì trợ lý sẽ từ
    chối chính thứ nó đo được chính xác nhất.
    """
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Giá cà phê Đắk Lắk hôm nay?",
        intent="price_analysis",
        rag={"status": "no_match", "sources": []},
        co_du_lieu_so=True,
    )

    assert quyet_dinh.duoc_goi_model is True


def test_cau_hoi_gia_khong_co_so_lieu_cung_khong_co_tai_lieu_thi_bi_chan():
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Giá cà phê Đắk Lắk hôm nay?",
        intent="price_analysis",
        rag={"status": "no_match", "sources": []},
        co_du_lieu_so=False,
    )

    assert quyet_dinh.duoc_goi_model is False
    assert "chưa đủ dữ liệu" in quyet_dinh.cau_tra_loi.lower()


def test_so_lieu_gia_khong_chung_minh_duoc_cach_tri_sau_benh():
    """Số liệu chỉ neo được đúng loại câu hỏi mà nó đo.

    Có giá cà phê trong context không có nghĩa là trợ lý được phép kê thuốc
    trị đốm lá. Đây đúng là kiểu "có dữ liệu gì đó nên cứ trả lời" mà cổng
    grounding sinh ra để chặn.
    """
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Cà phê bị rệp sáp thì phun thuốc gì, liều bao nhiêu?",
        intent="quality_analysis",
        rag={"status": "no_match", "sources": []},
        co_du_lieu_so=True,
    )

    assert quyet_dinh.duoc_goi_model is False


def test_cau_hoi_ngoai_nong_nghiep_tu_choi_theo_pham_vi():
    """"Chưa đủ dữ liệu" là câu trả lời SAI cho câu hỏi ngoài phạm vi.

    Nó ngụ ý rằng nạp thêm tài liệu thì trợ lý sẽ trả lời được thủ đô nước
    Pháp. Hai tình huống khác nhau thì phải nói khác nhau.
    """
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Thủ đô nước Pháp là gì?",
        intent="general_question",
        rag={"status": "no_match", "sources": []},
    )

    assert quyet_dinh.duoc_goi_model is False
    assert quyet_dinh.ly_do == "ngoai_pham_vi"
    assert "nông nghiệp" in quyet_dinh.cau_tra_loi.lower()
    assert "chưa đủ dữ liệu" not in quyet_dinh.cau_tra_loi.lower()


def test_cau_hoi_nong_nghiep_thieu_nguon_co_ly_do_khac_ngoai_pham_vi():
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Lúa hè thu bón đạm bao nhiêu kg một hecta?",
        intent="general_question",
        rag={"status": "no_match", "sources": []},
    )

    assert quyet_dinh.ly_do == "thieu_nguon"
    assert "chưa đủ dữ liệu" in quyet_dinh.cau_tra_loi.lower()


def test_cay_trong_da_xac_dinh_thi_luon_thuoc_pham_vi():
    """Câu cụt như "Nho?" không chứa từ khoá nông nghiệp nào, nhưng crop đã
    được resolve từ tầng trên — đừng vứt thông tin đó đi."""
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Nho ngón tay?",
        intent="general_question",
        rag={"status": "no_match", "sources": []},
        crop="nho",
    )

    assert quyet_dinh.ly_do == "thieu_nguon"

NGUON = [
    {"citation": "TL1", "name": "Quy trình cà chua", "page": 3},
    {"citation": "TL2", "name": "Sổ tay BVTV", "page": 11},
]


def test_cau_tra_loi_khong_co_trich_dan_duoc_gan_nguon():
    """Có nguồn mà không trích dẫn thì người đọc không kiểm chứng được.

    Model nhỏ thường bỏ qua yêu cầu trích dẫn trong prompt. Không chặn được
    thì ít nhất phải nói rõ câu trả lời dựa trên tài liệu nào.
    """
    ket_qua = bao_dam_trich_dan("Bón 20 kg đạm mỗi hecta.", NGUON)

    assert "TL1" in ket_qua and "Quy trình cà chua" in ket_qua
    assert "TL2" in ket_qua and "Sổ tay BVTV" in ket_qua
    assert ket_qua.startswith("Bón 20 kg đạm mỗi hecta.")


def test_cau_tra_loi_da_trich_dan_thi_giu_nguyen():
    da_trich_dan = "Theo [TL1], bón 20 kg đạm mỗi hecta."

    assert bao_dam_trich_dan(da_trich_dan, NGUON) == da_trich_dan


def test_khong_co_nguon_thi_khong_bia_ra_phan_nguon():
    assert bao_dam_trich_dan("Chưa đủ dữ liệu.", []) == "Chưa đủ dữ liệu."


def test_du_lieu_mock_khong_duoc_tinh_la_nguon():
    """Mock từng lọt ra API công khai một lần rồi — đừng để nó neo câu trả lời."""
    from app.services.grounding_policy import co_du_lieu_so

    assert co_du_lieu_so({"pricing": {"avg_price": 96433, "source_type": "database"}}) is True
    assert co_du_lieu_so({"pricing": {"avg_price": 96433, "is_mock": True}}) is False
    assert co_du_lieu_so({"pricing": {"avg_price": 96433, "source_type": "mock"}}) is False
    assert co_du_lieu_so({"pricing": {}}) is False
    assert co_du_lieu_so({}) is False
    assert co_du_lieu_so(None) is False


def test_thoi_tiet_va_canh_bao_cung_la_so_lieu_neo_duoc():
    from app.services.grounding_policy import co_du_lieu_so

    assert co_du_lieu_so({"weather": {"temperature": 31.2}}) is True
    assert co_du_lieu_so({"alerts": [{"title": "Mưa lớn"}]}) is True
    assert co_du_lieu_so({"harvest_status": {"days_to_harvest": 12}}) is True
    assert co_du_lieu_so({"history": [{"role": "user"}]}) is False


def test_so_lieu_khong_mo_khoa_cau_hoi_ke_thuoc_ke_lieu():
    """Có số liệu thời tiết không có nghĩa là được kê thuốc.

    Bộ phân loại intent khớp "phun" vào nhóm thời tiết, nên câu "sâu bệnh này
    phun thuốc gì?" đi vào weather_analysis — intent vốn được neo bằng số liệu
    đo được. Nếu chỉ xét intent thì nhiệt độ và lượng mưa sẽ mở khoá cho model
    tự kê thuốc và liều lượng. Đây là loại sai nguy hiểm nhất với nông dân.
    """
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Cà chua bị đốm lá nên phun thuốc gì?",
        intent="weather_analysis",
        rag={"status": "no_match", "sources": []},
        co_du_lieu_so=True,
    )

    assert quyet_dinh.duoc_goi_model is False
    assert quyet_dinh.ly_do == "thieu_nguon"


def test_cau_hoi_lieu_luong_phan_bon_cung_can_tai_lieu():
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Lúa giai đoạn đẻ nhánh bón bao nhiêu kg urê một sào?",
        intent="harvest_analysis",
        rag={"status": "no_match", "sources": []},
        co_du_lieu_so=True,
    )

    assert quyet_dinh.duoc_goi_model is False


def test_cau_hoi_lieu_luong_duoc_phep_khi_nguon_co_nong_do_cu_the():
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Cà phê nên pha thuốc với liều bao nhiêu ml mỗi lít nước?",
        intent="quality_analysis",
        rag={"status": "ready", "sources": [{
            "name": "Quy trình phòng bệnh cà phê",
            "excerpt": "Pha 2 ml thuốc cho mỗi lít nước theo hướng dẫn trên nguồn.",
        }]},
        co_du_lieu_so=False,
    )

    assert quyet_dinh.duoc_goi_model is True


def test_cau_hoi_thuan_so_lieu_van_duoc_tra_loi_binh_thuong():
    """Siết chỗ kê đơn, không siết chỗ đọc số liệu."""
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Mai trời có mưa không, tôi tính phơi lúa?",
        intent="weather_analysis",
        rag={"status": "no_match", "sources": []},
        co_du_lieu_so=True,
    )

    assert quyet_dinh.duoc_goi_model is True


def test_cau_hoi_ve_dat_dai_thuoc_pham_vi_nong_nghiep():
    """Cải tạo đất phèn, đất mặn là câu hỏi nông nghiệp lõi ở ĐBSCL.

    Từ chối theo phạm vi ở đây là nói sai — vấn đề là kho chưa có nguồn, chứ
    không phải câu hỏi lạc đề.
    """
    for cau_hoi in (
        "Đất phèn thì xử lý ra sao cho hợp lý?",
        "Cải tạo đất mặn bằng cách nào?",
        "Độ pH đất bao nhiêu là tốt?",
    ):
        quyet_dinh = danh_gia_grounding(
            cau_hoi=cau_hoi, intent="general_question",
            rag={"status": "no_match", "sources": []},
        )
        assert quyet_dinh.ly_do == "thieu_nguon", cau_hoi


def test_cau_hoi_ro_rang_lac_de_van_bi_tu_choi_theo_pham_vi():
    """Nới từ vựng không được làm cổng phạm vi thành vô dụng."""
    for cau_hoi in (
        "Thủ đô nước Pháp là gì?",
        "Viết giúp tôi một đoạn code Python sắp xếp mảng",
        "Tỷ số trận đấu tối qua thế nào?",
    ):
        quyet_dinh = danh_gia_grounding(
            cau_hoi=cau_hoi, intent="general_question",
            rag={"status": "no_match", "sources": []},
        )
        assert quyet_dinh.ly_do == "ngoai_pham_vi", cau_hoi


def test_rag_bi_tat_cung_la_khong_co_nguon():
    """RAG_ENABLED=false trả status "disabled" — nằm ngoài bốn trạng thái.

    Tắt tra cứu không làm câu trả lời có nguồn hơn. Quy về unavailable để giữ
    đúng bốn trạng thái, nhưng câu chữ không được đổ tại "sự cố" vì đây có
    thể là lựa chọn cấu hình.
    """
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Cà chua bị đốm lá nên phun thuốc gì?",
        intent="quality_analysis",
        rag={"status": "disabled", "sources": []},
    )

    assert quyet_dinh.trang_thai == "unavailable"
    assert quyet_dinh.duoc_goi_model is False
    assert "sự cố" not in quyet_dinh.cau_tra_loi.lower()
    assert "chưa đủ dữ liệu" in quyet_dinh.cau_tra_loi.lower()


def test_cau_lac_de_van_bi_tu_choi_du_retrieval_tra_ve_nguon():
    """Vector store luôn tìm được "cái gì đó" — đo thật trên corpus khuyến nông:

        Hỏi "Thủ đô nước Pháp là gì?" -> rag status = ready, có sources.

    Không tài liệu nào trong kho nói về thủ đô nước Pháp; điểm tương đồng vượt
    ngưỡng chỉ vì ngưỡng là một con số, không phải một phán đoán. Nếu cổng xét
    "có nguồn" trước khi xét "có thuộc phạm vi", thì mấy đoạn trích vô can ấy
    trở thành giấy phép cho model trả lời bất cứ thứ gì.
    """
    quyet_dinh = danh_gia_grounding(
        cau_hoi="Thủ đô nước Pháp là gì?",
        intent="general_question",
        rag={"status": "ready", "sources": [
            {"citation": "TL1", "name": "challenge-kn-09.txt", "excerpt": "Khắc phục rau màu sau bão lũ."},
        ]},
    )

    assert quyet_dinh.duoc_goi_model is False
    assert quyet_dinh.ly_do == "ngoai_pham_vi"


def test_cau_hoi_thuy_san_va_vat_nuoi_khong_bi_coi_la_lac_de():
    """Đo thật: "Tôm thẻ chân trắng bị hoại tử gan tụy cấp do Vibrio thì kiểm
    soát ra sao?" bị cổng phạm vi từ chối — trong khi kho có hẳn một tài liệu
    khuyến nông đúng chủ đề đó.

    Danh sách từ khoá bỏ hết từ một âm tiết vì sợ nhầm khi bỏ dấu. Nhưng với
    chữ CÒN DẤU thì "tôm", "cá", "gà", "vịt" không nhầm với gì cả — dấu chính
    là thứ phân biệt. Bỏ chúng đi là nói với người nuôi tôm rằng câu hỏi của
    họ không thuộc lĩnh vực nông nghiệp.
    """
    for cau_hoi in (
        "Tôm thẻ chân trắng bị hoại tử gan tụy cấp do Vibrio thì kiểm soát ra sao?",
        "Cá song chấm nâu thương phẩm cho ăn thế nào?",
        "Gà đẻ bị giảm sản lượng trứng thì xử lý ra sao?",
        "Vịt bỏ ăn mấy hôm nay là dấu hiệu gì?",
        "Lợn nái sau sinh chăm thế nào cho lại sức?",
    ):
        quyet_dinh = danh_gia_grounding(
            cau_hoi=cau_hoi, intent="general_question",
            rag={"status": "no_match", "sources": []},
        )
        assert quyet_dinh.ly_do == "thieu_nguon", cau_hoi


def test_mac_dinh_coi_cau_hoi_la_nong_nghiep_tru_khi_co_dau_hieu_lac_de():
    """Ba lần đo thật, ba câu nông nghiệp bị trả lời "ngoài lĩnh vực nông
    nghiệp": tôm thẻ chân trắng, chôm chôm ra hoa trái vụ, và trước đó là
    trồng nho ngón tay.

    Nguyên nhân chung là hướng của luật: bắt câu hỏi phải CHỨNG MINH mình
    thuộc nông nghiệp bằng cách khớp một danh sách từ khoá. Danh sách nào
    cũng thiếu, và mỗi lần thiếu là một nông dân bị nói rằng câu hỏi nhà
    nông của họ lạc đề — hỏng nặng hơn hẳn việc trả nhầm "chưa đủ dữ liệu"
    cho một câu lạc đề thật.

    Trợ lý này chỉ làm nông nghiệp, nên mặc định đúng là coi mọi câu là nông
    nghiệp; từ chối theo phạm vi phải có bằng chứng lạc đề.
    """
    for cau_hoi in (
        "Quy trình xử lý ra hoa trái vụ cho chôm chôm áp dụng vào thời gian nào?",
        "Tôm thẻ chân trắng bị hoại tử gan tụy cấp thì kiểm soát ra sao?",
        "Mắc ca bị bọ xít muỗi chích thì xử lý thế nào?",
        "Sầu riêng xì mủ thân là do đâu?",
    ):
        quyet_dinh = danh_gia_grounding(
            cau_hoi=cau_hoi, intent="general_question",
            rag={"status": "no_match", "sources": []},
        )
        assert quyet_dinh.ly_do == "thieu_nguon", cau_hoi


def test_dau_hieu_lac_de_ro_rang_van_bi_tu_choi_theo_pham_vi():
    """Đảo mặc định không được làm cổng phạm vi thành vô dụng."""
    for cau_hoi in (
        "Thủ đô nước Pháp là gì?",
        "Viết giúp tôi một đoạn code Python sắp xếp mảng",
        "Tỷ số trận đấu tối qua thế nào?",
        "Hôm nay có phim gì hay ngoài rạp không?",
        "Kê khai thuế VAT cho doanh nghiệp nhỏ thế nào?",
    ):
        quyet_dinh = danh_gia_grounding(
            cau_hoi=cau_hoi, intent="general_question",
            rag={"status": "no_match", "sources": []},
        )
        assert quyet_dinh.ly_do == "ngoai_pham_vi", cau_hoi
