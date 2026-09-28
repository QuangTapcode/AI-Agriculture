# AgriAI

AgriAI là nền tảng hỗ trợ nông nghiệp cho người dùng Việt Nam. Hệ thống kết hợp dữ liệu thị trường, thời tiết, mùa vụ, kiểm tra chất lượng nông sản qua ảnh và trợ lý AI có RAG.

Giao diện hiện tại theo hướng **Field Command**: các màn hình công khai phục vụ khám phá sản phẩm; khu vực đăng nhập tập trung vào dashboard, vận hành mùa vụ, thị trường và trợ lý AI.

## Tính năng hiện có

- Dashboard vận hành và các báo cáo tổng hợp.
- Tra cứu cây trồng, giá hiện tại, lịch sử giá, so sánh vùng và gợi ý kênh bán.
- Thời tiết hiện tại/dự báo và phân tích rủi ro nông nghiệp.
- Quản lý mùa vụ, lịch canh tác và dự báo thu hoạch.
- Kiểm tra chất lượng nông sản qua ảnh với pipeline YOLO11 + EfficientNet + phân tích màu.
- Trợ lý AI, chat streaming và thư viện tài liệu RAG.
- Tin tức thị trường, cảnh báo giá/thời tiết và thông báo.
- Đăng ký, đăng nhập, hồ sơ, cài đặt và phân quyền cơ bản.
- Các trang công khai: landing page, tính năng, bài viết, gói giá và liên hệ.

API backend cũng có crawler/refresh theo lịch, nguồn giá và tin tức bên ngoài, lưu raw data và metadata nguồn/freshness để kiểm soát độ tin cậy.

## Kiến trúc

```text
AgriAI/
├── backend/                 # FastAPI, SQLAlchemy, crawler, Celery, AI/RAG
│   ├── app/api/             # HTTP routers
│   ├── app/services/        # nghiệp vụ ứng dụng
│   ├── app/integrations/    # Ollama, Gemini, Tavily, thời tiết, thị trường...
│   ├── app/tasks/           # refresh và background jobs
│   ├── ai_models/           # inference và model runtime
│   └── tests/               # pytest
├── frontend/                # React 18 + Vite + Tailwind + Zustand
│   ├── src/pages/           # các màn hình public/app
│   ├── src/services/        # API clients
│   ├── src/utils/           # format, data trust, route helpers
│   └── tests/e2e/            # Playwright
├── training/
│   ├── quality/             # EfficientNet, notebook và checkpoint
│   └── yolo/                # recipe/notebook YOLO11
├── docs/
│   ├── project/             # API, database, vận hành, triển khai
│   ├── database/            # SQL schema và seed
│   ├── agents/              # quy ước làm việc cho agent
│   └── redesign/            # tài liệu kiểm thử/đánh giá UI
├── scripts/                 # setup, start/stop, smoke test, deploy helper
├── infra/                   # Cloudflare Pages worker và nginx config
├── storage/                 # upload/raw crawl/RAG storage khi chạy local
└── .local/                  # output, log, backup, tmp; bị gitignore
```

Các context chi tiết nằm trong [`CONTEXT-MAP.md`](CONTEXT-MAP.md):

- Frontend: [`frontend/CONTEXT.md`](frontend/CONTEXT.md)
- Backend/RAG: [`backend/CONTEXT.md`](backend/CONTEXT.md)
- YOLO training: [`training/yolo/CONTEXT.md`](training/yolo/CONTEXT.md)

## Yêu cầu

### Chạy bằng Docker (khuyến nghị)

- Docker Desktop có Docker Compose.
- Ollama trên máy host nếu muốn dùng trợ lý AI local; model mặc định là `qwen3:4b-instruct`.

### Chạy local từng phần

- Python 3.11+.
- Node.js 20+ và npm.
- SQL Server hoặc SQLite cho phát triển cục bộ.
- Redis nếu chạy các chức năng cache/background đầy đủ.
- ODBC Driver 17+ nếu kết nối SQL Server bằng `pyodbc`.

