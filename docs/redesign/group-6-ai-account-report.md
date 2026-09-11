# Nhóm 6 — AI và tài khoản (Trợ lý AI, Kho tài liệu, Cài đặt, Hồ sơ)

Nhánh `feat/ui-field-command`. `deploy/agriai-demo-pages/_worker.js` nằm ngoài mọi commit giao diện.

## Phạm vi đã làm

| Page | Route | Trạng thái |
| --- | --- | --- |
| Trợ lý AI | `/ai-chat` | Xong |
| Kho tài liệu | `/knowledge-documents` | Xong |
| Cài đặt | `/settings` | Xong |
| Hồ sơ | `/profile` | Xong |

## Lỗi nghiêm trọng: hai trang sập khi phản hồi thiếu danh sách

Giống hệt trang Cảnh báo ở nhóm 5:

- `/ai-chat` lưu thẳng `data.history` và `data.documents`; phản hồi thiếu một
  trong hai làm `history.length` ném lỗi.
- `/knowledge-documents` lưu thẳng `data.documents`; thiếu trường này làm
  `catalogue.documents.filter()` ném lỗi.

Cả hai route rơi xuống error boundary. Nay mọi danh sách giữ đúng hình dạng mảng.

Đây là mẫu lỗi lặp lại ở ba trang khác nhau, nên đáng ghi lại thành quy ước:
**không lưu nguyên phản hồi vào state khi UI giả định hình dạng của nó.**

## Lỗi dữ liệu thật đã sửa

- Ô đếm trạng thái kho tri thức (`records_fetched`, `records_saved`) hiển thị `0`
  cho lần chạy không báo về số lượng.

Phần còn lại của nhóm này vốn đã trung thực: `/settings` gọi đúng trạng thái
`Chưa rõ`, `Chưa có người nhận`, `Chưa gửi thử`; `/knowledge-documents` đã dùng
`?? '—'` cho các ô tổng hợp.

## Accessibility đã sửa

- **Toggle trong Cài đặt**: mỗi toggle bị bọc trong một `<label>` ngoài, trong khi
  chính nó lại render một `<label>` nữa chứa checkbox. Không label nào sở hữu
  control → axe báo `label` mức critical. Nay switch tự mang tên
  (`role="switch"` + `aria-label`), vỏ ngoài là `div`.
- Nút "Kho tài liệu" trên `/ai-chat` ẩn chữ dưới breakpoint `sm`, nên ở 390px nó
  là một nút chỉ có icon và không có tên.
- Ô tìm kiếm và bộ lọc trạng thái ở `/knowledge-documents` không có tên.
- 8 `<label>` ở Cài đặt và Hồ sơ không gắn với control.
- Chữ phụ `gray-400/500` trên nền canvas chỉ đạt 2.5–4.47:1.

## Kết quả kiểm thử

```
Unit (Vitest)      26 file, 104 test — pass
E2E (Playwright)   142 test trên 4 khung hình, 2 skip — pass
Build production   pass
```

Hạ tầng test: `src/test/setup.js` nay shim `scrollIntoView` — jsdom không cài đặt
hàm này, nên trang chat cuộn tới tin nhắn mới sẽ ném lỗi khi test.

## Một bài học về test

Test đầu tiên tôi viết cho `/knowledge-documents` **báo xanh nhầm**. Trang
debounce 250ms trước khi gọi API, nên `findByRole` bắt được `<h1>` từ lần render
đầu với state khởi tạo và kết thúc trước khi phản hồi kịp làm sập trang. Chỉ sau
khi chờ `getKnowledgeDocuments` thực sự được gọi thì lỗi mới lộ ra. Các test
tương tự trong đợt này đều chờ đúng thời điểm sau khi dữ liệu đã áp vào state.

## Ảnh và video

`docs/redesign/evidence/group-6-ai-account/` — `ai-chat-*`, `knowledge-*`,
`settings-*`, `profile-*` cho cả bốn khung hình, kèm `scroll-*.mp4`.
