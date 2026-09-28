# Verification report — 2026-09-29

## Phạm vi

Lần chạy này kiểm tra bản Docker đang phục vụ tại http://127.0.0.1:8000
và gọi đúng endpoint người dùng gọi:

- GET /health
- GET /docs
- POST /api/ai-chat/message
- Frontend local qua Vite + Playwright

Môi trường runtime:

| Thành phần | Giá trị |
| --- | --- |
| Backend | Docker Compose, port 8000, health healthy |
| Database | SQL Server container |
| Cache | Redis container |
| AI provider | Ollama |
| Model sinh câu trả lời | qwen3:4b-instruct |
| Dataset | evaluation_questions.json, 30 câu |
| Ngày chạy | 2026-09-29, Asia/Bangkok |

## Smoke test ứng dụng

Smoke test Playwright kiểm tra:

- Backend /health trả HTTP 200 và status=healthy.
- Swagger /docs trả HTTP 200.
- Landing page frontend trả HTTP 200.
- Route /login render body không rỗng.
- Không có lỗi browser console.
- Screenshot được lưu local tại .local/verification/2026-09-29/local-app-smoke.png.

Kết quả: **pass**.

## Evaluation 30 câu

| Nhóm | Số câu | pass | needs_review | fail | Ghi chú |
| --- | ---: | ---: | ---: | ---: | --- |
| grounded | 20 | 0 | 20 | 0 | Citation tự động có, retrieval hit 14/20; cần duyệt semantic |
| no_source | 6 | 1 | 5 | 0 | 1 câu bị grounding gate chặn; 5 câu có evidence gần chủ đề |
| out_of_scope | 4 | 4 | 0 | 0 | Scope refusal đúng |
| Tổng | 30 | 5 | 25 | 0 | Không có fail tự động |

Latency của cả 30 lượt:

- p50: 22,901.8 ms
- p95: 34,610.9 ms
- max: 41,388.8 ms

Các file raw chỉ giữ trong workspace local để tránh nhầm với benchmark cũ:

- .local/verification/2026-09-29/evaluation_2026-09-29_grounded.jsonl
- .local/verification/2026-09-29/evaluation_2026-09-29_no_source.jsonl
- .local/verification/2026-09-29/evaluation_2026-09-29_out_of_scope.jsonl

## Đối chiếu tiêu chí challenge

| Tiêu chí | Trạng thái | Bằng chứng |
| --- | --- | --- |
| Dataset ít nhất 20 tài liệu | Đạt | Manifest có 20 tài liệu, URL/hash/metadata; test schema pass |
| Ingestion: parse → chunk → embedding → Chroma | Đạt ở local | verify_challenge_dataset.py, ingest_challenge_dataset.py, Chroma service |
| Search/retrieval | Đạt | Chroma vector + BM25 lexical + RRF ranking |
| Answer + citation | Đạt về contract | 20/20 grounded có citation tự động; semantic vẫn cần human review |
| Từ chối khi thiếu thông tin | Một phần | 1/6 strict pass; 5/6 cần cải thiện answerability |
| 30 câu evaluation | Đạt | 20 grounded + 6 no_source + 4 out_of_scope |
| Evaluation report | Đạt | Báo cáo này và docs/challenge/evaluation_report.md |
| Experiment ít nhất 2 cách | Đạt | Chunk 300 vs 800 trong experiment_report.md |
| README + AI_WORKLOG | Đạt | Root README và AI_WORKLOG.md đã cập nhật |
| Demo account public | Chưa xác minh | Local seed account không chứng minh public login |
| Public video | Chưa có bằng chứng | Cần link video công khai trước khi submit |

## Kết luận

AgriAI đạt yêu cầu về cấu trúc sản phẩm RAG, dataset, ingestion, retrieval,
citation, evaluation và out-of-scope refusal. Chưa đạt trạng thái “đạt toàn bộ”
cho submission vì:

1. 20 câu có nguồn chưa được người duyệt xác nhận semantic.
2. Nhóm thiếu nguồn mới có 1/6 strict pass.
3. Public demo account và video chưa có bằng chứng runtime công khai.