## Bắt đầu nhanh bằng Docker

`docker-compose.yml` khởi chạy SQL Server, Redis, backend, frontend và worker.

```bash
docker compose up -d --build
docker compose ps
```

Địa chỉ mặc định:

| Thành phần | Địa chỉ |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health check | http://localhost:8000/health |
| SQL Server | localhost:1433 |
| Redis | localhost:6379 |

Xem log hoặc dừng hệ thống:

```bash
docker compose logs -f backend
docker compose down
```

Nếu cần tuỳ chỉnh local, đặt biến trong `.env.local`. Compose đã nạp `.env.example` và `.env.local` nếu file tồn tại.

## Chạy local backend/frontend

Backend đọc cấu hình từ `.env` trong thư mục hiện hành. Một cách chạy local với SQLite mặc định:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item ..\.env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Trên macOS/Linux, thay lệnh kích hoạt môi trường bằng:

```bash
source venv/bin/activate
```

Chạy frontend ở terminal khác:

```bash
cd frontend
npm ci
npm run dev
```

Frontend dùng `VITE_API_URL`; khi chạy local có thể tạo `frontend/.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

## Cấu hình dữ liệu và AI

Sao chép `.env.example` để xem toàn bộ biến cấu hình. Các nhóm chính:

- `DATABASE_URL`, `REDIS_URL`: database và cache.
- `AI_PROVIDER`, `AI_BASE_URL`, `AI_MODEL_NAME`: nhà cung cấp/model AI.
- `RAG_ENABLED`, `RAG_STORAGE_PATH`, `RAG_EMBEDDING_MODEL`: RAG và kho tài liệu.
- `RAG_HYBRID_CANDIDATE_K`, `RAG_HYBRID_VECTOR_WEIGHT`, `RAG_HYBRID_LEXICAL_WEIGHT`, `RAG_RRF_K`: hybrid search và RRF ranking.
- `RAG_AGENT_MAX_STEPS`, `RAG_AGENT_MIN_RELEVANCE`: giới hạn vòng agentic RAG và ngưỡng evidence.
- `THITRUONG_NONGSAN_*`, `PRICE_SOURCE_URLS_JSON`: nguồn giá/tin tức.
- `WEATHER_PROVIDER`, `OPEN_METEO_BASE_URL`: nguồn thời tiết.
- `FIRECRAWL_*`, `TAVILY_*`, `GEMINI_API_KEY`: tích hợp tìm kiếm/crawl/LLM tùy chọn.
- `SMTP_*`: gửi email thông báo.
- `ALLOW_MOCK_DATA`, `ALLOW_SAMPLE_DATA`, `USE_REALTIME_ONLY`: chế độ dữ liệu.

Trong môi trường phát triển, `.env.example` cho phép mock/sample để kiểm thử luồng. **Không dùng các giá trị đó cho production.** Môi trường production phải tắt mock/sample, bật realtime-only khi phù hợp và chỉ hiển thị số liệu có nguồn, freshness và trạng thái cập nhật.

RAG hiện dùng hybrid search: Chroma cosine + BM25 lexical search, hợp nhất bằng RRF ranking. Vòng agentic RAG có giới hạn sẽ lập query tập trung theo crop/khu vực/intent, chấm evidence và rewrite một lần khi kết quả đầu chưa đủ liên quan. Chi tiết kiến trúc nằm trong [`docs/adr/0001-hybrid-ranking-agentic-rag.md`](docs/adr/0001-hybrid-ranking-agentic-rag.md).

### Dataset RAG cho AI Builder Challenge

Repo chốt một corpus gồm **20 tài liệu HTML công khai** từ Trung tâm Khuyến nông Quốc gia, bao phủ trồng trọt, chăn nuôi và thủy sản. Manifest cố định, URL nguồn, metadata, độ dài văn bản và SHA-256 nằm trong [`docs/challenge/dataset_manifest.json`](docs/challenge/dataset_manifest.json); quy tắc chọn và cách tái tạo nằm trong [`docs/challenge/dataset.md`](docs/challenge/dataset.md).

Kiểm tra manifest không cần mạng:

```powershell
backend\\venv\\Scripts\\python.exe scripts/verify_challenge_dataset.py
```

Tải lại, đối chiếu hash và index corpus vào shared Chroma collection:

```powershell
backend\venv\Scripts\python.exe scripts\verify_challenge_dataset.py --remote
backend\venv\Scripts\python.exe scripts\ingest_challenge_dataset.py
```

### Đánh giá trợ lý trên corpus

30 câu hỏi cố định chia ba nhóm — có nguồn, thiếu nguồn, ngoài phạm vi — chạy qua đúng endpoint người dùng gọi. Bộ đề, cách chấm và cách đọc kết quả nằm trong [`docs/challenge/evaluation.md`](docs/challenge/evaluation.md).

```powershell
backend\venv\Scripts\python.exe scripts\evaluate_rag.py --timeout 300
backend\venv\Scripts\python.exe scripts\evaluate_rag.py --review
```

#### Challenge submission summary

**Problem statement.** Nông dân cần câu trả lời kỹ thuật có nguồn kiểm chứng cho cây trồng, sâu bệnh, chăn nuôi và thủy sản; trợ lý phải từ chối rõ ràng khi kho không có dữ liệu thay vì đoán.

**Solution overview.** AgriAI dùng pipeline RAG local với Chroma và Ollama, metadata nguồn để citation, grounding gate để phân biệt có nguồn/thiếu nguồn/ngoài phạm vi, cùng bộ evaluation 30 câu cố định.

```text
Documents
  → Parsing
  → Chunking
  → Embedding
  → Retrieval
  → LLM
  → Answer + Citation
