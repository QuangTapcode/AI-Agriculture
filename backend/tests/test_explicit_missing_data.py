"""
TDD: vùng được hỏi mà không có dữ liệu phải được nêu RÕ trong phần DỮ LIỆU.

Chốt chặn số liệu (so_lieu_khong_co_trong_nguon) chỉ bắt được số BỊA. Nó
không bắt được ca tinh vi hơn — model dùng lại đúng con số có trong nguồn
nhưng GÁN SAI VÙNG:

    DỮ LIỆU: "Cà phê Đắk Lắk: 96.433 đ/kg"
    Hỏi:     "Còn Gia Lai thì sao?"
    Trả lời: "Gia Lai cũng đang ở mức tương tự, là 96.433 đ/kg"   <-- sai

Model nhỏ tuân theo SỰ THẬT PHỦ ĐỊNH tường minh ("Gia Lai: chưa có dữ liệu")
tốt hơn nhiều so với lệnh cấm ("không được suy sang vùng khác").
"""
from app.integrations.ai_grounding import bo_sung_vung_thieu_du_lieu

DU_LIEU = "Cà phê Đắk Lắk: 96.433 đ/kg (cập nhật 22/08/2026)"


def test_neu_ro_vung_duoc_hoi_ma_khong_co_du_lieu():
    ket_qua = bo_sung_vung_thieu_du_lieu("Còn Gia Lai thì sao?", DU_LIEU)
    assert "Gia Lai" in ket_qua
    assert "chưa có dữ liệu" in ket_qua.lower()


def test_giu_nguyen_khi_vung_da_co_du_lieu():
    ket_qua = bo_sung_vung_thieu_du_lieu("Giá Đắk Lắk bao nhiêu?", DU_LIEU)
    assert ket_qua == DU_LIEU, "Không được thêm gì khi vùng đã có dữ liệu"


def test_nhan_ra_ten_vung_khong_dau():
    ket_qua = bo_sung_vung_thieu_du_lieu("gia ca phe o gia lai?", DU_LIEU)
    assert "chưa có dữ liệu" in ket_qua.lower()


def test_cau_hoi_khong_nhac_vung_nao_thi_giu_nguyen():
    ket_qua = bo_sung_vung_thieu_du_lieu("Cà phê tưới mấy lần một tuần?", DU_LIEU)
    assert ket_qua == DU_LIEU


def test_nhieu_vung_thieu_deu_duoc_neu():
    ket_qua = bo_sung_vung_thieu_du_lieu("So sánh Gia Lai với Lâm Đồng?", DU_LIEU)
    assert "Gia Lai" in ket_qua and "Lâm Đồng" in ket_qua
