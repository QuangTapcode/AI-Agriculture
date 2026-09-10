# Trợ lý nông nghiệp: RAG và lịch sử hội thoại

Trang **Trợ lý → Kho tài liệu → Nạp tài liệu** nhận PDF có lớp văn bản, TXT và Markdown UTF-8. Sau khi nạp, hỏi trong cùng trang; câu trả lời hiển thị các nguồn `[TL1]`, `[TL2]` kèm tên tệp, trang và đoạn trích để đối chiếu. Tài liệu chỉ được tra cứu bởi tài khoản đã nạp. Kho ban đầu trống, không có sách nông nghiệp giả hoặc dữ liệu mẫu được tự nhận là nguồn chuyên môn.

## Chạy local

### Nếu đang chạy bằng Docker Compose

Container chứa bản sao mã nguồn lúc build. `docker compose restart` không cập nhật giao diện hay API mới. Từ thư mục gốc dự án, cập nhật hai dịch vụ bằng:

```powershell
docker compose start db redis
docker compose up -d --build --no-deps backend frontend
./scripts/check-assistant-runtime.ps1
```

Sau khi backend healthy, tải lại `http://localhost:5173/ai-chat` bằng `Ctrl+F5`. Nút **Kho tài liệu** nằm ở góc trên bên phải khung chat. Không dùng `docker compose down -v`; lệnh này có thể xóa dữ liệu volume. Giữ container cơ sở dữ liệu hiện có khi cập nhật Trợ lý.

### Nếu chạy trực tiếp bằng Python/Node

Từ thư mục `backend`, cài các phụ thuộc mới vào môi trường Python đang chạy ứng dụng:

```powershell
venv/Scripts/python.exe -m pip install "chromadb>=1.0,<2" "pypdf>=5,<7"
ollama pull qwen3:4b-instruct
ollama pull embeddinggemma
```

Thiết lập trong `backend/.env`, sau đó khởi động lại backend:

```dotenv
AI_PROVIDER=ollama
AI_BASE_URL=http://localhost:11434
AI_MODEL_NAME=qwen3:4b-instruct
AI_CONTEXT_TOKENS=4096
AI_MAX_OUTPUT_TOKENS=600
AI_TIMEOUT_SECONDS=120
AI_CONTEXT_TOKENS=8192
RAG_ENABLED=true
RAG_STORAGE_PATH=storage/rag
RAG_EMBEDDING_MODEL=embeddinggemma
RAG_TIMEOUT_SECONDS=60
RAG_TOP_K=4
RAG_MAX_CHUNKS_PER_DOCUMENT=2
RAG_MIN_SIMILARITY=0.35
```