```

Corpus challenge có **20 tài liệu HTML công khai** (đủ nhóm trồng trọt, chăn nuôi và thủy sản), được cố định bằng manifest, URL và SHA-256. Bộ câu hỏi và test schema nằm trong [`docs/challenge/evaluation.jsonl`](docs/challenge/evaluation.jsonl).

Kết quả baseline với chunk 800: Hit@K **100%**, Recall@K **93.3%**, citation có ít nhất một nguồn đúng **25/25**, tổng latency p50/p95 **12.427/21.118 ms**. Chi tiết answer quality và failure analysis ở [`docs/challenge/evaluation_report.md`](docs/challenge/evaluation_report.md). Phần từ chối đã được sửa và kiểm tra lại riêng trong [`grounding_gate_verification.md`](docs/challenge/grounding_gate_verification.md).

Experiment chunk 300 vs 800 có số liệu trong [`docs/challenge/experiment_report.md`](docs/challenge/experiment_report.md), [`experiment_chunk_300.json`](docs/challenge/experiment_chunk_300.json) và [`experiment_chunk_800.json`](docs/challenge/experiment_chunk_800.json). Chunk 800 có recall tốt hơn; chunk 300 nhanh hơn ở p50 và ít citation dư hơn. Cấu hình được điều khiển bằng `RAG_CHUNK_SIZE` và `RAG_CHUNK_OVERLAP`.

**Reviewer test nhanh.**

```powershell
backend\venv\Scripts\python.exe scripts\verify_challenge_dataset.py
backend\venv\Scripts\python.exe scripts\ingest_challenge_dataset.py
backend\venv\Scripts\python.exe scripts\evaluate_rag.py --questions docs/challenge/evaluation.jsonl --timeout 300
backend\venv\Scripts\python.exe scripts\summarize_evaluation.py `
  docs\challenge\experiment_chunk_800.jsonl `
  docs\challenge\experiment_chunk_800.json --chunk-size 800 --overlap 120
