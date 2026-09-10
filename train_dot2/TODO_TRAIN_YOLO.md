# TODO — Huấn luyện YOLO đợt tiếp theo

## Mục tiêu

Huấn luyện model kiểm định chất lượng nông sản từ **16 lớp hiện tại** lên tối đa
**96 lớp**: 24 loại nông sản × 4 mức chất lượng `Fresh`, `Semifresh`,
`Semirotten`, `Rotten`.

Không thay `backend/ai_models/weights/best.pt` cho đến khi model mới vượt toàn bộ
cổng đánh giá trong tài liệu này.

## Hiện trạng đã kiểm tra

- [x] Model production: `backend/ai_models/weights/best.pt`.
- [x] Model hiện tại là YOLO detection, có 16 lớp: Apple, Banana, Mango, Orange × 4 mức chất lượng.
- [x] Có checkpoint gốc `yolo11n.pt`, `yolo11s.pt`, `yolo11m.pt` trong `backend/`.
- [x] Có notebook `train_dot2/train_yolo11_dot2.ipynb`.
- [x] Có recipe tái lập trong `train_dot2/recipe.py`.
- [x] Có cấu trúc mục tiêu 96 lớp trong `train_dot2/data.yaml`.
- [ ] Dataset ảnh và label thật chưa nằm trong repository.
- [ ] Chưa có báo cáo baseline chuẩn trên một test set cố định.

## Quyết định về cấu hình train

- **Khuyến nghị:** train `HIGH_LEVEL` — YOLO11m, ảnh 768 px, batch 16, 120 epoch trên Colab T4 hoặc GPU có ít nhất khoảng 13 GB VRAM.
- **Train tại máy hiện tại:** dùng `LOCAL_4GB` — YOLO11s, ảnh 640 px, batch 8; nếu OOM giảm batch xuống 4.
- Không dùng YOLO11n làm model chính cho đợt mới; chỉ giữ làm baseline.
- Giữ augmentation màu nhẹ (`hsv_h=0.01`, `hsv_s=0.25`, `hsv_v=0.25`) vì màu sắc là tín hiệu phân biệt độ tươi/hỏng.
- Khi số lớp thay đổi từ 16 lên 96, bắt đầu từ backbone pretrained tương ứng (`yolo11m.pt` hoặc `yolo11s.pt`), không resume detection head 16 lớp cũ.

## Giai đoạn 1 — Chốt phạm vi và quy ước nhãn

- [ ] Chọn một trong hai phạm vi:
  - Pilot: 4 loại quả cũ + 5 loại rau củ ưu tiên = 36 lớp.
  - Đầy đủ: 4 loại quả cũ + 20 loại rau củ = 96 lớp.
- [ ] Với pilot, ưu tiên: cà chua, cà rốt, khoai tây, dưa leo và ớt chuông.
- [ ] Giữ nguyên index 0–15 của 16 lớp cũ trong mọi phiên bản dataset.
- [ ] Dùng đúng mẫu tên lớp: `<Crop> Fresh`, `<Crop> Semifresh`, `<Crop> Semirotten`, `<Crop> Rotten`.
- [ ] Viết hướng dẫn gán nhãn kèm ảnh mẫu cho bốn mức chất lượng:
  - `Fresh`: tươi, không có dấu hiệu hư hỏng rõ.
  - `Semifresh`: bắt đầu xuống màu hoặc hơi mềm, vẫn sử dụng tốt.
  - `Semirotten`: hư cục bộ rõ ràng, có đốm thâm hoặc nhũn một phần.
  - `Rotten`: hỏng nặng, mốc, chảy nước hoặc không còn sử dụng được.
- [ ] Chốt cách xử lý trường hợp khó: bị che khuất, cắt mất một phần, nhiều mức hỏng trên cùng một quả và vật thể quá nhỏ.
- [ ] Hai người gán nhãn thử cùng 100 ảnh; rà lại các ảnh bất đồng trước khi label hàng loạt.

**Hoàn thành khi:** danh sách class, thứ tự index và quy tắc bốn mức chất lượng không còn mơ hồ.

## Giai đoạn 2 — Thu thập và quản lý dữ liệu

- [ ] Tạo một project/version riêng trên Roboflow hoặc một kho dữ liệu có version.
- [ ] Nạp lại đầy đủ dữ liệu 16 lớp cũ để tránh catastrophic forgetting.
- [ ] Thu ảnh mới từ nhiều nguồn thực tế: điện thoại khác nhau, trong nhà/ngoài trời, nền sáng/tối, chợ, vườn và kho bảo quản.
- [ ] Mỗi lớp có tối thiểu 150 bounding box; mục tiêu 250–300 bounding box/lớp.
- [ ] Không để một trạng thái `Fresh` chiếm quá 40% dữ liệu của cùng loại nông sản.
- [ ] Bổ sung 5–10% ảnh nền không có nông sản mục tiêu để đo false positive.
- [ ] Bổ sung ca khó: nhiều vật thể, che khuất, vật thể nhỏ, ảnh rung/mờ vừa phải và ánh sáng yếu.
- [ ] Ghi metadata tối thiểu: nguồn, giấy phép, ngày chụp/tải, thiết bị, khu vực, loại nông sản và batch thu thập.
- [ ] Loại ảnh trùng và gần trùng bằng hash/perceptual hash trước khi chia tập.
- [ ] Không sử dụng ảnh không rõ quyền khai thác hoặc không truy được nguồn.

