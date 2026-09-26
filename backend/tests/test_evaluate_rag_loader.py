"""
TDD: script đánh giá phải chạy được cả hai bộ đề đang có trong repo.

- docs/challenge/evaluation.jsonl — bộ chính, mỗi câu kèm ground_truth và
  expected_source, dùng để đo chất lượng câu trả lời.
- docs/challenge/evaluation_questions.json — bộ đo cổng grounding, chia rõ ba
  nhóm và phủ đủ 20/20 tài liệu corpus.

Hai định dạng khác nhau. Viết hai script riêng thì luật chấm sẽ trôi khỏi
nhau; chuẩn hóa một lần lúc nạp thì phần chấm không cần biết bộ đề đến từ đâu.
"""
import json
from pathlib import Path

from scripts.evaluate_rag import _load_questions

ROOT = Path(__file__).resolve().parents[2]
BO_CHINH = ROOT / "docs" / "challenge" / "evaluation.jsonl"
BO_GROUNDING = ROOT / "docs" / "challenge" / "evaluation_questions.json"


def test_nap_duoc_bo_de_dang_json_co_truong_questions():
    bo_de = _load_questions(BO_GROUNDING)
    cac_cau = bo_de["questions"]

    assert len(cac_cau) == 30
    assert {item["category"] for item in cac_cau} == {"grounded", "no_source", "out_of_scope"}
    assert bo_de["version"]


def test_nap_duoc_bo_de_dang_jsonl_moi_dong_mot_cau():
    bo_de = _load_questions(BO_CHINH)
    cac_cau = bo_de["questions"]

    assert len(cac_cau) == 30
    assert all(item["id"] and item["question"] for item in cac_cau)
    assert bo_de["version"]


def test_cot_answerable_duoc_dich_sang_nhom_thieu_nguon():
    """answerable=false nghĩa là corpus không trả lời được — cùng ý với nhóm
    no_source của bộ kia, nên phải chấm bằng cùng một chuẩn."""
    cac_cau = _load_questions(BO_CHINH)["questions"]
    theo_ma = {item["id"]: item for item in cac_cau}

    assert theo_ma["q026"]["category"] == "no_source"
    assert theo_ma["q026"]["expected_behavior"] == "insufficient_data"
    assert theo_ma["q026"]["expected_doc_ids"] == []


def test_cau_lac_de_duoc_nhan_ra_truoc_khi_xet_answerable():
    """q030 (kê khai thuế VAT) vừa answerable=false vừa out_of_scope.

    Xét answerable trước thì nó thành "thiếu nguồn", và bài đánh giá sẽ chấp
    nhận câu trả lời "chưa đủ dữ liệu" cho một câu lẽ ra phải từ chối theo
    phạm vi — ngụ ý rằng nạp thêm tài liệu thuế thì trợ lý sẽ trả lời.
    """
    cac_cau = _load_questions(BO_CHINH)["questions"]
    theo_ma = {item["id"]: item for item in cac_cau}

    assert theo_ma["q030"]["category"] == "out_of_scope"
    assert theo_ma["q030"]["expected_behavior"] == "out_of_scope_refusal"


def test_cau_tra_loi_duoc_giu_lai_de_nguoi_duyet_doi_chieu():
    cac_cau = _load_questions(BO_CHINH)["questions"]
    theo_ma = {item["id"]: item for item in cac_cau}

    assert theo_ma["q001"]["ground_truth"]
    assert theo_ma["q001"]["expected_doc_ids"] == ["kn-01"]


def test_bo_khong_co_ground_truth_thi_truong_do_de_trong():
    cac_cau = _load_questions(BO_GROUNDING)["questions"]

    assert all(not item.get("ground_truth") for item in cac_cau)
