# Đánh giá trợ lý trên corpus cố định

Bài đánh giá chạy 30 câu hỏi qua đúng endpoint người dùng gọi
(`POST /api/ai-chat/message`) và ghi lại câu trả lời sinh ra, trích dẫn thực
tế, độ trễ và kết luận.

Repo giữ **hai bộ đề**, mỗi bộ đo một thứ khác nhau; script đọc được cả hai và
chuẩn hóa về cùng một dạng trước khi chấm, để luật chấm không trôi khỏi nhau.

| Bộ đề | Đo cái gì | Kết quả |
| --- | --- | --- |
| [`evaluation.jsonl`](evaluation.jsonl) | Chất lượng câu trả lời — mỗi câu kèm `ground_truth` và `expected_source` | [`evaluation_results_groundtruth.jsonl`](evaluation_results_groundtruth.jsonl) |
| [`evaluation_questions.json`](evaluation_questions.json) | Cổng grounding — chia rõ ba nhóm, phủ đủ 20/20 tài liệu corpus | [`evaluation_results.jsonl`](evaluation_results.jsonl) |

Script: [`scripts/evaluate_rag.py`](../../scripts/evaluate_rag.py)

## Vì sao chia ba nhóm câu hỏi

Một hệ thống từ chối mọi câu hỏi vẫn đạt điểm tuyệt đối nếu chỉ đo bằng câu
hỏi không có nguồn. Ngược lại, một hệ thống trả lời mọi thứ từ trí nhớ của
model sẽ đạt điểm tuyệt đối nếu chỉ đo bằng câu hỏi có nguồn. Cần cả ba nhóm
mới kẹp được hành vi đúng:

| Nhóm | Số câu | Hành vi bắt buộc |
| --- | --- | --- |
| `grounded` | 20 | Trả lời kèm trích dẫn, lấy đúng tài liệu trong corpus |
| `no_source` | 6 | Nói "chưa đủ dữ liệu", không suy từ tài liệu gần giống |
| `out_of_scope` | 4 | Từ chối theo phạm vi — khác với "chưa đủ dữ liệu" |

20 câu nhóm `grounded` phủ hết 20 tài liệu của corpus: mỗi tài liệu được chạm
ít nhất một lần, có test canh điều đó
([`test_evaluation_questions.py`](../../backend/tests/test_evaluation_questions.py)).

## Chạy

```powershell
# bộ đo cổng grounding
backend\venv\Scripts\python.exe scripts\evaluate_rag.py --timeout 300
# bộ có ground_truth
backend\venv\Scripts\python.exe scripts\evaluate_rag.py --timeout 300 `
  --questions docs\challenge\evaluation.jsonl `
  --out docs\challenge\evaluation_results_groundtruth.jsonl
```

`--rescore` và `--review` cũng nhận `--questions`/`--out`; chạy bộ nào thì
truyền đúng cặp file của bộ đó, nếu không kết quả sẽ bị chấm bằng bộ đề khác.

Script đợi backend trả lời `/health` trước khi đo (`--wait`, mặc định 60s) và
dừng lại mà **không đụng tới file kết quả cũ** nếu backend chưa lên. Chạy ngay
sau `docker compose up -d` từng làm cả 60 lượt trả `RemoteProtocolError` và
ghi đè mất hai bộ kết quả tốt.

Tuỳ chọn hữu ích:

```powershell
# thử nhanh một nhóm
backend\venv\Scripts\python.exe scripts\evaluate_rag.py --only no_source
# duyệt tay các lượt máy không kết luận được
backend\venv\Scripts\python.exe scripts\evaluate_rag.py --review
# chấm lại file đã có sau khi sửa luật chấm, không gọi lại model
backend\venv\Scripts\python.exe scripts\evaluate_rag.py --rescore
```

`--rescore` tồn tại vì luật chấm còn sửa nhiều lần. Bắt chạy lại 30 lượt gọi
LLM mỗi lần sửa thì hoặc mất nửa tiếng, hoặc người ta thôi không sửa luật nữa.
Câu trả lời đã lưu nguyên văn — đủ để kết luận lại.

