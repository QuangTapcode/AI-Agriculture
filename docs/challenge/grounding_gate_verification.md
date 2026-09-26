# Grounding gate verification sau khi sửa

Ngày chạy: 2026-09-26, Asia/Bangkok.

Đây là lần kiểm tra tập trung cho tiêu chí “từ chối khi thiếu thông tin”, chạy qua
đúng endpoint người dùng gọi (`POST /api/ai-chat/message`) trên backend mới khởi
động, với bộ câu hỏi cố định [`evaluation.jsonl`](evaluation.jsonl).

| Nhóm | Câu hỏi | Kết quả strict |
|---|---|---:|
| `no_source` | q026–q029 | **4/4 pass** |
| `out_of_scope` | q030 | **1/1 pass** |
| Tổng | q026–q030 | **5/5 pass** |

Kết quả thô:

- [`evaluation_results_post_fix_no_source.jsonl`](evaluation_results_post_fix_no_source.jsonl)
- [`evaluation_results_post_fix_out_of_scope.jsonl`](evaluation_results_post_fix_out_of_scope.jsonl)

## Điều được xác minh

- Câu hỏi về liều thuốc không được dùng tài liệu chỉ nói biện pháp phòng trừ để
  suy ra dosage.
- Giá hiện tại không được dùng tin thị trường hoặc số liệu không đúng scope để
  trả lời.
- Dự báo định lượng tương lai không được model tự đoán khi không có số liệu.
- Retrieval trả về tài liệu cây khác không được coi là evidence của crop đang hỏi.
- Câu ngoài phạm vi nông nghiệp bị trả về `ngoai_pham_vi`, không bị trộn với lý do
  `thieu_nguon`.

Trong các ca pass, grounding gate chặn trước bước gọi model khi thiếu bằng chứng.
Các câu answerable trong bộ 30 câu vẫn cần human review nội dung; kết quả 5/5 ở
đây chỉ kết luận hành vi refusal/scope, không thay thế đánh giá semantic.

## Lệnh tái chạy

```powershell
$env:PYTHONUTF8 = "1"
backend\venv\Scripts\python.exe scripts\evaluate_rag.py `
  --base-url http://127.0.0.1:8013 `
  --questions docs\challenge\evaluation.jsonl `
  --only no_source `
  --out docs\challenge\evaluation_results_post_fix_no_source.jsonl

backend\venv\Scripts\python.exe scripts\evaluate_rag.py `
  --base-url http://127.0.0.1:8013 `
  --questions docs\challenge\evaluation.jsonl `
  --only out_of_scope `
  --out docs\challenge\evaluation_results_post_fix_out_of_scope.jsonl
```
