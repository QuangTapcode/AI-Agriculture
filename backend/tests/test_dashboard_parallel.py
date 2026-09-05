"""
TDD: các khối độc lập của dashboard chạy song song, mỗi luồng một session.

Đo thực tế: lần gọi nguội /api/dashboard/summary mất 6.7s trong khi 28
endpoint còn lại chỉ 2-600ms. Nguyên nhân: featured_crop, weather_risk,
price_trend, market_news, regional_prices chạy nối đuôi dù độc lập.

Test nhắm đúng hợp đồng đã thay đổi — bộ chạy song song. Không đo tổng thời
gian get_summary vì trong đó còn phần tuần tự khác chưa đụng tới; đo cả cụm
sẽ khiến test đo lẫn thứ mình không sửa.
"""
import threading
import time

from app.services.dashboard_service import dashboard_service

TRE = 0.4
SO_JOB = 5


def _job(_ten):
    def fn(_sess):
        time.sleep(TRE)
        return {"ok": True}
    return fn


def test_cac_khoi_chay_dong_thoi():
    jobs = {f"job{i}": (_job(i), {}) for i in range(SO_JOB)}

    t0 = time.monotonic()
    ket_qua = dashboard_service._run_dashboard_jobs(jobs, [])
    mat = time.monotonic() - t0

    assert set(ket_qua) == set(jobs), "Thiếu kết quả của một số khối"
    assert mat < TRE * 2, (
        f"{SO_JOB} khối x {TRE}s mất {mat:.2f}s — có vẻ vẫn nối đuôi "
        f"(song song phải quanh {TRE}s)"
    )


def test_moi_khoi_chay_tren_luong_rieng():
    """Mỗi luồng phải có DB session riêng — Session không thread-safe."""
    luong = set()

    def fn(sess):
        luong.add(threading.get_ident())
        time.sleep(0.1)
        assert sess is not None, "Khối không được cấp session"
        return {}

    jobs = {f"job{i}": (fn, {}) for i in range(4)}
    dashboard_service._run_dashboard_jobs(jobs, [])

    assert len(luong) > 1, f"Tất cả chạy trên 1 luồng: {luong}"


def test_mot_khoi_hong_khong_lam_chet_ca_dashboard():
    """Một card lỗi không được kéo đổ toàn trang (TOD0 §6)."""
    def no(_sess):
        raise RuntimeError("nguon ngoai chet")

    def ok(_sess):
        return {"gia": 96433}

    jobs = {"hong": (no, {"fallback": True}), "tot": (ok, {})}
    ket_qua = dashboard_service._run_dashboard_jobs(jobs, [])

    assert ket_qua["tot"]["gia"] == 96433, "Khối tốt bị ảnh hưởng bởi khối hỏng"
    assert ket_qua["hong"].get("fallback") is True, "Khối hỏng không dùng fallback"