Backend phải đang chạy và corpus đã được index
(`scripts/ingest_challenge_dataset.py`). Mỗi câu hỏi dùng một `session_id`
riêng — dùng chung một phiên thì lượt sau đọc được lượt trước và bài đánh giá
đo nhầm trí nhớ hội thoại thay vì retrieval.

## Phạm vi retrieval không chỉ là 20 tài liệu corpus

Kho chia sẻ (owner `0`) chứa **127 tài liệu / 5700 chunk** chứ không chỉ 20
tài liệu trong [`dataset_manifest.json`](dataset_manifest.json): knowledge
agent nạp thêm hằng đêm từ nongthonmoi.gov.vn, vaas.vn,
banquanlyrungvakhuyennong.gov.vn và các nguồn đã duyệt khác. Retrieval tìm
trên toàn bộ kho, không giới hạn theo corpus.

Hệ quả cho bài đánh giá:

- `retrieved_doc_ids` rỗng **không** có nghĩa là không lấy được tài liệu nào —
  nó có nghĩa là tài liệu lấy được không thuộc corpus cố định.
- Nhóm `no_source` chỉ đúng khi câu hỏi nằm ngoài cả 127 tài liệu. Kho lớn dần
  mỗi đêm, nên bộ đề cần soát lại định kỳ: một câu "không có nguồn" hôm nay có
  thể có nguồn vào tuần sau.

## Cách chấm

Nhóm `out_of_scope` chấm tự động trọn vẹn: chỉ có một hành vi đúng, kiểm được
bằng `grounding.reason` và câu chữ từ chối.

Nhóm `no_source` tách theo **ai từ chối**, vì hai nguồn từ chối khác hẳn nhau
về độ tin cậy:

| Tình huống | Kết luận |
| --- | --- |
| Cổng grounding chặn (`reason = thieu_nguon`) | `pass` — chặn bằng luật, lặp lại được |
| Model tự từ chối, cổng để đi qua | `needs_review` + ghi chú `cong_khong_chan_model_tu_tu_choi` |
| Hệ thống trả lời thẳng câu hỏi | `fail` |

Gọi trường hợp giữa là "đạt" thì bài đánh giá đang tính công cho sự may mắn:
lần này model ngoan, cùng câu hỏi đó lần sau nó có thể bịa.

Nhóm `grounded` chỉ chấm tự động được phần hình thức: có trích dẫn không, có
lấy nhầm tài liệu khác trong corpus không, có chèn con số ngoài đoạn trích
không (dùng lại chốt chặn `so_lieu_khong_co_trong_nguon` của hệ thống). Lấy
nhầm một tài liệu khác **trong corpus** là retrieval sai chứng minh được →
`fail`. Lấy tài liệu **ngoài corpus** thì chưa kết luận được → `needs_review`
kèm ghi chú `tai_lieu_ngoai_corpus_co_dinh`.

Nội dung có đúng với tài liệu khuyến nông hay không thì script không đọc hiểu
được, nên kết luận dừng ở `needs_review` thay vì tự phong là đạt. `--review`
hiển thị từng lượt để người đọc chốt `pass`/`fail`, ghi vào trường
`human_review` của chính dòng JSONL đó.

## Kết quả lần chạy 2026-09-26

Cấu hình: `qwen3:4b-instruct`, `AI_CONTEXT_TOKENS=4096`, GTX 1650 4GB, kho
chia sẻ 127 tài liệu. Bộ đo cổng grounding
([`evaluation_results.jsonl`](evaluation_results.jsonl)):

| Nhóm | pass | needs_review | fail |
| --- | --- | --- | --- |
| grounded (20) | — | 20 | 0 |
| no_source (6) | 1 | 4 | 1 |
| out_of_scope (4) | 4 | — | 0 |

- retrieval hit (lấy đúng tài liệu corpus mong đợi): 14/20
- latency: p50 41.7s, p95 62.0s, max 90.7s

