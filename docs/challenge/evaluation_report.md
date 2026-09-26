# Evaluation report

Ngày chạy: 2026-09-26 (Asia/Bangkok). Báo cáo chính dùng kết quả chunk `800`, vì đây là cấu hình có Recall@K cao hơn trong experiment. Dữ liệu thô và metrics đầy đủ nằm trong [`experiment_chunk_800.json`](experiment_chunk_800.json); bộ câu hỏi là [`evaluation.jsonl`](evaluation.jsonl).

## Phạm vi và cách chấm

- 30 câu: 20 câu một tài liệu, 5 câu nhiều tài liệu, 5 câu thiếu dữ liệu hoặc ngoài phạm vi.
- 25 câu answerable được dùng cho retrieval/citation.
- `pass` là kiểm tra máy đạt; `needs_review` là câu có hình thức grounding/citation đạt nhưng chưa được người đọc xác nhận nội dung; `fail` là kiểm tra máy thất bại.
- Vì chưa duyệt thủ công toàn bộ câu trả lời, không gọi `needs_review` là “đúng tuyệt đối”.

## Answer quality

| Kết luận máy | Số câu | Tỷ lệ |
| --- | ---: | ---: |
| Đúng theo kiểm tra tự động (`pass`) | 0 | 0% |
| Chấp nhận được về hình thức, cần người duyệt (`needs_review`) | 27 | 90.0% |
| Sai theo kiểm tra tự động (`fail`) | 3 | 10.0% |

Ba câu `fail` là q004, q029 và q030. Các câu còn lại chưa được gắn nhãn nội dung cuối cùng vì cần human review.

## Retrieval quality

Runtime dùng `RAG_TOP_K=4`, embedding `embeddinggemma`, chunk size 800 và overlap 120.

| Chỉ số | Kết quả |
| --- | ---: |
| Hit@K — có ít nhất một nguồn kỳ vọng | 25/25 = 100.0% |
| Recall@K — nguồn kỳ vọng được truy hồi | 28/30 = 93.3% |
| Câu lấy đủ toàn bộ expected sources | 23/25 = 92.0% |

Hai câu còn thiếu một nguồn kỳ vọng là q021 và q024. Đây là các câu so sánh nhiều tài liệu; hệ thống lấy được ít nhất một tài liệu liên quan nhưng chưa lấy đủ cả cặp.

## Citation quality

| Loại | Số câu |
| --- | ---: |
| Có citation đúng ít nhất một nguồn kỳ vọng | 25/25 |
| Thiếu citation | 0/25 |
| Chỉ citation sai nguồn | 0/25 |
| Có thêm citation ngoài expected source | 18/25 |
| Bộ citation khớp chính xác expected source set | 7/25 |

Như vậy hệ thống luôn chỉ ra được ít nhất một nguồn đúng trong nhóm answerable, nhưng còn trích dẫn dư nguồn gần chủ đề. Đây là vấn đề precision của retrieval/citation, không phải thiếu citation.

## No-answer accuracy — baseline trước khi sửa

Có 5 câu không có nguồn kỳ vọng. Kết quả dưới đây là baseline chunk 800 trước khi sửa cổng grounding; chấm strict chỉ tính `pass` là từ chối đúng:

- Đúng: 0/5 = 0% ở cấu hình 800.
- Nhóm `no_source`: 0/4.
- Nhóm `out_of_scope`: 0/1.

Q026–q028 có lúc model tự nói chưa đủ dữ liệu nhưng cổng grounding vẫn để `ready`, nên chỉ được `needs_review`, không tính là pass. Q029 trả lời theo hướng không đủ dữ liệu và pass ở cấu hình 300 nhưng không pass ở cấu hình 800. Q030 chưa phân biệt đúng từ chối ngoài phạm vi. Đây là baseline trước khi sửa, không phải kết quả hiện tại.

## Post-fix grounding gate verification

Chạy lại đúng endpoint `POST /api/ai-chat/message` trên backend mới khởi động ngày 2026-09-26, dùng bộ câu hỏi `evaluation.jsonl`: q026–q029 đạt **4/4** strict pass cho `no_source`, q030 đạt **1/1** strict pass cho `out_of_scope`. Các ca bị chặn bởi policy trước khi gọi model; chi tiết request/response nằm trong [`grounding_gate_verification.md`](grounding_gate_verification.md).

## Latency

Đơn vị: milliseconds. `n` nhỏ hơn 30 ở stage không chạy cho câu bị chặn sớm.

| Stage | n | p50 | p95 | max |
| --- | ---: | ---: | ---: | ---: |
| Retrieval | 29 | 2,323.8 | 3,386.3 | 3,973.1 |
| Generation | 28 | 10,117.4 | 12,458.6 | 22,656.4 |
| Tổng request | 29 | 12,426.8 | 21,117.8 | 25,032.2 |

Tổng request không có ở câu out-of-scope bị từ chối trước retrieval; generation không có ở các lượt không gọi model.

## Failure analysis

Các số dưới đây là phân loại heuristic từ `retrieved_doc_ids`, `citations`, `grounding.reason` và verdict; chúng không thay thế human review nội dung.

| Nhóm lỗi | Số lượt | Bằng chứng chính |
| --- | ---: | --- |
| Retrieval | 2 | q021, q024 thiếu một expected source |
| Chunking/top-k | 2 | Cùng q021, q024: có nguồn đúng nhưng chưa đủ cặp tài liệu multi-document |
| Prompt/grounding gate | 5 baseline | Toàn bộ nhóm no-answer chưa đạt strict refusal trước khi sửa |
| Model/content review | 24 | Câu grounded cần người kiểm tra câu trả lời có bám ground truth không |
| Request/transport | 0 | Không có request error |

## Kết luận

Chunk 800 có recall tốt và luôn lấy được ít nhất một nguồn đúng, nhưng baseline sinh nhiều citation dư và no-answer gate chưa đạt. Cổng từ chối đã được sửa và có regression evidence riêng; bước tiếp theo là reranking hoặc diversity filter để giảm nguồn gần chủ đề không cần thiết. So sánh định lượng giữa chunk 300 và 800 nằm trong [`experiment_report.md`](experiment_report.md).
