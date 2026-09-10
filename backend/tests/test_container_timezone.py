"""
Container phải chạy giờ Việt Nam.

Backend chạy trong container mặc định UTC, trong khi người dùng ở UTC+7.
Hệ quả đã đo được:

    recorded_at = 2026-09-09T17:00:00   (UTC)
    đồng hồ máy  = 2026-09-10T00:00     (giờ Hà Nội)

Số liệu đúng — 17:00 UTC CHÍNH LÀ 00:00 giờ Việt Nam — nhưng người dùng
nhìn mốc giờ sẽ tưởng dữ liệu cũ 7 tiếng. Chính tôi cũng đọc nhầm mốc này
và kết luận sai ở lần chẩn đoán đầu tiên.

Celery đã cấu hình timezone='Asia/Ho_Chi_Minh' nhưng đó chỉ áp cho lịch
beat, không đổi đồng hồ hệ thống mà datetime.now() đọc.
"""
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]


def test_compose_dat_mui_gio_viet_nam():
    compose = (GOC / "docker-compose.yml").read_text(encoding="utf-8")

    assert "Asia/Ho_Chi_Minh" in compose, (
        "docker-compose không đặt TZ — container chạy UTC, mọi mốc thời gian "
        "hiển thị lệch 7 tiếng so với đồng hồ người dùng"
    )


def test_ca_backend_va_worker_deu_duoc_dat():
    """Worker ghi FetchedAt vào DB; lệch múi giờ với backend là lệch dữ liệu."""
    compose = (GOC / "docker-compose.yml").read_text(encoding="utf-8")

    assert compose.count("Asia/Ho_Chi_Minh") >= 2, (
        f"Chỉ {compose.count('Asia/Ho_Chi_Minh')} service được đặt TZ — "
        f"backend và worker phải cùng múi giờ"
    )
