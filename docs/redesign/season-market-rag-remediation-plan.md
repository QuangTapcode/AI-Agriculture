# Kế hoạch hợp nhất mùa vụ, làm sâu phân tích thị trường và mở rộng RAG

Ngày đánh giá: 13/09/2026

## Kết luận

Ba vấn đề có liên quan trực tiếp đến cấu trúc dữ liệu, không chỉ là lỗi giao diện:

1. Dự báo thu hoạch và quản lý mùa vụ đang dùng hai bảng, hai API và hai cách tính riêng. Dự báo phải trở thành một phần của một mùa vụ cụ thể.
2. Phân tích thị trường có dữ liệu nền nhưng hợp đồng giữa frontend và backend không khớp, provenance bị làm phẳng và nhiều trạng thái thiếu dữ liệu bị biến thành “ổn định”.
3. RAG vẫn chạy mỗi đêm, nhưng discovery chỉ đọc trang đầu và dừng ở 1–2 liên kết đầu của mỗi nguồn. Vì vậy pipeline liên tục phát hiện lại cùng tài liệu thay vì mở rộng kho.

## 1. Hợp nhất dự báo thu hoạch vào quản lý mùa vụ

### Hiện trạng

- `/harvest` và `/season-management` là hai trải nghiệm độc lập.
- Dữ liệu bị chia giữa `Seasons` và `HarvestSchedule`.
- Dashboard đọc `Seasons`; báo cáo, AI context, dự báo và kiểm định chất lượng lại phụ thuộc `HarvestSchedule`.
- Một thao tác chỉ nhằm xem dự báo hiện có thể tạo thêm `HarvestSchedule`, dẫn đến lịch trùng hoặc lịch “ma”.
- Thời gian sinh trưởng được khai báo ở hai nơi với giá trị không thống nhất.
- Khi thiếu thời tiết hoặc thị trường, backend đang tự thay bằng mức rủi ro trung bình, trạng thái trung lập và confidence cố định.

### Kiến trúc đích

`Season` là tên Module nghiệp vụ duy nhất trên API và giao diện. Trong giai đoạn chuyển đổi, `HarvestSchedule` được giữ làm Implementation lưu trữ chuẩn vì `HarvestForecastResults` và `QualityRecords` đang tham chiếu bảng này. `HarvestForecastResults` trở thành lịch sử các snapshot dự báo của một mùa vụ, không tạo mùa vụ mới.

Màn hình Quản lý mùa vụ có chi tiết theo mùa vụ gồm:

- Tổng quan.
- Cửa sổ thu hoạch dự kiến.
- Căn cứ tính, nguồn và thời điểm cập nhật.
- Rủi ro thời tiết/thị trường khi có dữ liệu phù hợp.
- Việc cần chuẩn bị và lịch sử cập nhật dự báo.

Khi thiếu căn cứ, UI hiển thị `—` kèm lý do. Không dùng ngày mặc định, confidence mặc định hoặc trạng thái trung lập.

### Các bước

1. Viết test khóa hành vi: xem ước tính không tạo bản ghi; cập nhật một mùa vụ chỉ tạo một snapshot; kiểm tra quyền sở hữu; thiếu cây trồng hoặc dữ liệu trả `unavailable`.
2. Bỏ mục Dự báo thu hoạch khỏi sidebar; redirect `/harvest` và `/harvest-forecast` sang `/season-management`.
3. Đưa drawer/chi tiết dự báo vào từng thẻ mùa vụ và bổ sung nguồn, độ tươi, cảnh báo.
4. Tách hàm tính dự báo thuần khỏi thao tác lưu database; thống nhất catalog thời gian sinh trưởng và mốc bắt đầu áp dụng.
5. Migrate có kiểm đếm từ `Seasons` sang storage chuẩn, giữ nguyên liên kết forecast/quality, sau đó chuyển Dashboard, Reports và AI sang cùng một Interface.
6. Giữ API harvest cũ như adapter tương thích trong một giai đoạn; chỉ xóa sau khi không còn caller.

### Hoàn thành khi

