# Kế hoạch cải thiện AI local và chuyển cảnh giao diện

Ngày đo: 14/09/2026

## Bằng chứng hiện tại

- Frontend unit: 30 file, 128 test — đạt.
- Frontend production build: đạt.
- Playwright: 164 test trên 390×844, 768×1024, 1024×768 và 1440×900 — đạt.
- Backend: 483 test đạt, 2 bỏ qua, 9 lỗi do weights YOLO/EfficientNet bị thiếu trong
  môi trường (`ai_models/weights/best.pt` và `efficientnet_quality.pt`), không liên
  quan pipeline RAG.
- Ollama đang có `qwen3:4b-instruct`, `qwen2.5:3b-instruct-q4_K_M` và
  `embeddinggemma`. Lượt chat lạnh của Qwen3 4B mất 16,65 giây (load 9,11 giây,
  sinh 126 token); lượt ấm mất 5,66 giây (96 token). Embedding một câu mất 2,59
  giây ở lượt ấm và trả vector 768 chiều.

Các số đo trên là baseline của máy hiện tại, không phải số liệu giả lập. Mọi lần đo
sau phải ghi model, quantization, context, output token, trạng thái cold/warm và
nguồn dữ liệu.

## P1 đã triển khai

- Ollama có endpoint NDJSON `/api/ai-chat/message/stream`: gửi trạng thái truy xuất,
  token trả lời theo từng đoạn và sự kiện hoàn tất. Endpoint JSON cũ vẫn giữ nguyên
  cho client tích hợp hiện tại.
- Embedding câu hỏi được cache trong bộ nhớ theo hash, TTL và giới hạn kích thước cấu
  hình được qua `RAG_EMBED_CACHE_TTL_SECONDS`, `RAG_EMBED_CACHE_SIZE`; không lưu nội
  dung câu hỏi vào database.
- Prompt không còn tự gán Hà Nội hoặc lúa khi người dùng chưa cung cấp phạm vi.
- UI đã dùng stream để hiển thị token sớm; `Reveal` tìm đúng scroll container, có
  fallback dưới một giây và tôn trọng reduced motion. `TiltCard` giới hạn pointer
  fine, dùng `requestAnimationFrame` và tắt trên touch/reduced motion. Route có
  transition chỉ dùng transform, giữ độ tương phản ổn định.

## Vấn đề AI local cần xử lý

1. **Độ trễ lượt đầu.** Model phải nạp lại vào RAM/GPU; embedding gọi Ollama riêng
   và đang ép `num_gpu=0`. API chat dùng `stream=false`, nên người dùng thấy màn hình
   chờ trong toàn bộ thời gian sinh.
2. **Prompt và context dài.** `AI_CONTEXT_TOKENS=3072`, `AI_MAX_OUTPUT_TOKENS=256`;
   prompt hệ thống lớn, lịch sử và trích đoạn RAG có thể chiếm phần lớn context.
3. **Mặc định nghiệp vụ.** Context service còn có mặc định nội bộ `Ha Noi` và `lua`
   cho một số luồng. Cần giữ giá trị thiếu là `null`/`—`, không biến thành địa điểm
   hoặc cây trồng người dùng chưa cung cấp.
4. **Retrieval chưa đủ chọn lọc.** Chroma đang tìm dense-only, tối đa 4 kết quả và
   giới hạn một chunk mỗi tài liệu; chưa lọc metadata cây trồng/khu vực trước khi
   đưa bằng chứng vào prompt.
5. **Chất lượng chưa được đo độc lập.** Test hiện kiểm tra prompt và cấm bịa số,
   nhưng chưa có bộ câu hỏi chuẩn đo đúng nguồn, đúng đơn vị, đúng cây và đúng vùng.
6. **Khả năng mô hình.** Máy hiện chỉ có Qwen3 4B và Qwen2.5 3B. Chưa được tự ý
   tải model lớn hơn; cần benchmark trên chính máy trước khi đổi model mặc định.

## Lộ trình AI local

### P0 — đo và làm rõ lỗi

- Thêm `request_id`, `prompt_tokens`, `output_tokens`, `retrieval_ms`, `context_ms`,
  `embedding_ms`, `generation_ms`, `model` và `rag_status` vào log nội bộ; không ghi
  nội dung câu hỏi hoặc dữ liệu cá nhân.
- Tạo bộ đánh giá 50 câu tiếng Việt, chia theo giá/thời tiết/kỹ thuật/sâu bệnh/mùa
  vụ; mỗi câu ghi nguồn bắt buộc, cây, vùng, đơn vị và trạng thái thiếu dữ liệu.
- Tách test cold-start, warm-start, Ollama tắt, embedding lỗi, Chroma rỗng và nguồn
  RAG không khớp.

**Cổng đạt:** có p50/p95 cho từng giai đoạn và có thể chỉ ra câu trả lời sai do
retrieval, prompt hay model.

### P1 — giảm thời gian chờ

- Chuyển `/api/ai-chat/message` sang streaming NDJSON/SSE từ Ollama; frontend hiển
  thị token đầu tiên, trạng thái truy xuất và trạng thái hoàn tất riêng.
- Giữ model chat bằng `keep_alive`, thêm health/prewarm tùy chọn khi worker khởi
  động; nếu Ollama không sẵn sàng thì trả trạng thái rõ ràng.
