# Hướng dẫn Train Đợt 2 — Fruits + Vegetables Quality (YOLO11, 96 class)

## Tổng quan

| Mục | Đợt 1 (đã có) | Đợt 2 (mục tiêu) |
|---|---|---|
| Model | YOLO11n | YOLO11n (train tiếp từ `best.pt`) |
| Số loại | 4 quả | 4 quả + **20 rau củ** |
| Mức chất lượng | Fresh / Semifresh / Semirotten / Rotten | giữ nguyên 4 mức |
| Tổng class | 16 | **96** (16 + 20×4) |

Kết quả cuối: **1 model duy nhất** nhận diện cả quả lẫn rau củ kèm đánh giá độ tươi/hỏng.

---

## Lưu ý quan trọng trước khi bắt đầu

**1. Catastrophic forgetting.** Không train chỉ trên 20 loại mới — model sẽ quên 16 class cũ. Bắt buộc **gộp ảnh đợt 1 + đợt 2** rồi train chung. (Đây là lý do cần lấy lại dataset đợt 1 trên Roboflow.)

**2. Khối lượng label rất lớn.** 80 class mới, mỗi class nên có tối thiểu **150–300 ảnh đã gán bounding box** → khoảng **12.000–24.000 ảnh** cần label. Đây là phần tốn công nhất. Gợi ý chia nhỏ: làm trước 5 loại → train thử → rồi mở rộng dần, thay vì làm hết 20 loại cùng lúc.

**3. File `efficientnet_quality.pt` bạn upload bị 0 byte** (tải lỗi). Nếu pipeline đợt 1 có dùng EfficientNet riêng để phân loại chất lượng thì cần tải lại. Nhưng với hướng "1 model YOLO 96 class" thì **không cần** file này.

---

## Quy trình 5 bước

### Bước 1 — Thu thập ảnh 20 loại rau củ

Mỗi loại cần ảnh ở **cả 4 trạng thái** (tươi → hỏng dần). Nguồn:

- **Tự chụp** (tốt nhất): chụp rau củ thật ở các độ tươi khác nhau, nhiều góc/ánh sáng/nền. Để vài ngày cho héo/hỏng rồi chụp tiếp cùng quả đó.
- **Bộ dữ liệu công khai:** tìm trên **Roboflow Universe** (universe.roboflow.com), **Kaggle** ("fruit vegetable fresh rotten"), Open Images.
- **Crawl web:** dùng từ khoá EN + VI ("fresh tomato", "cà chua hỏng"…).

Mục tiêu khởi đầu: ~200 ảnh/loại, cân đối giữa 4 mức (đừng để 90% ảnh "Fresh").

### Bước 2 — Gán nhãn (label) bằng Roboflow ⭐ khuyến nghị

Vì đợt 1 đã ở Roboflow, cách sạch nhất:

1. Mở **chính project Roboflow đợt 1** (`Fruits-Quality-Analysis`).
2. **Thêm 80 class mới** (Tomato Fresh, Tomato Rotten, … — xem `data.yaml`). Giữ nguyên 16 class cũ ở đầu.
3. Upload ảnh 20 loại mới → vẽ **bounding box** quanh từng rau củ, chọn đúng class theo độ tươi.
4. Quy ước gán mức chất lượng cho nhất quán:
   - **Fresh** — tươi hoàn toàn, không tì vết.
   - **Semifresh** — bắt đầu xuống màu/hơi mềm, còn dùng được.
   - **Semirotten** — hư rõ một phần (đốm thâm, nhũn cục bộ).
   - **Rotten** — hỏng nặng, mốc/chảy nước.
5. **Generate version** → áp dụng augmentation nhẹ (flip, xoay ≤15°, đổi sáng) → **Export định dạng `YOLOv11`**.

> Làm theo cách này, Roboflow tự quản class index và xuất 1 dataset gộp sẵn — **không cần** `merge_datasets.py`.

*Thay thế:* nếu muốn label offline, dùng **LabelImg** hoặc **label-studio** (export YOLO txt), rồi gộp bằng `merge_datasets.py`.

### Bước 3 — Gộp dataset (chỉ khi export riêng)

Nếu bạn export đợt 1 và đợt 2 thành 2 thư mục riêng:

```bash
pip install pyyaml
python merge_datasets.py --d1 ./fruits_dot1 --d2 ./veg_dot2 --out ./fruits-veg-quality
```

Script tự remap index (đợt 1: 0–15, đợt 2: 16–95) và sinh `data.yaml` gộp.

### Bước 4 — Train tiếp từ `best.pt`

Mở **`train_yolo11_dot2.ipynb`** trên **Google Colab** (Runtime → GPU T4), chạy lần lượt các cell:

1. Cài ultralytics + roboflow
2. Upload `best_dot1.pt` (đã copy sẵn trong thư mục này)
3. Tải dataset gộp từ Roboflow (điền API key)
4. Kiểm tra `nc = 96`
5. `model.train(...)` — 80 epochs, transfer từ checkpoint đợt 1
6. Đánh giá mAP + confusion matrix + **liệt kê class yếu nhất**
7. Test ảnh
8. Tải `best.pt` đợt 2 về

Cấu hình train đã đặt sẵn (epochs 80, imgsz 640, batch 16 — giảm còn 8 nếu hết VRAM, augmentation nhẹ).

### Bước 5 — Đánh giá & lặp lại

- Xem `confusion_matrix_normalized.png`: nếu 2 mức cạnh nhau (vd Semifresh ↔ Semirotten) hay nhầm → cần định nghĩa rõ ranh giới + thêm ảnh.
- Cell "class yếu nhất" chỉ ra loại nào mAP thấp → ưu tiên bổ sung/label lại ảnh cho loại đó.
- Train lại từ `best.pt` mới sau khi bổ sung dữ liệu.

---

## File trong thư mục này

| File | Công dụng |
|---|---|
| `best_dot1.pt` | Checkpoint YOLO11 đợt 1 (16 class) — dùng làm điểm xuất phát |
| `data.yaml` | Cấu trúc 96 class mục tiêu (sửa tên 20 loại tuỳ ý) |
| `train_yolo11_dot2.ipynb` | Notebook train trên Colab |
| `merge_datasets.py` | Gộp 2 dataset YOLO + remap index (chỉ dùng khi export riêng) |
| `HUONG_DAN.md` | File này |

---

## 20 loại rau củ đề xuất (sửa được)

Cà chua, cà rốt, khoai tây, dưa leo, ớt chuông, bắp cải, súp lơ trắng, bông cải xanh, cà tím, hành tây, tỏi, ớt, khổ qua, bí đỏ, bí ngòi, xà lách, rau bina, bắp/ngô, củ cải, khoai lang.

> Muốn đổi danh sách: sửa phần `names` (index 16–95) trong `data.yaml` và đặt class tương ứng trong Roboflow.
