# Triage labels

| Role | GitHub label | Màu |
| --- | --- | --- |
| Maintainer evaluation required | `needs-triage` | `D93F0B` |
| Waiting for reporter information | `needs-info` | `FBCA04` |
| Fully specified for an agent | `ready-for-agent` | `0E8A16` |
| Human implementation required | `ready-for-human` | `1D76DB` |
| Will not be actioned | `wontfix` | `6E7781` |

Nguồn sự thật: [`.github/labels.yml`](../../.github/labels.yml).

## Tạo nhãn trên GitHub

Cần đăng nhập một lần bằng tài khoản có quyền ghi trên repo:

```bash
gh auth login
bash scripts/sync-github-labels.sh
```

Script idempotent: nhãn đã tồn tại thì cập nhật màu và mô tả cho khớp manifest,
chạy lại bao nhiêu lần cũng được.

## Mẫu issue

`.github/ISSUE_TEMPLATE/` có sẵn hai mẫu, cả hai tự gắn `needs-triage`:

- **Báo lỗi** — hỏi route, khung hình và phản hồi API, vì phần lớn lỗi trong đợt
  redesign là số liệu hiển thị sai chứ không phải trang hỏng.
- **Đề xuất tính năng** — bắt buộc nêu nguồn dữ liệu, vì dự án không hiển thị
  số liệu không có nguồn.
