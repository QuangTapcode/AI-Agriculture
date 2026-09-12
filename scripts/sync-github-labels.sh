#!/usr/bin/env bash
# Đồng bộ năm nhãn triage chuẩn lên GitHub.
#
# Yêu cầu: gh đã cài và đã đăng nhập (`gh auth login`).
# Chạy:    bash scripts/sync-github-labels.sh
#
# Idempotent: nhãn đã có thì cập nhật màu và mô tả thay vì báo lỗi.
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-QuangTapcode/AI-Agriculture}"

if ! command -v gh >/dev/null 2>&1; then
  echo "Chưa có gh CLI. Cài bằng: winget install --id GitHub.cli" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh chưa đăng nhập. Chạy: gh auth login" >&2
  exit 1
fi

sync_label() {
  local name="$1" color="$2" description="$3"
  if gh label list --repo "$REPO" --limit 200 --json name --jq '.[].name' | grep -qx "$name"; then
    gh label edit "$name" --repo "$REPO" --color "$color" --description "$description"
    echo "cập nhật  $name"
  else
    gh label create "$name" --repo "$REPO" --color "$color" --description "$description"
    echo "tạo mới   $name"
  fi
}

sync_label needs-triage    D93F0B "Cần maintainer đánh giá trước khi ai đó bắt tay vào làm"
sync_label needs-info      FBCA04 "Đang chờ người báo cáo bổ sung thông tin"
sync_label ready-for-agent 0E8A16 "Đã đặc tả đủ để một agent tự thực hiện"
sync_label ready-for-human 1D76DB "Cần người thực hiện, không giao cho agent"
sync_label wontfix         6E7781 "Sẽ không xử lý"

echo "Xong. Năm nhãn triage đã khớp với .github/labels.yml"
