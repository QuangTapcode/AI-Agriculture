# Knowledge Agent

Knowledge Agent chỉ cập nhật dữ liệu cho RAG. Nó không sửa mã nguồn, đổi model hoặc tự triển khai phiên bản mới.

## Luồng chạy

Celery Beat gọi `app.tasks.knowledge_tasks.ingest_knowledge_sources` lúc 02:00 hằng ngày theo múi giờ `Asia/Ho_Chi_Minh`.

1. Đọc danh sách nguồn từ `KNOWLEDGE_AGENT_SOURCES_FILE`; biến `KNOWLEDGE_AGENT_SOURCES_JSON` là cấu hình dự phòng.
2. Chỉ theo liên kết cùng `allowed_domain` và khớp bộ lọc URL đã cấu hình.
3. Tải PDF, TXT, Markdown hoặc trang HTML; nếu trang chi tiết có PDF cùng miền thì ưu tiên PDF.
4. Chuẩn hóa văn bản và tính SHA-256. Nội dung đã có sẽ bị bỏ qua.
5. Lưu bản mới vào `storage/rag/staging` với trạng thái `pending` và metadata nguồn, ngày, khu vực, cây trồng, phiên bản.
6. Kiểm tra độ dài, từ khóa nông nghiệp và độ phủ của ba câu hỏi kiểm tra bằng embedding.
7. Tài liệu đạt yêu cầu được chuyển sang `storage/rag/approved` và collection RAG hệ thống. Tài liệu không đạt giữ trạng thái `rejected`; lỗi kỹ thuật có trạng thái `failed`.
8. Khi cùng URL có nội dung mới, bản mới được tăng phiên bản. Bản cũ chỉ chuyển thành `superseded` sau khi bản mới đã xuất bản thành công.

Collection hệ thống dùng owner `0`. Khi chat, trợ lý tìm đồng thời trong collection hệ thống và collection riêng của người dùng, xếp hạng chung rồi trả về tối đa `RAG_TOP_K` đoạn. Trích dẫn chứa tên nguồn và URL gốc.

Tài liệu tự động có giới hạn riêng `KNOWLEDGE_AGENT_MAX_BYTES` (mặc định 50 MB) và `KNOWLEDGE_AGENT_MAX_TEXT_CHARS` (mặc định một triệu ký tự). Giới hạn tải lên thủ công vẫn là 10 MB.

## Cấu hình nguồn

Mỗi phần tử trong `config/knowledge_sources.json` hỗ trợ:

- `name`, `url`, `allowed_domain`: bắt buộc.
- `include_patterns`: chuỗi phải xuất hiện trong URL tài liệu trên trang danh mục.
- `include_regexes`: biểu thức chính quy cho nguồn có đường dẫn động hoặc mã tài liệu.
- `link_text_patterns`: chỉ nhận liên kết có tiêu đề chứa ít nhất một từ khóa chuyên ngành đã khai báo.
- `exclude_patterns`, `exclude_regexes`: loại liên kết điều hướng, bản xem PDF trùng hoặc mục không liên quan.
- `include_start_page`: nạp chính trang nguồn khi đó là một tài liệu kỹ thuật tĩnh.
- `region`, `crop`: metadata mặc định.
- `max_documents`: giới hạn mỗi lần quét.
- `validation_questions`: bộ câu hỏi riêng của nguồn; nếu bỏ trống sẽ dùng ba câu hỏi nông nghiệp chung.

Ví dụ:

```json
[
  {
    "name": "Trung tâm Khuyến nông Quốc gia",
    "url": "https://khuyennongvn.gov.vn/thu-vien-khuyen-nong/thu-vien-sach-kn",
    "allowed_domain": "khuyennongvn.gov.vn",
    "region": "Việt Nam",
    "crop": "Nông nghiệp",
    "include_patterns": ["/thu-vien-khuyen-nong/thu-vien-sach-kn/"],
    "max_documents": 6
  }
]
```

Worker và backend phải cùng mount `RAG_STORAGE_PATH`; cấu hình Docker Compose hiện dùng volume `rag_data` cho cả hai.

Cấu hình mặc định hiện theo dõi 11 luồng từ 7 hệ thống: Khuyến nông Quốc gia (sách, trồng trọt, chăn nuôi, thủy sản), VAAS (sách và ấn phẩm), Viện KHKT Nông nghiệp miền Nam, Viện Khoa học Lâm nghiệp (tiến bộ kỹ thuật và tạp chí), Cục Thủy sản, cùng Cục Trồng trọt và Bảo vệ thực vật. Mỗi nguồn chỉ lấy tối đa 1-2 tài liệu đầu danh sách trong một lần chạy; hash nội dung ngăn việc lập chỉ mục lại ở đêm tiếp theo.

## Vận hành

Các API quản trị yêu cầu tài khoản có vai trò `admin`:

- `GET /api/admin/knowledge/sources`: xem lịch và nguồn hiện tại.
- `GET /api/admin/knowledge/documents?status=pending`: xem kho chờ và kết quả kiểm tra.
- `POST /api/admin/knowledge/run`: chạy thủ công, kể cả khi lịch tự động đang tắt.

Lịch sử mỗi lần chạy cũng xuất hiện ở `GET /api/admin/ingestion-logs?job_name=knowledge_agent`.