- Một mùa vụ xuất hiện giống nhau ở Quản lý mùa vụ, Dashboard, Báo cáo và AI.
- Xem ước tính tạo 0 mùa vụ; lưu lại tạo đúng 1 snapshot cho mùa vụ đã chọn.
- Mọi kết quả định lượng có căn cứ, nguồn và thời gian cập nhật.
- Route cũ đi đúng về Quản lý mùa vụ và không còn menu Dự báo thu hoạch.

## 2. Làm sâu phân tích thị trường

### Hiện trạng đã kiểm tra

- Database hiện có 53 bản ghi giá, toàn bộ từ `thitruongnongsan.gov.vn`; ngày quan sát mới nhất là 04/08/2026. Cà phê Đắk Lắk chỉ có 6 điểm trong khoảng 28/07–04/08, nên hiện không đủ dữ liệu cho cửa sổ 7 ngày hoặc 30 ngày tính đến 13/09/2026.
- Tin thị trường hiện chỉ gồm 139 bản ghi từ VnExpress RSS Tin mới nhất và 65 bản ghi từ VnExpress RSS Kinh doanh.
- Bảng giá bán lẻ đang trống.
- Frontend đọc `trend_7d`, `trend_30d`, `recommendation`, `data_sources`; backend trả `market_signal`, `recommendations`, `sources`. Vì không khớp, UI thường rơi về nội dung chung hoặc không hiện nguồn.
- Khi lịch sử không đủ, backend đang trả xu hướng `stable` và `0%`. Khi thiếu tín hiệu, hệ thống vẫn có thể trả “ổn định” hoặc “trung lập”. Đây là kết luận không có bằng chứng.
- Snapshot phân tích chỉ lưu tên chung “Market analysis cache”, làm mất danh sách bằng chứng tạo ra kết quả.
- Sáu kênh bán là dữ liệu seed tĩnh; giá chuỗi cửa hàng được tạo từ giá sỉ nhân markup 18–28% nhưng payload lại đánh dấu `is_mock: false`. Các số này chưa phải quan sát thị trường và phải bị loại khỏi production UI.

### Interface dữ liệu mới

Mọi chỉ số thị trường dùng một `MarketEvidence` thống nhất:

- `metric`, `value`, `unit`.
- `crop`, `region`, `marketLevel`.
- `observedAt`, `fetchedAt`.
- `sourceName`, `sourceUrl`.
- `status`: `live`, `cached`, `database`, `unavailable`.
- `sampleSize`, `coverage`, `qualityWarning`.

Một `MarketAnalysis` phải giữ toàn bộ evidence tạo nên kết quả. Cache chỉ là trạng thái lưu trữ, không được thay tên nguồn gốc.

### Nguồn theo vai trò

- Giá nội địa chính thức: nguồn nông nghiệp hiện có và bản tin thị trường nông, lâm, thủy sản của Bộ Công Thương.
- Xuất nhập khẩu: số liệu Hải quan Việt Nam, gắn đúng mã hàng và kỳ báo cáo.
- Tham chiếu quốc tế: FAOSTAT/FAO cho chuỗi giá và thống kê dài hạn; chỉ dùng futures khi ánh xạ được đúng hàng hóa.
- Giá chuyên ngành: connector riêng cho cà phê, hồ tiêu hoặc cây trồng cụ thể, bắt buộc giữ URL bài/bảng gốc.
- Giá bán lẻ: chỉ hiển thị dữ liệu crawl được trực tiếp với sản phẩm, đơn vị, cửa hàng và thời điểm; không dùng giá do model ước lượng.
- Tin tức: ưu tiên bản tin thị trường chuyên ngành; RSS tổng hợp chỉ đóng vai trò ngữ cảnh.

### Thiết kế trang

- Thẻ giá hiện tại: giá, đơn vị, khu vực, nguồn, thời điểm quan sát.
- Biểu đồ lịch sử: số điểm, khoảng bao phủ, khoảng trống dữ liệu.
- So sánh khu vực: chỉ hiện các vùng có cùng hàng hóa, đơn vị và thời điểm đủ gần.
- Tín hiệu: nêu bằng chứng nào đóng góp và mức độ đầy đủ.
- Bảng nguồn: trạng thái connector, lần cập nhật thành công, số bản ghi mới, lỗi gần nhất.
- Khi chưa đủ dữ liệu, thay biểu đồ/kết luận bằng empty state có lý do và hành động kiểm tra nguồn.

