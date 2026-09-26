"""Verify the fixed 20-document challenge corpus.

The default mode is offline and validates the committed manifest. ``--remote``
re-fetches every source through the same HTML extraction path used by the
knowledge agent, then checks the recorded character count and SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "challenge" / "dataset_manifest.json"
REQUIRED_COUNT = 20
ALLOWED_DOMAIN = "khuyennongvn.gov.vn"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_manifest() -> dict:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("documents"), list):
        raise AssertionError("Manifest phải là object có trường documents dạng list.")
    return payload


def verify_static(payload: dict) -> list[dict]:
    documents = payload["documents"]
    if len(documents) < REQUIRED_COUNT:
        raise AssertionError(f"Dataset có {len(documents)} tài liệu; cần ít nhất {REQUIRED_COUNT}.")
    if payload.get("document_count") != len(documents):
        raise AssertionError("document_count không khớp số phần tử documents.")

    ids = [item.get("id") for item in documents]
    urls = [item.get("source_url") for item in documents]
    if len(set(ids)) != len(ids):
        raise AssertionError("ID tài liệu bị trùng.")
    if len(set(urls)) != len(urls):
        raise AssertionError("URL tài liệu bị trùng.")

    minimum = int(payload.get("minimum_document_characters", 800))
    for item in documents:
        if item.get("verified_http_status") != 200:
            raise AssertionError(f"{item.get('id')}: status phải là 200.")
        if int(item.get("verified_characters", 0)) < minimum:
            raise AssertionError(f"{item.get('id')}: văn bản ngắn hơn {minimum} ký tự.")
        if not SHA256_RE.fullmatch(str(item.get("content_sha256", ""))):
            raise AssertionError(f"{item.get('id')}: content_sha256 không hợp lệ.")
        parsed = urlparse(str(item.get("source_url", "")))
        if parsed.scheme != "https" or parsed.hostname != ALLOWED_DOMAIN:
            raise AssertionError(f"{item.get('id')}: URL nằm ngoài miền nguồn cho phép.")
        for field in ("title", "source_name", "source_url", "topic", "crop", "region"):
            if not str(item.get(field, "")).strip():
                raise AssertionError(f"{item.get('id')}: thiếu metadata {field}.")
    return documents


def verify_remote(documents: list[dict]) -> None:
    backend_root = ROOT / "backend"
    sys.path.insert(0, str(backend_root))
    from app.services.knowledge_ingestion_service import KnowledgeIngestionService

    service = KnowledgeIngestionService()
    for index, item in enumerate(documents, start=1):
        response = service.fetch(item["source_url"], ALLOWED_DOMAIN)
        extracted = service.extract(item["source_url"], response)
        characters = len(extracted["text"])
        content_hash = hashlib.sha256(extracted["content"]).hexdigest()
        if response.status_code != item["verified_http_status"]:
            raise AssertionError(f"{item['id']}: status hiện tại {response.status_code} không khớp manifest.")
        if characters < 800:
            raise AssertionError(f"{item['id']}: nội dung hiện tại chỉ có {characters} ký tự.")
        if content_hash != item["content_sha256"]:
            raise AssertionError(
                f"{item['id']}: SHA-256 thay đổi; expected={item['content_sha256']} actual={content_hash}"
            )
        print(f"[{index:02d}/{len(documents)}] OK {item['id']} — {characters} chars")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true", help="Fetch and re-extract every source URL.")
    args = parser.parse_args()

    documents = verify_static(load_manifest())
    if args.remote:
        verify_remote(documents)
    print(f"Dataset verification passed: {len(documents)} documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