20 lượt `grounded` đều qua phần kiểm tự động (có trích dẫn, trạng thái `ready`,
không chèn số ngoài đoạn trích, không lấy nhầm tài liệu khác trong corpus) và
đang chờ người đọc xác nhận nội dung — chạy `--review`. 6 trong số đó mang ghi
chú `tai_lieu_ngoai_corpus_co_dinh`: tài liệu lấy được nằm ngoài 20 tài liệu
manifest.

4 lượt `no_source` mang ghi chú `cong_khong_chan_model_tu_tu_choi`: model tự
nói không có dữ liệu, nhưng cổng grounding để lượt đó đi qua vì retrieval trả
`ready`. Lượt `fail` duy nhất (q-24, tái canh cà phê) là **nhãn bộ đề sai chứ
không phải lỗi hệ thống**: kho có tài liệu kỹ thuật cà phê của VAAS (score
0.82) và câu trả lời trích dẫn [TL1] kèm số liệu cụ thể. Xem phần "Phạm vi
retrieval" ở trên.

Bộ có ground_truth
([`evaluation_results_groundtruth.jsonl`](evaluation_results_groundtruth.jsonl)):

| Nhóm | pass | needs_review | fail |
| --- | --- | --- | --- |
| grounded (25) | — | 23 | 2 |
| no_source (4) | — | 3 | 1 |
| out_of_scope (1) | — | — | 1 |

- retrieval hit: 21/25
- latency: p50 50.7s, p95 83.6s, max 101.6s

Bốn lượt `fail` và nguyên nhân:

| Lượt | Nguyên nhân |
| --- | --- |
| q015 | Hỏi lịch cho ăn tháng đầu để kiểm soát Vibrio (`kn-17`), retrieval lấy `kn-18` — tài liệu nuôi tôm an toàn. Retrieval sai thật. |
| q017 | Hỏi diện tích và độ sâu ao cá song (`kn-19`, phần 1), retrieval lấy `kn-20` — phần 2 của cùng tài liệu. Tài liệu bị chia hai phần và lấy sai nửa. |
| q029 | Nhãn bộ đề sai: `answerable=false` nhưng kho **có** tài liệu hướng dẫn trồng nho Hạ Đen, nên trợ lý trả lời là đúng. |
| q030 | Câu "**Hướng dẫn** kê khai thuế VAT…" khớp từ khoá `hướng dẫn` của `is_capability_question()` và bị trả lời bằng đoạn giới thiệu năng lực, nên không bao giờ tới cổng grounding (`grounding.status = not_used`). Lỗi có sẵn, chưa sửa. |

Độ trễ dao động theo tải máy chứ không theo cấu hình: cùng code và cùng
`AI_CONTEXT_TOKENS=4096`, một lần đo trước đó cho p50 17.5s. Con số so sánh
được giữa các cấu hình là lần đo sát nhau: trước khi cắt prompt
(`AI_CONTEXT_TOKENS=8192`) p50 22.5s / p95 55.0s, sau khi cắt p50 17.5s / p95
35.3s, và hết hẳn các lượt hỏng vì Ollama từ chối prompt quá dài.

## Đọc file kết quả

Mỗi dòng là một câu hỏi:

| Trường | Nội dung |
| --- | --- |
| `generated_answer` | Câu trả lời trợ lý sinh ra, nguyên văn |
| `citations` | Trích dẫn thực tế: id tài liệu, tên, URL nguồn, trang, điểm, đoạn trích |
| `retrieved_doc_ids` | Tài liệu lấy được, đã map về id trong manifest |
| `grounding` | `status` (ready/no_match/empty/unavailable) và `reason` |
| `latency_ms` | Độ trễ đo từ phía người gọi, gồm cả retrieval lẫn sinh câu |
| `result` | Kết luận tự động: `verdict`, từng `check`, ghi chú |
| `human_review` | `null` cho tới khi có người duyệt |
| `error` | `null` khi lượt hỏi thành công |

Lượt lỗi được ghi là `fail` chứ không bị bỏ qua: bỏ qua lượt lỗi là tính tỷ lệ
đạt trên phần mẫu còn sống, tức là làm đẹp số liệu.