**Quy mô tham khảo:** 96 lớp × 150–300 box tương ứng khoảng 14.400–28.800 box đã kiểm tra.

## Giai đoạn 3 — Kiểm tra label và chia dữ liệu

- [ ] Kiểm tra mỗi file ảnh có file label tương ứng và ngược lại.
- [ ] Kiểm tra class index nằm trong khoảng hợp lệ, bbox không âm, không vượt biên và có diện tích lớn hơn 0.
- [ ] Rà trực quan ít nhất 10% ảnh của từng class; rà 100% class có ít dữ liệu.
- [ ] Tìm box quá lớn, quá nhỏ, box trùng và vật thể bị bỏ sót.
- [ ] Xuất báo cáo số ảnh/box theo class và theo mức chất lượng.
- [ ] Chia `train/valid/test` theo tỷ lệ 70/15/15.
- [ ] Chia theo phiên chụp hoặc vật thể gốc; không để các ảnh liên tiếp/cùng một quả lọt sang nhiều tập.
- [ ] Khóa test set sau khi chia; không dùng test set để chọn hyperparameter.
- [ ] Kiểm tra `data.yaml`: `nc` bằng đúng số phần tử trong `names` và đường dẫn tồn tại.
- [ ] Lưu dataset version và hash của file export.

**Hoàn thành khi:** không còn lỗi cấu trúc label, không rò rỉ dữ liệu và không có class thiếu validation/test.

## Giai đoạn 4 — Đo baseline trước khi train

- [ ] Chạy `backend/ai_models/weights/best.pt` trên test set cố định.
- [ ] Chạy thêm `BASELINE_NANO` để có mốc so sánh tái lập.
- [ ] Ghi lại:
  - mAP50-95, mAP50, precision và recall toàn bộ.
  - AP/precision/recall của từng class.
  - Confusion matrix giữa `Fresh ↔ Semifresh` và `Semirotten ↔ Rotten`.
  - Số false positive trên ảnh nền.
  - Recall theo kích thước vật thể nhỏ/vừa/lớn.
- [ ] Lưu ít nhất 30 ảnh lỗi đại diện cùng dự đoán của baseline.
- [ ] Đo thời gian inference và VRAM trên GTX 1650 với `conf=0.15`, `iou=0.7`, `augment=True`.

**Artifact cần lưu:** `metrics.json`, confusion matrix, PR curve, danh sách class yếu và thư mục ảnh lỗi.

## Giai đoạn 5 — Train thử và train chính

- [ ] Chạy smoke train 2–3 epoch để kiểm tra dataset, class index, VRAM và output trước khi train dài.
- [ ] Kiểm tra ảnh augmentation; dừng nếu màu làm thay đổi nhãn chất lượng.
- [ ] Chạy pilot 20–30 epoch và xem loss/mAP có học đúng trước khi dùng đủ 120 epoch.
- [ ] Train chính bằng `HIGH_LEVEL` trên Colab/GPU ≥13 GB; dùng `LOCAL_4GB` nếu chỉ có GTX 1650.
- [ ] Bật early stopping theo recipe (`patience=30`).
- [ ] Lưu cả `best.pt` và `last.pt`; không chỉ tải một file về sau khi train.
- [ ] Lưu đầy đủ thư mục run: `args.yaml`, `results.csv`, biểu đồ, confusion matrix và ảnh prediction.
- [ ] Ghi manifest của lần train:
  - Git commit.
  - Dataset project/version/hash.
  - Recipe và mọi tham số override.
  - Phiên bản Python, Ultralytics, PyTorch, CUDA và loại GPU.
  - Seed, thời gian bắt đầu/kết thúc và thời lượng train.

Notebook chạy chính: `train_dot2/train_yolo11_dot2.ipynb`.

## Giai đoạn 6 — Đánh giá model ứng viên

- [ ] Đánh giá `best.pt` trên test set đã khóa, không chỉ đọc kết quả validation.
- [ ] So sánh cùng một bảng với model production 16 lớp và baseline nano.
- [ ] Liệt kê 15 class yếu nhất theo mAP50-95.
- [ ] Xem thủ công false positive, false negative và nhầm mức chất lượng của từng class yếu.
- [ ] Kiểm tra riêng dữ liệu chụp bằng điện thoại và điều kiện thực tế tại Việt Nam.
- [ ] Chạy bộ ảnh hồi quy gồm các ảnh từng phát hiện sai trong ứng dụng.
- [ ] Kiểm tra nhiều vật thể, tiled detection và trường hợp YOLO không tìm thấy bbox.
- [ ] Đo inference trên GTX 1650; model phải chạy không OOM.

