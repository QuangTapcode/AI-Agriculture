# AgriAI

AgriAI là nền tảng hỗ trợ nông nghiệp cho người dùng Việt Nam. Ứng dụng gom
dữ liệu thời tiết, thị trường, mùa vụ, kiểm tra chất lượng nông sản và một trợ
lý AI có RAG để người dùng nhận được câu trả lời có nguồn, hoặc được thông báo
rõ khi kho tài liệu chưa đủ.

Giao diện dùng hướng **Field Command**: các trang public giúp khám phá sản
phẩm; khu vực đăng nhập tập trung vào dashboard, vận hành mùa vụ, thị trường
và trợ lý AI.

## Trạng thái challenge

Đã chạy bản local Docker ngày **2026-09-29** qua đúng endpoint người dùng gọi,
POST /api/ai-chat/message, với 30 câu hỏi cố định:

| Nhóm | Kết quả | Ý nghĩa |
| --- | ---: | --- |
| grounded (20 câu) | 20 needs_review | Có citation và retrieval hit 14/20; nội dung semantic cần người duyệt |
| no_source (6 câu) | 1 pass, 5 needs_review, 0 fail | Cơ chế từ chối đã hoạt động chắc chắn ở 1 câu; 5 câu còn evidence gần chủ đề |
| out_of_scope (4 câu) | 4 pass | Từ chối ngoài phạm vi đúng |
| Latency | p50 22.9s / p95 34.6s / max 41.4s | Đo từ endpoint, dùng Ollama qwen3:4b-instruct |

Kết luận trung thực: pipeline, dataset, citation, evaluation và guardrail đã
đủ để trình diễn; **chưa nên tuyên bố đạt tuyệt đối** vì answer quality vẫn cần
human review và nhóm no_source chưa đạt 6/6 strict pass. Raw output của lần
chạy local nằm trong .local/verification/2026-09-29/; cách chạy lại nằm ở
[báo cáo verification](docs/challenge/verification_2026-09-29.md).

## Tính năng và công nghệ

| Tính năng | Luồng chính | Công nghệ chính |
| --- | --- | --- |
| Dashboard Field Command | Chọn cây trồng/khu vực → tổng hợp chỉ số → hiển thị trạng thái nguồn | React, FastAPI, SQLAlchemy, Redis, Chart.js |
| Thời tiết và cảnh báo | Khu vực → Open-Meteo → cache/freshness → rủi ro nông nghiệp → alert | FastAPI, Open-Meteo, Redis, Celery |
| Giá và thị trường | Cây trồng/khu vực → crawler/API → chuẩn hóa → lịch sử, xu hướng, kênh bán | FastAPI, SQLAlchemy, crawler, Tavily tùy chọn, Chart.js |
| Mùa vụ/thu hoạch | Ngày trồng + cây + khu vực → dự báo ngày thu hoạch → lịch và rủi ro | FastAPI, Prophet/logic mùa vụ, SQLAlchemy |
| Kiểm tra chất lượng | Ảnh → phát hiện/phân loại → khuyết tật → grade và giá gợi ý | YOLO/Ultralytics, EfficientNet, OpenCV, Pillow |
| Trợ lý AI RAG | Câu hỏi → intent/scope → hybrid retrieval → grounding gate → LLM + citation/refusal | Ollama, Chroma, BM25, RRF, FastAPI |
| Tài liệu tri thức | URL/file → parse → chunk → embedding → Chroma → metadata nguồn | Python, BeautifulSoup, pypdf, Ollama embeddings, Chroma |
| Đăng nhập và dữ liệu cá nhân | Login → JWT → ProtectedRoute → API Bearer → database | React Router, JWT, python-jose, passlib, SQLAlchemy |

## Kiến trúc tổng thể

~~~mermaid
flowchart LR
    Browser[React 18 + Vite<br/>Field Command UI] -->|Axios / JSON / JWT| API[FastAPI + Uvicorn]
    API --> DB[(SQL Server dev<br/>PostgreSQL production<br/>SQLite fallback)]
    API --> Cache[(Redis)]
    Worker[Celery worker + beat] --> Cache
    Worker --> DB
    API --> Weather[Open-Meteo]
    API --> Market[Official sources / crawlers / Tavily]
    API --> RAG[Chroma + BM25/RRF]
    RAG --> Ollama[Ollama<br/>qwen3 + embeddinggemma]
    API --> Models[YOLO/Ultralytics<br/>EfficientNet/OpenCV]
