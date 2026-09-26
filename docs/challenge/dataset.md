# Challenge dataset

AgriAI dùng một tập tài liệu cố định gồm **20 tài liệu HTML công khai** từ Cổng Thông tin điện tử Trung tâm Khuyến nông Quốc gia (`khuyennongvn.gov.vn`). Tập dữ liệu bao phủ ba nhóm: trồng trọt, chăn nuôi và thủy sản tại Việt Nam.

Danh sách chính thức, URL canonical, metadata, độ dài văn bản sau chuẩn hóa và SHA-256 nằm trong [`dataset_manifest.json`](dataset_manifest.json). Không commit bản sao toàn văn của các trang nguồn; hệ thống tải lại từ URL, chuẩn hóa bằng cùng pipeline ingestion và đối chiếu SHA-256 trước khi index.

## Tiêu chí chọn

- Miền nguồn được allow-list và thuộc cổng khuyến nông chính thức.
- HTTP status `200` tại thời điểm chốt dataset.
- Văn bản sau khi loại bỏ phần giao diện có ít nhất 800 ký tự.
- Có tiêu đề, chủ đề/cây/vật nuôi và URL để citation.
- SHA-256 được ghi lại để phát hiện nội dung nguồn thay đổi.

## Kiểm tra offline

```powershell
backend\\venv\\Scripts\\python.exe scripts/verify_challenge_dataset.py
```

## Kiểm tra lại nguồn và hash

Lệnh này tải 20 URL, chạy bộ trích xuất HTML của backend và đối chiếu status, độ dài, SHA-256:

```powershell
backend\venv\Scripts\python.exe scripts/verify_challenge_dataset.py --remote
```

Nếu nguồn thay đổi, lệnh sẽ fail thay vì âm thầm coi dataset vẫn hợp lệ. Khi đó cần cập nhật manifest có review và ghi nhận ngày/version mới.