### Các bước

1. Viết test RED cho contract, provenance và trạng thái thiếu dữ liệu; xóa fallback “ổn định/0%/trung lập”.
2. Chuẩn hóa backend response và frontend selector theo `MarketEvidence`.
3. Lưu snapshot cùng toàn bộ evidence; thêm source-health API.
4. Hoàn thiện lần lượt các Adapter: giá chính thức, xuất nhập khẩu, nguồn chuyên ngành, quốc tế, bán lẻ và tin tức.
5. Thêm điều kiện dữ liệu tối thiểu trước khi tính xu hướng; thiếu độ phủ phải trả `unavailable`.
6. Làm lại trang Phân tích thị trường theo Prototype A và kiểm thử loading, empty, cached, live, error, responsive.

### Hoàn thành khi

- Không có kết luận xu hướng khi dữ liệu không đủ.
- Người dùng mở được URL nguồn cho từng giá, điểm biểu đồ, tin tức và kết luận.
- Không có giá bán lẻ ước lượng được trình bày như số đo.
- Lỗi một nguồn không làm mất dữ liệu hợp lệ của nguồn khác và được hiển thị trong source health.

## 3. Làm cho kho RAG thực sự tăng trưởng

### Hiện trạng đã kiểm tra

- Scheduler và worker đang hoạt động.
- Có 11 luồng nguồn, 21 tài liệu `approved`, 21 tài liệu trong Chroma và 1.189 chunks.
- Lần chạy gần nhất phát hiện 21 URL, có 20 URL trùng, 0 tài liệu mới và 1 lỗi HTTP 500.
- Mỗi nguồn chỉ cho phép `max_documents` bằng 1 hoặc 2. Discovery đọc một trang, lấy các liên kết đầu tiên rồi mới kiểm tra trùng. Các URL phía sau không bao giờ được xét.
- Hai luồng sách chiếm 874/1.189 chunks, làm kết quả retrieval lệch về vài tài liệu dài.
- Retrieval lấy tối đa 4 candidate trước khi giới hạn một chunk trên mỗi tài liệu, nên có thể kết thúc với chỉ 1–2 nguồn.
- Không có bộ lọc đầy đủ theo cây/vật nuôi, vùng và chủ đề. Probe đã trả tài liệu rau/cà phê cho câu hỏi bệnh tôm và tài liệu thủy sản cho câu hỏi giá hồ tiêu.
- Cổng chất lượng hiện quá nhẹ và mọi tài liệu đều đạt 100%; chưa có hàng chờ duyệt thật.

### Kiến trúc đích

Tạo Seam `KnowledgeSourceAdapter` với các Implementation:

- `SitemapAdapter`.
- `RssAtomAdapter`.
- `HtmlCatalogueAdapter` có phân trang/cursor.
- `DirectDocumentAdapter`.

Source Registry nằm trong database và giữ `sourceId`, publisher, connector, trust tier, chủ đề, cây/vật nuôi, vùng, ngôn ngữ, quyền sử dụng, lịch chạy, cursor, ETag/Last-Modified, lần thành công, lỗi gần nhất và các bộ đếm vận hành. File JSON chỉ dùng để seed cấu hình ban đầu.

### Các bước