~~~

Các lớp chính:

~~~text
frontend/src/pages       # màn hình public và authenticated
frontend/src/services    # API client cho từng domain
backend/app/api          # HTTP routers và validation
backend/app/services     # nghiệp vụ dashboard, weather, market, RAG, quality
backend/app/integrations # Ollama, Gemini, Tavily, external sources
backend/app/tasks        # Celery và background refresh
backend/tests            # pytest cho contract, grounding, service
docs/challenge            # dataset, evaluation, experiment, verification
scripts                   # ingest, evaluate, smoke test, verification
~~~

## Luồng hoạt động từng tính năng

### 1. Dashboard Field Command

~~~mermaid
flowchart TD
    U[Người dùng chọn cây trồng + khu vực] --> UI[Dashboard React]
    UI --> ENDPOINT[/api/dashboard/overview<br/>/summary /data-health]
    ENDPOINT --> DS[DashboardService]
    DS --> SQL[(SQLAlchemy / database)]
    DS --> W[WeatherService + cache]
    DS --> P[Pricing/Market services]
    DS --> N[Market news service]
    W --> UI
    P --> UI
    N --> UI
    UI --> Trust[Hiển thị source + freshness + unavailable state]
~~~

Dashboard không tự bịa số liệu. Mỗi giá trị định lượng phải đi qua API, có
nguồn/trạng thái cập nhật; khi thiếu dữ liệu, frontend hiển thị unavailable.

### 2. Thời tiết và cảnh báo

