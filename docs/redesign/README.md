# Redesign AgriAI — Prototype A "Field Command"

Nhánh `feat/ui-field-command`. Toàn bộ sáu nhóm page đã hoàn thành.

## Trạng thái

| Nhóm | Nội dung | Báo cáo |
| --- | --- | --- |
| 1 | Header/Footer, Trang chủ, Tính năng, Đăng nhập/Đăng ký | trong lịch sử commit |
| 2 | Bài viết, Gói dịch vụ, Liên hệ, 404 | trong lịch sử commit |
| 3 | Sidebar/Navbar/app shell, Dashboard, Báo cáo | [group-3](group-3-app-shell-report.md) |
| 4 | Thời tiết, Định giá, Chi tiết cây trồng, Phân tích thị trường | [group-4](group-4-market-data-report.md) |
| 5 | Chất lượng, Thu hoạch, Mùa vụ, Cảnh báo, Thông báo | [group-5](group-5-operations-report.md) |
| 6 | Trợ lý AI, Kho tài liệu, Cài đặt, Hồ sơ | [group-6](group-6-ai-account-report.md) |

## Kết quả cuối

```
Frontend unit (Vitest)    28 file, 111 test — pass
Frontend e2e (Playwright) 164 test trên 4 khung hình — pass
Frontend build            pass
Backend (pytest)          478 pass, 7 skip, 1 fail có sẵn
```

Một test backend hỏng từ trước đợt này và không liên quan:
`test_port_convention.py::test_docker_expose_cong_chuan` đọc `docker-compose.yml`,
file mà toàn bộ đợt redesign không chạm tới (`git diff 0d3da45..HEAD` trên các
file docker cho kết quả rỗng).

Bốn khung hình nghiệm thu: 390×844, 768×1024, 1024×768, 1440×900.

## Ba mẫu lỗi lặp lại xuyên suốt

### 1. Thiếu dữ liệu bị trình bày thành số 0

Xuất hiện ở gần như mọi trang: `value || 0`, `value ?? 0`, state khởi tạo bằng
`0`. Hệ quả là "chưa gọi được API" và "giá trị thật bằng 0" trông giống hệt nhau.
Quy tắc nay nằm một chỗ trong `src/utils/format.js` (`hasValue`, `formatNumber`,
`formatConfidence`, `MISSING`) và ở backend trong `api_response`.

Nặng nhất: `getDashboardFullData` chặn trần độ tin cậy ở `0.78`, nên một giá trị
thật `0.91` từ backend bị ghi đè thành `0.78`.

### 2. Không có dữ liệu bị diễn giải thành trạng thái an toàn

- Trang Thời tiết ép số đo thiếu về `0` và nhiệt độ về `25`, rồi khuyên nông dân
  *"Ít mưa — thích hợp phun thuốc, bón phân"* từ một payload rỗng.
- `RiskBadge` mặc định "Rủi ro Thấp"; `thunderRisk` mặc định "Không có";
  xu hướng thị trường mặc định "Ổn định"; mùa vụ mặc định "Quanh năm".

Đây là loại lỗi tệ nhất trong đợt: không phải một con số xấu xí, mà là một lời
trấn an sai về điều kiện ngoài đồng.

### 3. Lưu nguyên phản hồi vào state rồi giả định hình dạng của nó

Ba trang (`/alerts`, `/ai-chat`, `/knowledge-documents`) sập hoàn toàn xuống
error boundary khi phản hồi thiếu một mảng. Quy ước rút ra: **chuẩn hóa hình
dạng ngay tại chỗ nhận, đừng tin phản hồi có đủ trường.**

## Ngoài ra

Bảng giá vùng miền ở `/crop/:cropId` vốn được **bịa ra**: khi API so sánh vùng
không trả dữ liệu, trang gán `typical_price_max` của cây trồng thành giá "Hà Nội"
và `typical_price_min` thành giá "Cần Thơ". Sáu route mockup cũ (`/dashboard-new`,
`/pricing-dashboard`, `/quality-check`, `/harvest-forecast`, `/market-strategy`,
`/alerts-management`) không gọi API nào, chỉ hardcode số liệu — đã redirect về
page chuẩn và xóa file.

Hai nút trên trang cây trồng (Chia sẻ, Đặt cảnh báo giá) không có handler — bấm
không làm gì. Nay nút cảnh báo dẫn sang `/alerts`, nút chia sẻ dùng Web Share API.

## Chạy lại

```bash
cd frontend
npm run check          # unit + build
npm run test:e2e       # e2e trên cả bốn khung hình

# Ảnh và video nghiệm thu cho một nhóm
EVIDENCE_GROUP=group-5-operations npm run evidence
cd ../docs/redesign/evidence/group-5-operations
for f in *.webm; do ffmpeg -y -i "$f" -c:v libx264 -preset slow -crf 23 \
  -pix_fmt yuv420p -movflags +faststart \
  -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" "${f%.webm}.mp4"; done
```

Ảnh/video nằm trong `docs/redesign/evidence/<nhóm>/`, không commit vào repo.

CI chạy `npm run check` và `npm run test:e2e` trên mỗi push và pull request. Bộ
sinh ảnh/video chỉ chạy khi có biến `EVIDENCE_GROUP`, nên không làm chậm CI.

## Nhãn triage và mẫu issue

Năm nhãn chuẩn nằm trong [`.github/labels.yml`](../../.github/labels.yml). Tạo
chúng trên GitHub sau khi đăng nhập một lần:

```bash
gh auth login
bash scripts/sync-github-labels.sh
```

Mẫu issue ở `.github/ISSUE_TEMPLATE/` đã bật (báo lỗi và đề xuất tính năng, cả
hai tự gắn `needs-triage`); issue trống bị tắt.

## Còn mở

- Chưa có test render riêng cho trạng thái `cached` và `live` trên từng trang;
  hợp đồng metadata đã được phủ ở `normalizeDataMeta` và tầng service.
- `unwrapApiResponse` trả về cả phong bì lẫn payload phẳng vì backend spread
  `dict(data)`. Đang chạy đúng nhưng dễ gây nhầm, nên tách ở một đợt riêng.
- Tiêu đề trang Thời tiết vẫn ghi "Theo dõi thời gian thực" — mô tả tính năng,
  không phải nhãn gắn lên một con số cụ thể.
- Chưa triển khai billing hoặc CMS: `/pricing-plans` và `/articles` giữ empty state.