- Cache embedding câu hỏi theo hash trong thời gian ngắn; gom batch embedding khi
  lập chỉ mục; chỉ bật GPU cho embedding sau khi đo VRAM và kiểm tra không ảnh hưởng
  model chat.
- Chỉ gọi các nguồn context theo intent; hủy công việc hết ngân sách thay vì chờ
  thread không còn cần thiết.

**Cổng đạt:** lượt ấm có token đầu tiên ≤2 giây và p95 hoàn tất ≤8 giây trên máy
hiện tại; lượt lạnh được hiển thị tiến trình nạp model thay vì màn hình trống.

### P2 — tăng độ đúng của RAG và câu trả lời

- Đổi tên `_build_gemini_prompt` thành tên trung lập như `_build_grounded_prompt`;
  tách system rule, backend facts, RAG evidence và format answer thành các phần có
  giới hạn token.
- Lọc Chroma theo metadata `crop`, `region`, `topic`, `status=approved`; tăng
  candidate pool rồi rerank bằng lexical+dense, vẫn giới hạn số chunk đưa vào prompt.
- Thêm bước kiểm tra sau sinh: mọi số phải xuất hiện trong backend facts hoặc trích
  dẫn; trích dẫn phải tồn tại; câu trả lời sai cây/vùng bị trả về trạng thái cần
  xác minh.
- Thử `num_ctx` 4096/6144 và output 384/512 trong benchmark, không tăng mặc định
  nếu độ trễ hoặc tỷ lệ bịa tăng.

**Cổng đạt:** bộ 50 câu đạt ngưỡng groundedness/relevance đã thống nhất; câu thiếu
nguồn trả `unavailable` hoặc yêu cầu làm rõ, không trả số ước lượng.

### P3 — chọn model mạnh hơn có bằng chứng

- So sánh Qwen3 4B hiện tại với một bản Qwen3 8B (và chỉ thử 14B nếu máy còn đủ
  tài nguyên) cùng quantization phù hợp. Không tải model mới trong production trước
  khi có quyết định và benchmark.
- Bảng benchmark bắt buộc gồm cold/warm latency, token/s, RAM/VRAM, tỷ lệ trả đúng
  nguồn, tỷ lệ đúng số/đơn vị và tỷ lệ trả lời tiếng Việt.
- Giữ Qwen3 4B làm fallback local nếu model lớn không sẵn sàng; không tự chuyển sang
  Gemini/Claude khi cấu hình provider là `ollama`.

## Vấn đề chuyển cảnh giao diện

Kiểm thử hiện đã chứng minh không tràn ngang, focus và reduced-motion hoạt động; chưa
đo được cảm giác chuyển cảnh. Rà soát mã cho thấy:

- `Reveal` bắt đầu `opacity: 0`, dùng fallback 2,5 giây; trong AppShell, vùng cuộn
  là `<main>` nhưng `IntersectionObserver` dùng viewport mặc định. Vì vậy phần tử
  trong trang nội bộ có thể hiện muộn hoặc bị trống.
- Chưa có page transition theo `location.pathname`; Suspense có thể thay toàn bộ
  nội dung bằng spinner khi đổi route.
- Nhiều class dùng `transition` chung, làm trình duyệt thử animate cả thuộc tính bố
  cục; `TiltCard` cập nhật style trên mọi pointermove, chưa giới hạn bằng
  `requestAnimationFrame`.
- Sidebar/Drawer vẫn giữ nội dung trong DOM khi đóng; cần kiểm tra focus trap và
  `aria-hidden` bằng keyboard, không chỉ kiểm tra bằng mắt.

## Lộ trình UI/transition

1. Sửa `Reveal` nhận `root` hoặc tự tìm scroll container gần nhất; giảm fallback
   xuống dưới 1 giây và luôn hiện nội dung khi JS/IntersectionObserver không hoạt
   động. Viết test observer không kích hoạt, scroll container nội bộ và reduced
   motion.
2. Thêm `PageTransition` ở lớp route với một key duy nhất; chỉ chuyển `opacity` và
   `transform`, không chặn thao tác hoặc làm mất chiều cao trang. Test điều hướng
   bàn phím, back/forward và route lazy.
3. Chuẩn hóa token motion: 160–220ms cho hover/focus, 280–420ms cho drawer/page,
   easing thống nhất; thay `transition`/`transition-all` bằng danh sách thuộc tính
   cụ thể.
4. Giới hạn tilt bằng `matchMedia('(pointer: fine)')`, `requestAnimationFrame` và
   biên độ nhỏ; tắt hoàn toàn với touch hoặc reduced motion.
5. Bổ sung Playwright kiểm tra: thời gian transition, không có layout shift lớn,
   focus không rơi vào drawer đóng, scroll reveal trong `<main>`, và ảnh trước/sau
   ở cả bốn viewport.

## Thứ tự thực hiện

1. P0 AI và test transition để có baseline đáng tin.
2. P1 streaming/cache và sửa Reveal, vì đây là hai nguyên nhân người dùng thấy
   “chờ lâu” và “transition không mượt”.
3. P2 retrieval/grounding rồi mới điều chỉnh context/output.
4. P3 benchmark model mạnh hơn sau khi pipeline đo được chất lượng.

Mỗi bước dùng RED–GREEN–REFACTOR, chạy `npm run check`, `npm run test:e2e` và nhóm
backend liên quan. Chỉ đưa model hoặc hiệu ứng mới vào production khi test chứng minh
không làm mất dữ liệu nguồn, không tạo số liệu giả và không phá responsive.