```

Reviewer có thể mở demo local tại [http://localhost:5173](http://localhost:5173), API/Swagger tại [http://localhost:8000/docs](http://localhost:8000/docs), hoặc public demo [agriai-demo.pages.dev](https://agriai-demo.pages.dev/). Mã nguồn: [github.com/QuangTapcode/AI-Agriculture](https://github.com/QuangTapcode/AI-Agriculture).

#### Product/demo verification — 2026-09-26

| Tiêu chí | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|
| Frontend public | **Đạt** | `https://agriai-demo.pages.dev/`, `/features`, `/login`, `/register` trả HTTP 200 trên mobile và desktop; smoke test không phát hiện overflow, lỗi console hoặc response 5xx. `/health` trả `{"status":"healthy"}`. |
| Đăng nhập/demo account | **Chưa đạt / chưa xác minh** | Đã thử `nguyenvanan@gmail.com` với `Farmer@2024` và `123456`; public API trả HTTP 401. Không trình bày các tài khoản dưới đây như tài khoản đang hoạt động. |
| Kho RAG ≥20 tài liệu | **Đạt ở local** | Chroma local có **20 documents / 103 chunks**; public knowledge-status cần đăng nhập nên chưa thể xác nhận con số trên public demo. |
| API không dùng mock | **Đạt ở local; public chưa đủ bằng chứng** | Local smoke dùng provider `ollama`, model `qwen3:4b-instruct`, grounding `ready`, có 3 nguồn và không có `is_mock=true`. Cấu hình production đặt `ALLOW_MOCK_DATA=false`, `ALLOW_SAMPLE_DATA=false`, `USE_REALTIME_ONLY=true`. Public request AI chưa hoàn tất trong thời gian kiểm tra. |
| Video công khai | **Chưa đạt** | Video hiện có [agriai-ui-motion-concept.mp4](frontend/prototypes/ui-redesign/agriai-ui-motion-concept.mp4) trong repository, nhưng chưa được upload lên một host công khai. |

**Tài khoản demo tham chiếu từ seed** (cần re-seed/reset password và kiểm tra lại trước khi gửi reviewer):

```text
nguyenvanan@gmail.com       / 123456  / farmer
tranthimy2205@gmail.com     / 123456  / farmer
levanbinhfarmer@gmail.com   / 123456  / farmer
phamthilan@gmail.com        / 123456  / farmer
admin@agriai.vn             / 123456  / admin
```

**Câu hỏi mẫu:** `Sau bão lũ, vườn cây ăn quả bị gãy cành cần làm gì trước?`

**Lệnh kiểm tra public:** `PUBLIC_BASE_URL=https://agriai-demo.pages.dev node frontend/scripts/smoke-public.mjs`. Muốn hoàn tất hai mục còn thiếu cần cung cấp một tài khoản demo public đã seed/reset và một dịch vụ/tài khoản upload video (YouTube, Loom, Drive hoặc host tương đương).

**Prompt chính đã dùng:**

```text
KIẾN THỨC KỸ THUẬT: chỉ được lấy từ các đoạn tài liệu truy xuất.
Mỗi nhận định lấy từ đoạn nào thì trích dẫn [TL1], [TL2] tương ứng.
Phần nào tài liệu không nói tới thì trả lời thẳng "chưa đủ dữ liệu cho phần này"
— không thay bằng hiểu biết sẵn có và không suy đoán liều lượng thuốc/phân.
```

**Limitations.** Baseline trước khi sửa có no-answer strict **0/5**; kiểm tra hồi quy sau sửa đạt **5/5** (q026–q030). Citation vẫn có nguồn dư; `needs_review` chưa phải xác nhận semantic của câu trả lời; latency phụ thuộc model local, warm-up Ollama và CPU/GPU máy chạy. Không nên trình bày metrics answerable như bảo đảm production nếu chưa duyệt thủ công 25 câu.

Nhật ký sử dụng AI và các điểm đã kiểm chứng nằm trong [`AI_WORKLOG.md`](AI_WORKLOG.md).

## Chạy production/home deployment

`compose.home.yml` là compose hiện tại cho môi trường home/production-like, dùng SQL Server, Redis, volume RAG/upload và Cloudflare Tunnel.

