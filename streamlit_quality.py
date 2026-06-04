"""
Stage 7 — Streamlit UI: real-time fruit quality checker.

Calls the FastAPI backend at BACKEND_URL (default: http://localhost:5000).
No model loaded here — inference runs in the backend process.

Usage:
    cd d:\\HocTap\\Nam3\\NongNghiepAI
    streamlit run streamlit_quality.py
"""
import os
import tempfile

import cv2
import numpy as np
import requests
import streamlit as st
from PIL import Image

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")
YOLO_ENDPOINT = f"{BACKEND_URL}/api/quality/yolo-check"

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AgriAI — Kiểm tra chất lượng quả",
    page_icon="🍎",
    layout="wide",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

GRADE_BADGE = {
    "grade_1": ("🟢", "Loại 1"),
    "grade_2": ("🟡", "Loại 2"),
    "grade_3": ("🟠", "Loại 3"),
    "damaged": ("🔴", "Hỏng"),
}

GRADE_COLOR_BGR = {
    "grade_1": (34, 197, 94),
    "grade_2": (234, 179, 8),
    "grade_3": (249, 115, 22),
    "damaged": (239, 68, 68),
}


def call_yolo_api(image_bytes: bytes, filename: str, conf: float = 0.25) -> dict:
    try:
        resp = requests.post(
            YOLO_ENDPOINT,
            files={"image": (filename, image_bytes, "image/jpeg")},
            data={"conf": str(conf)},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        # unwrap api_response wrapper
        return payload.get("data") or payload
    except requests.exceptions.ConnectionError:
        return {"error": f"Không kết nối được backend tại {BACKEND_URL}"}
    except Exception as exc:
        return {"error": str(exc)}


def draw_boxes(image_rgb: np.ndarray, detections: list[dict]) -> np.ndarray:
    img = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        color = GRADE_COLOR_BGR.get(det["grade"], (150, 150, 150))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f"{det['fruit_type_vi']} {det['grade_label_vi']} {det['confidence']:.0%}"
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(img, (x1, y1 - h - 6), (x1 + w + 4, y1), color, -1)
        cv2.putText(img, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def render_results(result: dict, image_rgb: np.ndarray, source_label: str):
    if "error" in result:
        st.error(f"Lỗi: {result['error']}")
        st.image(image_rgb, caption=source_label, use_container_width=True)
        return

    detections = result.get("detections", [])
    summary = result.get("summary", {})

    col_img, col_info = st.columns([3, 2])
    with col_img:
        annotated = draw_boxes(image_rgb, detections)
        st.image(annotated, caption=source_label, use_container_width=True)

    with col_info:
        st.subheader(f"Kết quả — {summary.get('total', 0)} quả")
        if not detections:
            st.info("Không phát hiện quả nào. Thử ảnh rõ hơn hoặc điều chỉnh ngưỡng confidence.")
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟢 Loại 1", summary.get("grade_1", 0))
        c2.metric("🟡 Loại 2", summary.get("grade_2", 0))
        c3.metric("🟠 Loại 3", summary.get("grade_3", 0))
        c4.metric("🔴 Hỏng",   summary.get("damaged",  0))

        st.divider()

        for i, det in enumerate(detections):
            emoji, label_vi = GRADE_BADGE.get(det["grade"], ("⚪", det.get("grade_label_vi", "")))
            with st.expander(
                f"{emoji} Quả #{i+1} — {det['fruit_type_vi']} ({label_vi})  "
                f"tin cậy {det['confidence']:.0%}"
            ):
                lo, hi = det.get("price_range", (0, 0))
                c1, c2 = st.columns(2)
                c1.write(f"**Loại quả:** {det['fruit_type_vi']}")
                c1.write(f"**Chất lượng:** {det['grade_label_vi']}")
                if lo:
                    c1.write(f"**Giá tham khảo:** {lo:,} – {hi:,} VND/kg")

                c2.metric("YOLO", f"{det.get('yolo_confidence', 0):.0%}", help="Độ tin cậy nhận diện")
                c2.metric("EfficientNet", f"{det.get('efficientnet_confidence', 0):.0%}", help="CNN chấm chất lượng")
                c2.metric("HSV tươi", f"{det.get('hsv_freshness', 0):.0%}", help="Phân tích màu sắc")
                c2.write(f"Màu: **{det.get('hsv_color', '—')}** · Khuyết tật: **{det.get('hsv_defect_ratio', 0):.1%}**")
                top3 = det.get("efficientnet_top3", [])
                if top3:
                    c2.caption("Top-3 EfficientNet: " + " · ".join(f"{n} {p:.0%}" for n, p in top3))

                if det.get("reasoning"):
                    st.info(f"🔍 **Lý do phân loại:** {det['reasoning']}")

                if det.get("recommendation"):
                    st.success(f"✅ {det['recommendation']}")


# ── Main UI ────────────────────────────────────────────────────────────────────

st.title("🍎 AgriAI — Kiểm tra chất lượng quả")
st.caption(f"Model: YOLO11 fruit_quality · Backend: {BACKEND_URL}")

with st.sidebar:
    st.header("⚙️ Cài đặt")
    conf_threshold = st.slider("Ngưỡng confidence", 0.1, 0.9, 0.25, 0.05)
    st.caption("Giảm ngưỡng để phát hiện nhiều quả hơn (có thể nhầm hơn)")

tab_upload, tab_camera = st.tabs(["📁 Upload ảnh", "📷 Camera"])

with tab_upload:
    uploaded = st.file_uploader("Chọn ảnh quả (JPG/PNG)", type=["jpg", "jpeg", "png"])
    if uploaded:
        img = Image.open(uploaded).convert("RGB")
        img_arr = np.array(img)
        with st.spinner("Đang phân tích..."):
            result = call_yolo_api(uploaded.getvalue(), uploaded.name, conf=conf_threshold)
        render_results(result, img_arr, uploaded.name)

with tab_camera:
    st.info("Nhấn **Take Photo** để chụp và phân tích.")
    camera_img = st.camera_input("Camera")
    if camera_img:
        img = Image.open(camera_img).convert("RGB")
        img_arr = np.array(img)
        with st.spinner("Đang phân tích..."):
            result = call_yolo_api(camera_img.getvalue(), "camera.jpg", conf=conf_threshold)
        render_results(result, img_arr, "Camera snapshot")