`AI_MODEL_NAME` hiện mặc định là Qwen3 4B Instruct thay cho Qwen2.5 3B. Đây là biến thể trả lời trực tiếp, tránh độ trễ của biến thể Thinking khi chạy trên GPU 4 GB. Model quantized khoảng 2,5 GB; bộ nhớ chạy thực tế còn bao gồm context và có thể phải dùng một phần RAM/CPU. Chất lượng thực tế vẫn cần đánh giá trên tài liệu và câu hỏi của dự án. Thông số model: [Qwen3 4B Instruct](https://ollama.com/library/qwen3:4b-instruct), [Qwen3 8B](https://ollama.com/library/qwen3:8b).

Embedding chạy CPU để tránh tranh VRAM với model chat. Model Qwen3 được gọi với `think: false` và `/no_think`, nhiệt độ 0,2 và context cấu hình ở trên; phần nằm trong thẻ suy luận được loại khỏi câu trả lời. Giao diện chờ tối đa 240 giây cho truy xuất cộng sinh câu trả lời; có thể ghi đè bằng `VITE_AI_TIMEOUT_MS`. Lần nạp tài liệu có thể mất lâu hơn, với thời gian chờ giao diện tối đa 10 phút.

## Luồng xử lý

1. Đọc tài liệu, giới hạn 10 MB, 300 trang PDF và 300.000 ký tự. PDF ảnh cần OCR trước, PDF có mật khẩu bị từ chối.
2. Chia đoạn tối đa 1.000 ký tự, chồng lấn 150 ký tự và giữ số trang.
3. Gọi [Ollama `/api/embed`](https://docs.ollama.com/api/embed) theo lô, lưu embedding cùng văn bản và metadata vào Chroma trên đĩa. Toàn bộ embedding phải hoàn thành trước khi xuất bản tài liệu; SHA-256 nội dung ngăn nạp trùng.
4. Khi hỏi, kết hợp câu hỏi hiện tại với cây trồng, khu vực và câu hỏi gần đây trong chính hội thoại để tìm đoạn liên quan theo cosine similarity. Chỉ nhận kết quả đạt ngưỡng, mặc định tối đa 4 đoạn.
5. Ghép nguồn truy xuất, dữ liệu nghiệp vụ phù hợp và tối đa 3 lượt hội thoại gần nhất vào prompt. Lịch sử được giới hạn độ dài và không được coi là nguồn xác minh.
6. Sinh câu trả lời, lưu cả trích dẫn vào lịch sử. Nếu model lỗi nhưng có nguồn, trả các đoạn trích với thông báo rõ ràng. Nếu kho trống, không có kết quả hoặc truy xuất lỗi, giao diện hiển thị trạng thái tương ứng; không tự tạo nguồn.

API tài liệu: `GET/POST /api/ai-chat/documents`, `DELETE /api/ai-chat/documents/{id}`. Tất cả cần đăng nhập. Kho giới hạn 10.000 đoạn mỗi tài khoản/model embedding. Đổi model embedding tạo collection riêng; cần nạp lại tài liệu, không trộn vector từ hai model. Dữ liệu collection cũ vẫn nằm trên đĩa để quản trị viên quản lý.

Chroma local phù hợp một tiến trình backend. Docker Compose phát triển gắn named volume `rag_data` để giữ chỉ mục qua việc tạo lại container. Sao lưu volume cùng cơ sở dữ liệu ứng dụng; không đưa thư mục `backend/storage/rag` lên Git. Với triển khai nhiều tiến trình/máy chủ, cần chuyển sang Chroma server thay vì dùng chung PersistentClient trên nhiều tiến trình.

## Lịch sử

- Mỗi hội thoại mới dùng một UUID riêng; mở lại sẽ tải đủ các lượt theo thứ tự để trao đổi tiếp.
- Sidebar nhóm theo ngày, hiển thị số lượt, tìm trong cả câu hỏi và câu trả lời, phân trang bằng **Xem thêm**.
- Xóa một hội thoại hoặc toàn bộ lịch sử cần xác nhận trên giao diện. Backend soft-delete toàn bộ lượt tương ứng và không đưa chúng vào bộ nhớ nữa.
- Hội thoại cũ có `SessionID` rỗng hoặc `frontend-session` được giữ thành từng mục `legacy-{ConvID}`; có thể tiếp tục ngay mà không gộp nhầm tất cả lịch sử cũ.
- API mới: `GET /api/ai-chat/conversations?q=...&offset=0&limit=20`, `GET/DELETE /api/ai-chat/conversations/{id}`. Chi tiết hội thoại phân trang 100 lượt/lần; UI tải tiếp các trang trước khi mở.
- Các API `/history` cũ vẫn giữ contract. Khi khởi động, schema upgrade thêm `deleted_at` cho SQLite/SQL Server hiện có. Không xóa dữ liệu cũ.
- Trích dẫn là snapshot tại thời điểm trả lời. Xóa tài liệu khỏi kho không xóa đoạn trích đã lưu trong lịch sử; xóa lịch sử nếu không muốn tiếp tục hiển thị chúng. Soft-delete không phải xóa vật lý dữ liệu.

## Kiểm thử

```powershell
venv/Scripts/python.exe -m pytest tests/test_assistant_rag.py tests/test_ai_chat_local.py tests/test_ai_chat_intent.py tests/test_ollama_client.py tests/test_chat_memory.py tests/test_docker_ollama_wiring.py -q
```

Phép thử thật với Ollama dùng tài liệu tổng hợp trong thư mục tạm, không đọc hay sửa tài liệu người dùng:

```powershell
$env:RUN_OLLAMA_RAG_TEST='1'
venv/Scripts/python.exe -m pytest tests/test_assistant_rag_live.py -q -s
```

Phép thử này xác nhận model trả đúng mã lô và tên người phụ trách chỉ có trong tài liệu, kèm trích dẫn. Đây là smoke test kỹ thuật, không phải đánh giá đầy đủ độ chính xác tư vấn nông nghiệp.
