import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "challenge" / "dataset_manifest.json"


def test_challenge_manifest_has_twenty_verified_documents():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    documents = payload["documents"]

    assert len(documents) >= 20
    assert payload["document_count"] == len(documents)
    assert len({item["id"] for item in documents}) == len(documents)
    assert len({item["source_url"] for item in documents}) == len(documents)

    for item in documents:
        assert item["verified_http_status"] == 200
        assert item["verified_characters"] >= payload["minimum_document_characters"]
        assert re.fullmatch(r"[0-9a-f]{64}", item["content_sha256"])
        parsed = urlparse(item["source_url"])
        assert parsed.scheme == "https"
        assert parsed.hostname == "khuyennongvn.gov.vn"
        assert item["title"] and item["topic"] and item["crop"]


def test_manifest_hashes_are_sha256_length_values():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for item in payload["documents"]:
        assert len(bytes.fromhex(item["content_sha256"])) == hashlib.sha256().digest_size
