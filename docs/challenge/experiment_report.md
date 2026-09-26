# Chunk-size experiment report

## Câu hỏi thực nghiệm

So sánh hai cấu hình chunking trên cùng 30 câu trong [`evaluation.jsonl`](evaluation.jsonl):

- A: chunk size 300, overlap 45 — 334 chunks cho 20 tài liệu.
- B: chunk size 800, overlap 120 — 129 chunks cho 20 tài liệu.
- Cùng embedding `embeddinggemma`, `RAG_TOP_K=4`, model `qwen2.5:3b-instruct-q4_K_M`, context 8192, output tối đa 256 tokens.
- Mỗi cấu hình có Chroma storage riêng và chạy qua cùng endpoint `POST /api/ai-chat/message`.

Kết quả đầy đủ, gồm từng câu trả lời/citation/timing, nằm ở [`experiment_chunk_300.json`](experiment_chunk_300.json) và [`experiment_chunk_800.json`](experiment_chunk_800.json).

## So sánh số liệu

| Metric | Chunk 300 | Chunk 800 | Nhận xét |
| --- | ---: | ---: | --- |
| Số chunks | 334 | 129 | 300 tạo locality nhỏ hơn, index lớn hơn |
| Answer: correct / acceptable / wrong | 1 / 26 / 3 | 0 / 27 / 3 | `acceptable` vẫn cần human review |
| Hit@K | 24/25 = 96.0% | 25/25 = 100.0% | 800 tốt hơn 4 điểm % |
| Recall@K | 27/30 = 90.0% | 28/30 = 93.3% | 800 tốt hơn 3.3 điểm % |
| Đủ toàn bộ expected sources | 22/25 = 88.0% | 23/25 = 92.0% | 800 tốt hơn 4 điểm % |
| Citation đúng nguồn (có ít nhất một nguồn đúng) | 24/25 | 25/25 | Cả hai không thiếu citation |
| Citation thiếu | 0/25 | 0/25 | — |
| Citation sai-only | 1/25 | 0/25 | 800 không có câu chỉ trích sai nguồn |
| Có citation dư ngoài expected | 11/25 | 18/25 | 300 precision citation tốt hơn |
| Strict no-answer accuracy | 1/5 = 20% | 0/5 = 0% | Cần sửa grounding gate, không nên chọn theo metric này một mình |
| Retrieval p50 / p95 | 2,298 / 2,442 ms | 2,324 / 3,386 ms | 300 nhanh hơn, nhất là p95 |
| Generation p50 / p95 | 7,394 / 20,661 ms | 10,117 / 12,459 ms | 300 có p50 tốt hơn; 800 ổn định hơn p95 |
| Tổng p50 / p95 | 9,666 / 23,066 ms | 12,427 / 21,118 ms | 300 nhanh hơn p50; 800 tốt hơn p95 |

## Vì sao kết quả khác nhau?

Chunk 300 chia tài liệu thành nhiều đoạn nhỏ, nên mỗi đoạn tập trung hơn vào một ý. Điều này làm retrieval nhanh hơn và giảm số citation ngoài mục tiêu, nhưng có thể làm mất liên kết giữa các ý nằm xa nhau; q007, q021 và q024 còn thiếu một nguồn kỳ vọng.

Chunk 800 giữ được nhiều ngữ cảnh trong mỗi đoạn và giảm số lượng vector khoảng 61%. Vì vậy Hit@K/Recall@K và độ ổn định citation đúng nguồn tăng nhẹ. Đổi lại, đoạn lớn chứa nhiều chủ đề lân cận hơn, làm 18/25 câu có citation dư; prompt gửi cho model cũng thường dài hơn, kéo p50 generation/tổng latency lên.

## Kết luận thực nghiệm

Không có cấu hình thắng tuyệt đối. Nếu ưu tiên recall nguồn, chọn chunk 800; nếu ưu tiên latency p50 và citation precision, chunk 300 có lợi thế. Với demo hiện tại, chọn 800 làm cấu hình báo cáo vì không bỏ sót nguồn ở Hit@K, nhưng cần thêm reranking/MRR hoặc giới hạn citation theo expected evidence để xử lý nguồn dư. Cả hai cấu hình đều chưa đạt no-answer strict accuracy, nên đây là blocker chất lượng cần sửa độc lập với chunk size.

## Cách tái chạy

```powershell
# Cấu hình runtime
$env:RAG_CHUNK_SIZE = "300"
$env:RAG_CHUNK_OVERLAP = "45"

# Index vào storage riêng, khởi động backend với cùng biến môi trường,
# rồi chạy evaluator:
backend\venv\Scripts\python.exe scripts\ingest_challenge_dataset.py
backend\venv\Scripts\python.exe scripts\evaluate_rag.py `
  --base-url http://127.0.0.1:8010 `
  --questions docs/challenge/evaluation.jsonl `
  --out docs/challenge/experiment_chunk_300.jsonl
backend\venv\Scripts\python.exe scripts\summarize_evaluation.py `
  docs/challenge/experiment_chunk_300.jsonl `
  docs/challenge/experiment_chunk_300.json --chunk-size 300 --overlap 45
```

Đổi storage/port và hai giá trị chunk thành 800/120 để chạy cấu hình B. Không dùng chung Chroma storage giữa hai experiment.
