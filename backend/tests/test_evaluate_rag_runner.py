"""
TDD: một lần chạy hỏng không được xoá kết quả của lần chạy tốt.

Đã xảy ra thật: chạy đánh giá ngay sau `docker compose up -d`, backend chưa
kịp khởi động, cả 60 lượt trả RemoteProtocolError — và vì file kết quả được
mở bằng "w" ngay từ đầu, hai bộ kết quả tốt trước đó bị thay bằng 60 dòng
lỗi. Đo lại được, nhưng mất nửa giờ chạy model.
"""
from pathlib import Path
from types import SimpleNamespace

from scripts.evaluate_rag import chay

ROOT = Path(__file__).resolve().parents[2]
BO_DE = ROOT / "docs" / "challenge" / "evaluation_questions.json"

# Cổng 9 (discard) đóng trên mọi máy — kết nối bị từ chối ngay, không phải chờ.
BACKEND_KHONG_TON_TAI = "http://127.0.0.1:9"


def _args(out: Path, **thay_doi):
    args = SimpleNamespace(
        base_url=BACKEND_KHONG_TON_TAI, wait=0.1, out=out, questions=BO_DE,
        only=None, limit=1, timeout=1.0, token=None,
    )
    for khoa, gia_tri in thay_doi.items():
        setattr(args, khoa, gia_tri)
    return args


def test_backend_chua_san_sang_thi_dung_lai_va_bao_loi(tmp_path):
    assert chay(_args(tmp_path / "ket_qua.jsonl")) == 1


def test_khong_dung_toi_file_ket_qua_cu(tmp_path):
    out = tmp_path / "ket_qua.jsonl"
    cu = '{"id": "q-01", "result": {"verdict": "pass"}}\n'
    out.write_text(cu, encoding="utf-8")

    chay(_args(out))

    assert out.read_text(encoding="utf-8") == cu


def test_khong_tao_file_moi_khi_chua_chay_duoc(tmp_path):
    out = tmp_path / "chua_ton_tai.jsonl"

    chay(_args(out))

    assert not out.exists()
