# AI worklog

## Công cụ đã dùng

- ChatGPT/Codex: phân tích yêu cầu challenge, lập checklist, viết test, script evaluator và tài liệu.
- Ollama `qwen2.5:3b-instruct-q4_K_M`: sinh câu trả lời trong hai experiment; cùng model cho cả hai cấu hình.
- Ollama `embeddinggemma`: tạo embedding cho Chroma.
- Chroma: lưu các index cô lập cho chunk 300 và chunk 800.
- Python, pytest và PowerShell: ingestion, chạy endpoint, kiểm tra schema, tính metrics.

Đã kiểm tra skill ecosystem theo yêu cầu `find-skills`. Không cài skill bên ngoài: evaluator native của repo đã có sẵn và phù hợp hơn vì cần gọi đúng endpoint, grounding gate và citation contract của AgriAI.

## Prompt và bộ câu hỏi quan trọng

- Bộ 30 câu cố định nằm trong [`docs/challenge/evaluation.jsonl`](docs/challenge/evaluation.jsonl), gồm câu có nguồn, multi-document, thiếu dữ liệu và ngoài phạm vi.
- Prompt runtime yêu cầu model chỉ trả lời từ evidence truy hồi, gắn `[TLn]`, không bịa số liệu và nói chưa đủ dữ liệu khi evidence không đủ.
- Prompt thực nghiệm giữ nguyên; chỉ thay chunk size/overlap và Chroma storage.

## AI đã giúp gì

- Chuyển tiêu chí challenge thành manifest, evaluation set và test phân phối.
- Viết bộ chấm tự động cho answer status, retrieval hit/recall, citation và no-answer.
- Thêm timing retrieval/generation/tổng vào response để báo cáo latency.
- Dựng hai index Chroma, chạy 30 câu cho từng cấu hình và tổng hợp JSON/report.
- Soạn README, evaluation report, experiment report và hướng dẫn reviewer.

## Output AI sai và cách sửa

- Một lần chạy ban đầu dùng `qwen3:4b-instruct` bị rơi vào `local-fallback-v1` do prompt vượt context mặc định; run đó bị loại khỏi số liệu chính.
- Một số câu có citation đúng nhưng kèm nguồn gần chủ đề không cần thiết; các nguồn này được đếm riêng là `extra_out_of_target_source`, không gộp thành citation đúng hoàn toàn.
- Các câu thiếu dữ liệu q026–q029 đôi lúc model tự từ chối nhưng grounding gate vẫn báo `ready`; chúng chỉ được xếp `needs_review`, không tính là strict pass trong baseline.
- Câu ngoài phạm vi q030 chưa bị từ chối đúng trong baseline; lỗi được giữ nguyên trong báo cáo trước khi sửa, không làm đẹp tỷ lệ.

## Cách kiểm tra và sửa sai

- Kiểm tra manifest offline và remote: 20/20 URL HTTP 200, hash/nội dung khớp.
- Kiểm tra Chroma: 20 tài liệu; chunk counts lần lượt 334 và 129.
- Chạy test schema/evaluation và test backend liên quan; kết quả gần nhất của nhóm test là pass.
- Đối chiếu từng `expected_doc_ids` với `retrieved_doc_ids` và citation thực tế.
- Kiểm tra p50/p95 từ timing server thay vì đo mỗi thời gian client tổng.
- Không dùng run fallback làm benchmark generation.

## Sửa cổng từ chối khi thiếu thông tin

Audit q026–q030 cho thấy lỗi nằm trước model, không chỉ ở câu trả lời sinh ra:

- Shortcut capability nhận nhầm mọi câu có “hướng dẫn” là câu hỏi khả năng, bỏ qua RAG.
- Từ khóa không dấu `gia` và `nang` va vào “giả”/“năng suất”, làm sai intent.
- Context số liệu được coi là dùng chung cho mọi intent; tin thị trường không được xem là giá hiện tại.
- Một con số kg trong tài liệu phân bón bị coi nhầm là liều thuốc bảo vệ thực vật.
- Evidence có “nhóm” bị khớp chuỗi con với crop “nho”, nên tài liệu cây khác lọt qua.

Đã sửa bằng intent classification chính xác hơn, cổng grounding có scope theo intent, kiểm tra dosage/future-quantitative riêng và token boundary cho crop. Test hồi quy không cho gọi model khi thiếu bằng chứng. Kết quả chạy endpoint thật sau sửa: q026–q029 `no_source` **4/4 pass**, q030 `out_of_scope` **1/1 pass**; log thô nằm trong [`grounding_gate_verification.md`](docs/challenge/grounding_gate_verification.md).

## Phần con người đã kiểm chứng

Con người kiểm chứng manifest/URL/hash, schema và phân phối 30 câu, storage tách biệt, model/config của hai run, log metrics, các q-id lỗi và kết luận giới hạn. Nội dung semantic của toàn bộ 25 câu answerable chưa được duyệt thủ công từng câu; vì vậy `needs_review` vẫn được giữ đúng tên và không tuyên bố là “đúng tuyệt đối”.

## Nếu có thêm 7 ngày

1. Duyệt thủ công 25 câu answerable và viết golden answer có tiêu chí chấp nhận.
2. Thêm reranker/MMR, giới hạn citation theo evidence thực sự dùng và thử nhiều overlap.
3. Tách retrieval latency khỏi embedding cache warm-up, chạy nhiều seed/repeat và thêm load test.
4. Thêm dashboard freshness/source health và một bộ regression test cho từng failure bucket.
