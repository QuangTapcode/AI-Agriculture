# Tự phát hiện nguồn cho kho RAG

AgriAI có một job Celery chạy lúc 03:00 mỗi đêm (`discover-knowledge-sources-nightly`).
Job đọc các trang trong `config/knowledge_sources.json`, lấy các liên kết HTTP(S)
liên quan đến nông nghiệp và lưu URL mới vào bảng `KnowledgeSourceCandidates`.

Mỗi ứng viên có domain, nguồn phát hiện, lý do, điểm tin cậy và trạng thái. Ứng viên
 luôn bắt đầu ở `pending`; chỉ quản trị viên mới có thể gọi API approve/reject. Khi
 được approve, URL sẽ được Knowledge Agent dùng ở lượt nạp kế tiếp qua bảng dữ liệu
 động; file registry vẫn giữ các nguồn seed đã kiểm soát.

API quản trị:

- `POST /api/admin/knowledge/source-discovery/run` chạy quét ngay.
- `GET /api/admin/knowledge/source-candidates?status=pending` xem danh sách chờ.
- `POST /api/admin/knowledge/source-candidates/{id}/approve` hoặc `/reject`.

Tắt lịch bằng `SOURCE_DISCOVERY_ENABLED=false`; giới hạn bằng
`SOURCE_DISCOVERY_MAX_CANDIDATES` (mặc định 100). Cơ chế không dùng LLM để bịa URL,
không theo liên kết mạng nội bộ, mạng riêng, mạng xã hội hoặc tệp tĩnh.

## Query-triggered discovery

When RAG returns `empty` or `no_match`, the chat endpoint creates a
`KnowledgeDiscoveryJob` and sends it to Celery. The job starts with a search
query in a fresh isolated browser context so the topic can expand beyond the
configured registry. It then scans matching links on configured domains to
supplement the browser results. Only official Vietnamese government/university
domains are accepted, and it does not search or ingest Facebook.

Job statuses are `queued`, `running`, `indexed`, `completed`, `no_match`,
`failed`, and `unavailable`. Progress is available at:

- `GET /api/ai-chat/knowledge-discovery/{job_id}`

A document is counted as `indexed` only after `KnowledgeIngestionService.process`
returns `approved`; hashing, extraction, embedding, and validation questions
still apply. Repeated questions within the cooldown are deduplicated.

## Search from an isolated browser session

The worker can search Bing's HTML results using a new headless Chromium process
and an in-memory Playwright browser context. Queries run this search before the
registry scan, and a newly discovered official domain is preferred in the
per-query results. It never reads or reuses the operator's
Chrome profile, cookies, history, or signed-in sessions. JavaScript and all
requests outside the search provider are blocked; result links are fetched later
by the existing allow-listed ingestion service, not opened in the browser.

If Bing returns no relevant official result, topic-specific verified hints in
`config/knowledge_topic_sources.json` provide a bounded fallback for supported
common crops (`cam`, `dưa hấu`, `xoài`, and `nho`). These pages are still
downloaded and validated by the same quality checks; the hint list is not an
allow-list bypass. The fallback also remains available when browser search is
disabled, so a temporary search-provider failure does not turn a known crop
question into an unexplained `no_match`.

Only results from registered domains or from Vietnamese `.gov.vn` and `.edu.vn`
domains proceed automatically. Results from commercial/social domains are not
downloaded, and Facebook, YouTube, and TikTok remain blocked. Text extraction,
deduplication, metadata, embedding, and agricultural quality checks still decide
whether a document is published to RAG. Search text and the server's IP address
are visible to Bing; only extracted search terms, crop/region fields, and the
server's IP address are sent, not the full chat message. An isolated browser
session is not anonymous browsing.

Docker installs Chromium when the backend image is built. For a local Windows
backend, install the dependency and browser once from the `backend` directory:

```powershell
python -m pip install playwright
python -m playwright install chromium
```

Run the API, Redis, and Celery worker for query-triggered discovery to complete.
Set `KNOWLEDGE_BROWSER_SEARCH_ENABLED=false` to disable web fallback, or adjust
`KNOWLEDGE_BROWSER_SEARCH_MAX_RESULTS` and `KNOWLEDGE_BROWSER_SEARCH_TIMEOUT_SECONDS`
to limit each isolated search.
