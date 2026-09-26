"""Fetch and index the fixed challenge corpus into the shared RAG collection.

The source pages are not copied into Git. This command re-fetches the pinned
URLs, verifies the manifest hash, and then uses the production ingestion and
embedding path to publish them to owner ``0`` (shared knowledge).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "challenge" / "dataset_manifest.json"
BACKEND_ROOT = ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.knowledge_ingestion_service import KnowledgeIngestionService  # noqa: E402
from app.services.rag_service import rag_service  # noqa: E402


def load_documents() -> list[dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return payload["documents"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and verify without writing Chroma.")
    args = parser.parse_args()

    service = KnowledgeIngestionService()
    documents = load_documents()
    for index, item in enumerate(documents, start=1):
        response = service.fetch(item["source_url"], item["domain"])
        extracted = service.extract(item["source_url"], response)
        content_hash = hashlib.sha256(extracted["content"]).hexdigest()
        if content_hash != item["content_sha256"]:
            raise RuntimeError(
                f"{item['id']}: nguồn đã thay đổi; expected={item['content_sha256']} actual={content_hash}"
            )
        if len(extracted["text"]) < 800:
            raise RuntimeError(f"{item['id']}: nội dung ngắn hơn ngưỡng 800 ký tự.")
        if args.dry_run:
            result = {"dry_run": True, "duplicate": False, "chunks": None}
        else:
            result = rag_service.ingest(
                owner=0,
                filename=item["ingest_filename"],
                content=extracted["content"],
                metadata={
                    "source_name": item["source_name"],
                    "source_url": item["source_url"],
                    "publisher": item["publisher"],
                    "topic": item["topic"],
                    "crop": item["crop"],
                    "region": item["region"],
                    "dataset_id": "agriai-knowledge-assistant-challenge",
                    "dataset_version": "2026-09-25",
                    "published_at": None,
                    "version": 1,
                },
            )
        state = "duplicate" if result.get("duplicate") else "indexed"
        print(f"[{index:02d}/{len(documents)}] {state} {item['id']} — {len(extracted['text'])} chars")

    if not args.dry_run:
        indexed = rag_service.documents(0)
        if len(indexed) < len(documents):
            raise RuntimeError(
                f"Chroma chỉ có {len(indexed)} tài liệu; cần ít nhất {len(documents)}."
            )
        print(f"Indexed shared challenge dataset: {len(indexed)} documents, {rag_service.collection(0).count()} chunks.")
    else:
        print(f"Dry-run passed: {len(documents)} documents verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