### Cổng chấp nhận đề xuất

- [ ] mAP50-95 toàn bộ cao hơn baseline ít nhất 0,05.
- [ ] Recall tại cấu hình production không thấp hơn model hiện tại.
- [ ] Không class nào có test support bằng 0.
- [ ] AP của 16 lớp cũ không giảm quá 0,03 so với baseline tương ứng.
- [ ] False positive trên ảnh nền không tăng quá 10%.
- [ ] Không có xu hướng chấm mọi ảnh thành `Fresh` hoặc `Rotten`.
- [ ] Tất cả lỗi nghiêm trọng đã được ghi lại cùng quyết định: bổ sung dữ liệu, sửa label hoặc chấp nhận có lý do.

Nếu chưa đạt một cổng, quay lại Giai đoạn 2–3; không sửa ngưỡng production để che chất lượng model.

## Giai đoạn 7 — Đồng bộ EfficientNet và ensemble

Pipeline production đang kết hợp YOLO + EfficientNet + HSV. Khi YOLO tăng lên 96 lớp:

- [ ] Chọn một phương án rõ ràng:
  - Train lại EfficientNet cùng 96 lớp; hoặc
  - Chỉ cho EfficientNet override các class mà nó thực sự hỗ trợ.
- [ ] Nếu train EfficientNet 96 lớp, xuất hai file:
  - `efficientnet_quality.pt`
  - `efficientnet_quality.classes.json` chứa đúng 96 tên theo đúng index.
- [ ] Kiểm tra ensemble không đổi loại nông sản hoặc mức chất lượng đúng thành nhãn sai.
- [ ] Chạy lại test pipeline, fallback full-image, crop hint, annotation và local-only.

**Không triển khai YOLO 96 lớp cùng EfficientNet 16 lớp nếu chưa có chính sách tương thích rõ ràng.**

## Giai đoạn 8 — Đóng gói và triển khai an toàn

- [ ] Tính SHA-256 của weights hiện tại và weights ứng viên.
- [ ] Sao lưu model production:
  - `best.pt` hiện tại.
  - `efficientnet_quality.pt` hiện tại.
- [ ] Đặt model ứng viên ở thư mục staging; không ghi đè trực tiếp trong lúc backend đang chạy.
- [ ] Nạp thử weights bằng Ultralytics và xác nhận đúng task, đúng số lớp, đúng tên lớp.
- [ ] Chạy các test liên quan đến weights và pipeline.
- [ ] Chạy API `/api/quality/yolo-check` với bộ ảnh smoke test.
- [ ] Kiểm tra ảnh annotation, kết quả grade, confidence và lịch sử lưu database.
- [ ] Thay `backend/ai_models/weights/best.pt` theo thao tác nguyên tử sau khi mọi cổng đều đạt.
- [ ] Rebuild/restart backend và kiểm tra log model loaded, không có fallback `model_unavailable`.
- [ ] Theo dõi 50–100 ảnh thực tế đầu tiên; lưu phản hồi sai vào hàng chờ gán nhãn cho đợt sau.
- [ ] Chuẩn bị rollback một lệnh về weights cũ.

## Definition of Done

- [ ] Dataset có version, nguồn và báo cáo chất lượng.
- [ ] Train tái lập được từ `recipe.py` và manifest.
- [ ] Model ứng viên vượt cổng đánh giá trên test set cố định.
- [ ] YOLO, EfficientNet và class mapping tương thích.
- [ ] Inference chạy ổn định trên GTX 1650 4 GB.
- [ ] API kiểm định chất lượng chạy qua Docker và website công khai.
- [ ] Weights cũ được sao lưu và rollback đã được thử.
- [ ] Báo cáo model ghi rõ phạm vi dữ liệu, class yếu và giới hạn sử dụng.

## Thứ tự thực hiện ngay

1. [ ] Chốt pilot 36 lớp hay đầy đủ 96 lớp.
2. [ ] Tạo/finalize project Roboflow và quy tắc nhãn.
3. [ ] Thu thập đủ dữ liệu, ưu tiên class mới và ảnh thực tế Việt Nam.
4. [ ] Kiểm tra label, chống trùng và chia tập không rò rỉ.
5. [ ] Đo baseline 16 lớp trên test set cố định.
6. [ ] Smoke train 3 epoch.
7. [ ] Train chính bằng YOLO11m trên Colab T4.
8. [ ] Đánh giá, sửa class yếu và train lại nếu cần.
9. [ ] Đồng bộ EfficientNet/ensemble.
10. [ ] Triển khai staging, kiểm tra API rồi mới thay weights production.