```powershell
Copy-Item .env.home.example .env.home
# Điền MSSQL_SA_PASSWORD, SECRET_KEY, CLOUDFLARE_TUNNEL_TOKEN và các secret cần thiết
docker compose --env-file .env.home -f compose.home.yml up -d --build
```

`.env.home` không được commit. `docker-compose.prod.yml` là cấu hình legacy dùng PostgreSQL; chỉ sử dụng sau khi đã kiểm tra lại driver, schema và biến môi trường tương ứng.

## API chính

Backend FastAPI tự sinh tài liệu đầy đủ tại `/docs`. Một số nhóm endpoint:

| Nhóm | Ví dụ |
| --- | --- |
| Auth | `/api/auth/register`, `/api/auth/login`, `/api/auth/me` |
| Cây trồng | `/api/crops`, `/api/crops/search`, `/api/crops/{crop_id}` |
| Thời tiết | `/api/weather/current/{region}`, `/api/weather/forecast/{region}` |
| Giá | `/api/pricing/current`, `/api/pricing/history/{crop_name}/{region}`, `/api/pricing/compare-regions/{crop_name}` |
| Dự báo giá | `/api/price-forecast/predict` |
| Mùa vụ | `/api/seasons`, `/api/harvest/forecast`, `/api/harvest/schedules/me` |
| Chất lượng | `/api/quality/check`, `/api/quality/grades`, `/api/quality/history/{user_id}` |
| Thị trường | `/api/market/channels`, `/api/market/suggest` |
| AI/RAG | `/api/ai-chat/message`, `/api/ai-chat/message/stream`, `/api/assistant-library` |
| Tin tức/crawler | `/api/news/...`, `/api/crawler/...` |
| Cảnh báo | `/api/alert/...`, `/api/notifications/...` |

Tài liệu API chi tiết: [`docs/project/API_DOCUMENTATION.md`](docs/project/API_DOCUMENTATION.md).

## Kiểm thử và build

Backend:

```bash
cd backend
pytest
```

Frontend unit test và production build:

```bash
cd frontend
npm run test
npm run build
# hoặc chạy cả hai
npm run check
```

Frontend E2E:

```bash
cd frontend
npx playwright install --with-deps chromium
npm run test:e2e
```

Một số lệnh tiện ích:

```bash
make help
./scripts/check_system.sh
./scripts/test_api.sh
```

## Huấn luyện và model

Workflow được gom trong `training/`:

```bash
python training/quality/prepare_dataset.py
python training/quality/train_quality_cnn.py
streamlit run training/quality/streamlit_quality.py
```

- Dữ liệu đầu vào mặc định: `training/quality/raw_data/`.
- Dataset sau khi chia: `training/quality/data/`.
- Checkpoint theo dõi trong Git: `training/quality/checkpoints/`.
- Có thể thay đổi đường dẫn bằng `AGRI_RAW_DATA_DIR`, `AGRI_DATA_DIR`, `AGRI_CHECKPOINT_DIR`.
- Recipe YOLO11 và hướng dẫn chi tiết nằm trong `training/yolo/`.
- `python scripts/setup_models.py` đồng bộ checkpoint vào `backend/ai_models/weights/`, là nơi backend nạp model runtime.

Không đưa dataset lớn, raw crawl, upload người dùng hoặc output thử nghiệm vào Git. Các thư mục runtime và file sinh ra đã được tách/ignore theo `.gitignore`.

## Tài liệu liên quan

- [`docs/project/DOCS.md`](docs/project/DOCS.md): mục lục tài liệu.
- [`docs/project/DATABASE_SCHEMA.md`](docs/project/DATABASE_SCHEMA.md): schema database.
- [`docs/project/DEPLOYMENT.md`](docs/project/DEPLOYMENT.md): hướng dẫn triển khai.
- [`docs/project/START_BACKEND.md`](docs/project/START_BACKEND.md): khởi động backend.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): quy ước đóng góp.
- [`CHANGELOG.md`](CHANGELOG.md): lịch sử thay đổi.
- [`scripts/README.md`](scripts/README.md): danh sách script.

## Giấy phép

[MIT](LICENSE)