1. Tách discovery khỏi download/extract/evaluate/index; discovery tạo danh sách candidate trước.
2. Kiểm tra URL đã biết trước khi áp quota. Quota giới hạn số tài liệu mới/đã thay đổi, không giới hạn hai liên kết đầu.
3. Bổ sung phân trang, sitemap/RSS, cursor và backfill round-robin. Chạy backfill có giới hạn đến khi bắt kịp, sau đó chuyển sang incremental.
4. Thêm retry, backoff và circuit breaker theo nguồn; lỗi VJFS phải hiện đúng ở health của VJFS mà không chặn nguồn khác.
5. Trích metadata thật. Nếu không biết ngày phát hành, lưu `null`; không dùng ngày nạp thay ngày phát hành.
6. Chấm authority, completeness, freshness, topical relevance và extraction quality. Nguồn tin cậy có thể tự duyệt; tài liệu biên hoặc nguồn mới đi vào hàng chờ approve/reject thật.
7. Sửa retrieval: metadata filter, candidate pool lớn hơn, lấy bù để đa dạng tài liệu, hybrid lexical+dense và reranker.
8. Khi quy mô tăng, chuyển Chroma sang service riêng và bỏ trần cứng 10.000 chunks sau khi có quota/backup/health phù hợp.

### Mở rộng nguồn

- Tầng 1: cơ quan quản lý, hệ thống khuyến nông và viện nghiên cứu Việt Nam.
- Tầng 2: tạp chí khoa học, trường đại học và trung tâm khuyến nông địa phương.
- Tầng 3: FAO, IRRI và các trung tâm CGIAR, bắt buộc gắn vùng áp dụng và ngôn ngữ.
- Nguồn doanh nghiệp chỉ được đưa vào khi có provenance, phiên bản và phạm vi áp dụng rõ.

Không thêm hàng loạt URL trước khi sửa discovery. Nếu chỉ nối thêm cấu hình, các nguồn mới cũng sẽ dừng ở 1–2 liên kết đầu.

### Màn hình quản trị kho tri thức

- Ma trận nguồn: trạng thái, chủ đề, lịch chạy, lần quét, lần có dữ liệu mới, cursor/backfill, số mới/trùng/từ chối/lỗi/đã index.
- Danh sách tài liệu: ngày phát hành, ngày nạp, phiên bản, nguồn/provenance, metadata, số chunks, điểm và lý do kiểm duyệt.
- Hành động có quyền: chạy lại nguồn, tạm dừng, retry, approve, reject, reindex.
- Báo cáo sau mỗi đêm: nguồn nào chạy, tài liệu nào mới, tài liệu nào đổi phiên bản, lỗi nào cần xử lý và kết quả regression retrieval.

### Hoàn thành khi

- URL thứ ba mới vẫn được nạp dù hai URL đầu đã trùng.
- Crawl tiếp tục được qua nhiều trang và từ cursor của đêm trước.
- Câu hỏi tôm không lấy tài liệu rau/cà phê; intent giá không dùng tài liệu kỹ thuật thay dữ liệu thị trường.
- Mỗi lỗi fetch xuất hiện tại đúng nguồn; người quản trị xác minh được tài liệu mới và trạng thái index.
- Báo cáo dùng cụm từ “nạp và lập chỉ mục”. RAG không được mô tả là huấn luyện lại trọng số model.

## 4. Thứ tự triển khai và cổng chất lượng

Thực hiện theo đúng nguyên tắc một page hoàn chỉnh trước khi chuyển page tiếp theo:

1. **Quản lý mùa vụ**: hợp nhất route/UI, sửa semantics dự báo, rồi migrate dữ liệu canonical.
2. **Phân tích thị trường**: sửa contract và false defaults trước, sau đó thêm evidence adapters và thiết kế trang.
3. **Kho tài liệu RAG**: sửa discovery, source registry và retrieval trước, sau đó mở rộng nguồn và hoàn thiện quản trị.

Mỗi nhóm dùng RED–GREEN–REFACTOR và chỉ hoàn thành khi:

- Backend contract, ownership, migration và failure modes có test.
- Frontend có test loading, empty, error, cached, live và dữ liệu thiếu.
- Không có mock/sample/demo/estimated value bị trình bày như dữ liệu thật.
- Không lỗi console hoặc request lỗi bị che giấu.
- Không tràn ngang tại 390×844, 768×1024, 1024×768 và 1440×900.
- Production build, unit/integration tests và Playwright đều đạt.
- Có ảnh desktop/mobile, video cuộn trang và báo cáo test trước khi chuyển sang page tiếp theo.