~~~mermaid
flowchart LR
    User[Chọn khu vực/cây trồng] --> WeatherAPI[/api/weather/*]
    WeatherAPI --> Service[WeatherService]
    Service --> Cache{Có cache còn hạn?}
    Cache -->|Có| Cached[Trả dữ liệu + freshness]
    Cache -->|Không| OpenMeteo[Open-Meteo API]
    OpenMeteo --> Store[Lưu DB + Redis]
    Store --> Risk[Phân tích rủi ro nông nghiệp]
    Risk --> Alerts[Cảnh báo thời tiết/notification]
    Cached --> UI[ForecastPage / AlertPage]
    Alerts --> UI
~~~

### 3. Giá, tin tức và kênh bán

~~~mermaid
flowchart TD
    Crawler[Crawler/Celery định kỳ] --> Sources[Trang giá chính thức<br/>RSS / Tavily tùy chọn]
    Sources --> Normalize[Chuẩn hóa tên cây, vùng, đơn vị, timestamp]
    Normalize --> PriceDB[(MarketPrices / PriceHistory)]
    User[Người dùng nhập cây + vùng + sản lượng] --> MarketAPI[/api/pricing/*<br/>/api/market/*<br/>/api/news/*]
    MarketAPI --> PriceDB
    MarketAPI --> Analyzer[PricingService + MarketAnalysisService]
    Analyzer --> Result[Lịch sử / xu hướng / giá gợi ý / kênh bán]
    Result --> UI[PricingPage / ReportsPage]
~~~

### 4. Mùa vụ và dự báo thu hoạch

~~~mermaid
flowchart LR
    Input[Ngày trồng + cây + vùng + giống] --> API[/api/seasons/*<br/>/api/harvest/*]
    API --> Season[SeasonService]
    Season --> Forecast[HarvestService<br/>logic mùa vụ / Prophet tùy luồng]
    Forecast --> Risk[WeatherService + harvest risk]
    Risk --> DB[(HarvestSchedule / ForecastResults)]
    DB --> UI[SeasonManagementPage]
    UI --> Actions[Lịch canh tác, lịch sử, nhắc việc]
~~~

### 5. Kiểm tra chất lượng nông sản

~~~mermaid
flowchart TD
    Upload[Upload ảnh] --> Validate[FastAPI multipart validation]
    Validate --> Detect[YOLO/Ultralytics phát hiện vùng/đối tượng]
    Detect --> Classify[EfficientNet phân loại chất lượng]
    Classify --> Vision[OpenCV/Pillow đo màu và khuyết tật]
    Vision --> Grade[QualityService hợp nhất grade, disease, defects]
    Grade --> Price[PricingService tính giá tham khảo nếu đủ dữ liệu]
    Grade --> Save[(QualityRecords)]
    Save --> UI[QualityPage + lịch sử]
~~~

Model weights phải tồn tại trong môi trường triển khai. Nếu thiếu model hoặc
dữ liệu ảnh không đủ, API phải trả trạng thái lỗi/unavailable; không được biến
fallback thành kết quả thật trong production.

### 6. Nạp tài liệu vào Chroma

~~~mermaid
flowchart TD
    Sources[20 tài liệu HTML công khai<br/>manifest + URL + SHA-256] --> Verify[Verify status, hash, min chars]
    Verify --> Parse[BeautifulSoup / pypdf parse text]
    Parse --> Chunk[Chunk size + overlap]
    Chunk --> Embed[Ollama embeddinggemma]
    Embed --> Chroma[(Persistent Chroma collection)]
    Parse --> Metadata[document_id, source, URL, crop, region, page, chunk]
    Metadata --> Chroma
~~~

Chạy lại ingestion:

~~~powershell
backend/venv/Scripts/python.exe scripts/verify_challenge_dataset.py
backend/venv/Scripts/python.exe scripts/verify_challenge_dataset.py --remote
backend/venv/Scripts/python.exe scripts/ingest_challenge_dataset.py
~~~

Manifest challenge có đúng **20 tài liệu**, mỗi tài liệu tối thiểu 800 ký tự,
nguồn thuộc nhóm Khuyến nông Quốc gia và có metadata/hash để tái lập.

### 7. Trợ lý AI: hybrid search, ranking và agentic RAG

~~~mermaid
flowchart TD
    Q[Câu hỏi người dùng] --> Intent[Intent + crop + region extraction]
    Intent --> Plan[Agentic plan: query gốc + query tập trung]
    Plan --> Retrieve[Retrieve tối đa RAG_AGENT_MAX_STEPS]
    Retrieve --> Vector[Chroma cosine candidates]
    Retrieve --> Lexical[BM25 lexical candidates trên snapshot]
    Vector --> RRF[RRF + weighted score]
    Lexical --> RRF
    RRF --> Grade[Evidence grade: scope + topic + score]
    Grade -->|Yếu| Rewrite[Rewrite query bounded]
    Rewrite --> Retrieve
    Grade -->|Đủ| Gate{Grounding gate}
    Gate -->|ready| LLM[Ollama qwen3:4b-instruct]
    Gate -->|no_match / out_of_scope| Refusal[Từ chối rõ ràng, không đoán]
    LLM --> Citation[Answer + TL1/TL2 + source metadata]
~~~

Các lớp bảo vệ:

1. Retrieval trả cả điểm vector, lexical, RRF để debug được vì sao tài liệu
   được xếp hạng.
2. Agentic loop bị giới hạn bước, không để model tự quyết định retry vô hạn.
3. Grounding gate chặn câu trả lời khi không có evidence hoặc ngoài scope.
4. Prompt yêu cầu citation, không bịa số liệu, và nói rõ “chưa đủ dữ liệu” khi
   đoạn trích không hỗ trợ câu hỏi.

### 8. Đăng nhập, phân quyền và dữ liệu cá nhân

~~~mermaid
flowchart LR
    Login[LoginPage] --> AuthAPI[POST /api/auth/login]
    AuthAPI --> Security[python-jose + passlib]
    Security --> DB[(Users)]
    Security --> Token[JWT access token]
    Token --> Storage[localStorage token]
    Storage --> Axios[Axios interceptor Bearer]
    Axios --> Protected[ProtectedRoute + authenticated API]
    Protected --> Pages[Dashboard / mùa vụ / chat / settings]
~~~

## Chạy dự án

### Cách khuyến nghị: Docker Compose

Yêu cầu: Docker Desktop, Ollama trên host nếu muốn dùng AI local.

~~~powershell
ollama serve
ollama pull qwen3:4b-instruct
ollama pull embeddinggemma
docker compose up -d --build
docker compose ps
~~~

| Thành phần | Địa chỉ mặc định |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| SQL Server | localhost:1433 |
| Redis | localhost:6379 |

~~~powershell
docker compose logs -f backend
docker compose down
~~~

### Chạy tách frontend/backend

Backend dùng Python 3.11+ và frontend dùng Node.js 20+:

~~~powershell
cd backend
python -m venv venv
./venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
Copy-Item ../.env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
~~~

Terminal khác:

~~~powershell
cd frontend
npm ci
$env:VITE_API_URL="http://127.0.0.1:8000"
npm run dev
~~~

## Kiểm thử và đánh giá

### Unit/integration tests

~~~powershell
# Backend
$env:PYTHONUTF8="1"
backend/venv/Scripts/python.exe -m pytest backend/tests -q

# Frontend: Vitest + production build
cd frontend
npm run check
~~~

### Smoke test local bằng Playwright

Backend phải đang ở port 8000:

~~~powershell
backend/venv/Scripts/python.exe .agents/skills/webapp-testing/scripts/with_server.py --server "npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5174" --port 5174 -- backend/venv/Scripts/python.exe scripts/verify_local_app.py
~~~

Smoke test kiểm tra /health, Swagger, landing page, login route, HTTP 200,
body không rỗng, screenshot và browser console errors.

### Bộ 30 câu challenge

~~~powershell
backend/venv/Scripts/python.exe scripts/evaluate_rag.py --base-url http://127.0.0.1:8000 --questions docs/challenge/evaluation_questions.json --timeout 180
~~~

Bộ câu hỏi gồm 20 grounded, 6 no_source và 4 out_of_scope. Báo cáo cũ,
experiment chunk 300/800 và luật chấm nằm trong [docs/challenge](docs/challenge).
Kết quả chạy mới không được thay thế bằng số liệu lịch sử; hãy ghi ngày chạy,
model, dataset và latency khi báo cáo.

## Challenge artifacts

- Dataset manifest: [docs/challenge/dataset_manifest.json](docs/challenge/dataset_manifest.json)
- Evaluation questions: [docs/challenge/evaluation_questions.json](docs/challenge/evaluation_questions.json)
- Evaluation có ground truth: [docs/challenge/evaluation.jsonl](docs/challenge/evaluation.jsonl)
- Luật chấm: [docs/challenge/evaluation.md](docs/challenge/evaluation.md)
- Báo cáo verification mới nhất: [verification_2026-09-29.md](docs/challenge/verification_2026-09-29.md)
- Experiment chunking: [experiment_report.md](docs/challenge/experiment_report.md)
- Architecture decision cho hybrid/agentic RAG: [ADR 0001](docs/adr/0001-hybrid-ranking-agentic-rag.md)
- Nhật ký AI: [AI_WORKLOG.md](AI_WORKLOG.md)

## Product/demo verification

Public demo hiện được ghi nhận tại [agriai-demo.pages.dev](https://agriai-demo.pages.dev/),
nhưng tài khoản đăng nhập public và video công khai phải được kiểm tra lại trước
khi nộp. Không ghi tài khoản seed như tài khoản reviewer đang hoạt động nếu chưa
đăng nhập thành công.

Reviewer local có thể dùng câu hỏi mẫu:

~~~text
Sau bão lũ, vườn cây ăn quả bị gãy cành cần làm gì trước?
~~~

Các tiêu chí public link, demo account, kho RAG public và video phải có bằng
chứng runtime riêng; kết quả local không tự chứng minh public deployment.

## Giới hạn hiện tại

- 20 câu grounded đều cần human review về nội dung semantic; automated checks
  mới chứng minh hình thức citation, scope và không chèn số ngoài evidence.
- 5/6 câu no_source nhận evidence gần chủ đề từ shared knowledge store;
  đây là rủi ro false-positive cần cải thiện bằng query-specific answerability
  hoặc reranker/threshold tốt hơn.
- Latency phụ thuộc warm-up Ollama, GPU/CPU và độ dài prompt; số liệu trên
  không phải SLA production.
- Model weights quality (best.pt, efficientnet_quality.pt) không nằm trong
  repository hiện tại; cần cung cấp artifact khi triển khai quality service.
- Giá, tin tức và thời tiết phụ thuộc nguồn ngoài, cache và trạng thái freshness;
  thiếu dữ liệu phải hiển thị unavailable, không thay bằng zero/mock.

## License và đóng góp

Đọc [AGENTS.md](AGENTS.md), context tương ứng và các test liên quan trước khi
thay đổi. Mọi thay đổi frontend cần chạy test + production build; mọi thay đổi
RAG cần cập nhật evaluation/AI worklog khi làm thay đổi hành vi.
