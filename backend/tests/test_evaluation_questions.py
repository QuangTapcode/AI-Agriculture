"""
Bộ câu hỏi đánh giá phải kiểm được TRƯỚC khi chạy evaluation thật.

Một lần chạy đánh giá gọi LLM 30 lần và mất vài phút. Phát hiện "câu này trỏ
sai doc id" hay "câu ngoài phạm vi lại bị phân loại thành câu hỏi giá" sau khi
chạy xong là quá muộn. Các test ở đây chạy trong một giây và không cần mạng.
"""
import json
from pathlib import Path

from app.services.ai_intent_service import classify_user_intent
from app.services.grounding_policy import danh_gia_grounding

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = json.loads(
    (ROOT / "docs" / "challenge" / "evaluation_questions.json").read_text(encoding="utf-8")
)
MANIFEST = json.loads(
    (ROOT / "docs" / "challenge" / "dataset_manifest.json").read_text(encoding="utf-8")
)
CAU_HOI = QUESTIONS["questions"]


def test_bo_cau_hoi_co_dung_30_cau_khong_trung():
    assert QUESTIONS["question_count"] == len(CAU_HOI) == 30
    assert len({item["id"] for item in CAU_HOI}) == 30
    assert len({item["question"].strip().lower() for item in CAU_HOI}) == 30


def test_ba_nhom_deu_co_du_so_luong_de_ket_luan():
    """Thiếu nhóm nào thì bài đánh giá mất khả năng phát hiện lỗi của nhóm đó."""
    dem = {}
    for item in CAU_HOI:
        dem[item["category"]] = dem.get(item["category"], 0) + 1

    assert dem["grounded"] >= 15, "Quá ít câu có nguồn thì không đo được chất lượng trả lời"
    assert dem["no_source"] >= 5, "Quá ít câu thiếu nguồn thì không đo được tính trung thực"
    assert dem["out_of_scope"] >= 3
    assert set(dem) == set(QUESTIONS["categories"])


def test_cau_co_nguon_deu_tro_toi_tai_lieu_co_that_trong_manifest():
    ma_tai_lieu = {doc["id"] for doc in MANIFEST["documents"]}

    for item in CAU_HOI:
        if item["category"] != "grounded":
            assert item["expected_doc_ids"] == [], item["id"]
            continue
        assert item["expected_doc_ids"], item["id"]
        for doc_id in item["expected_doc_ids"]:
            assert doc_id in ma_tai_lieu, f"{item['id']} trỏ tới {doc_id} không có trong corpus"


def test_moi_tai_lieu_trong_corpus_deu_duoc_hoi_it_nhat_mot_lan():
    """Corpus 20 tài liệu mà chỉ hỏi 5 cái thì 15 cái còn lại chưa từng được đo."""
    da_hoi = {doc_id for item in CAU_HOI for doc_id in item["expected_doc_ids"]}
    thieu = {doc["id"] for doc in MANIFEST["documents"]} - da_hoi

    assert not thieu, f"Chưa có câu hỏi nào chạm tới: {sorted(thieu)}"


def test_cau_ngoai_pham_vi_that_su_bi_cong_grounding_tu_choi():
    """Kiểm bộ câu hỏi bằng chính luật đang chạy, không bằng phỏng đoán.

    Bộ phân loại intent bắt từ khoá theo chuỗi con — "giá" trong câu hỏi giá
    Bitcoin sẽ đẩy nó sang nhánh phân tích giá và cổng phạm vi không xét tới.
    Test này bắt những câu như vậy ngay khi ai đó thêm vào bộ đề.
    """
    for item in CAU_HOI:
        if item["category"] != "out_of_scope":
            continue
        intent = classify_user_intent(item["question"])
        quyet_dinh = danh_gia_grounding(
            cau_hoi=item["question"],
            intent=intent,
            rag={"status": "no_match", "sources": []},
        )
        assert quyet_dinh.ly_do == "ngoai_pham_vi", (
            f"{item['id']} ({intent}) không rơi vào nhánh ngoài phạm vi: {item['question']}"
        )


def test_cau_thieu_nguon_duoc_coi_la_cau_hoi_nong_nghiep():
    """Ngược lại: câu nông nghiệp thật không được rơi nhầm vào 'lạc đề'."""
    for item in CAU_HOI:
        if item["category"] != "no_source":
            continue
        quyet_dinh = danh_gia_grounding(
            cau_hoi=item["question"],
            intent=classify_user_intent(item["question"]),
            rag={"status": "no_match", "sources": []},
        )
        assert quyet_dinh.ly_do == "thieu_nguon", (
            f"{item['id']} bị coi là ngoài phạm vi: {item['question']}"
        )


def test_hanh_vi_mong_doi_khop_voi_nhom():
    mong_doi = {
        "grounded": "answer_with_citation",
        "no_source": "insufficient_data",
        "out_of_scope": "out_of_scope_refusal",
    }
    for item in CAU_HOI:
        assert item["expected_behavior"] == mong_doi[item["category"]], item["id"]
