"""Scheduled, allow-listed ingestion into the shared RAG collection."""
import hashlib
import ipaddress
import json
import logging
import re
import socket
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ingestion import DataIngestionLog
from app.models.knowledge import KnowledgeDocument
from app.services.rag_service import extract_pages, rag_service

logger = logging.getLogger(__name__)
SYSTEM_KNOWLEDGE_OWNER = 0
DEFAULT_QUESTIONS = [
    "Tài liệu này hướng dẫn kỹ thuật nông nghiệp nào?",
    "Tài liệu áp dụng cho cây trồng, vật nuôi hoặc khu vực nào?",
    "Những biện pháp thực hành hoặc phòng ngừa nào được khuyến cáo?",
]
AGRICULTURE_TERMS = {
    "nông nghiệp", "khuyến nông", "cây trồng", "canh tác", "mùa vụ", "thu hoạch",
    "lúa", "cà phê", "hồ tiêu", "rau", "phân bón", "sâu bệnh", "dịch hại",
    "giống", "đất", "tưới", "chăn nuôi", "thủy sản", "bảo vệ thực vật",
    "lâm nghiệp", "rừng", "nông lâm", "khí hậu", "gia súc", "gia cầm",
    "dịch bệnh", "nuôi trồng",
}


def configured_sources() -> list[dict]:
    try:
        source_file = settings.KNOWLEDGE_AGENT_SOURCES_FILE.strip()
        if source_file:
            path = Path(source_file)
            if not path.is_absolute():
                path = Path(__file__).resolve().parents[2] / path
            sources = json.loads(path.read_text(encoding="utf-8"))
        else:
            sources = json.loads(settings.KNOWLEDGE_AGENT_SOURCES_JSON or "[]")
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Cấu hình nguồn Knowledge Agent không phải JSON hợp lệ hoặc không đọc được.") from exc
    if not isinstance(sources, list):
        raise ValueError("KNOWLEDGE_AGENT_SOURCES_JSON phải là một danh sách.")
    clean = []
    for item in sources:
        if not isinstance(item, dict) or not item.get("name") or not item.get("url"):
            continue
        parsed = urlparse(item["url"])
        domain = (item.get("allowed_domain") or parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not domain:
            continue
        clean.append({**item, "allowed_domain": domain})
    return clean


def _canonical_url(url: str) -> str:
    return urldefrag(url.strip())[0]


def _validate_remote_url(url: str, allowed_domain: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("URL tài liệu không hợp lệ.")
    if host != allowed_domain and not host.endswith("." + allowed_domain):
        raise ValueError("URL chuyển sang miền chưa được cho phép.")
    for result in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80)):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError("Nguồn tài liệu phải dùng địa chỉ mạng công khai.")


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError):
        pass
    match = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", value)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    match = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})", value)
    if match:
        try:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            return None
    return None


def _storage_root() -> Path:
    path = Path(settings.RAG_STORAGE_PATH)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path


class KnowledgeIngestionService:
    def fetch(self, url: str, allowed_domain: str) -> httpx.Response:
        start_url = _canonical_url(url)
        timeout = httpx.Timeout(
            connect=settings.EXTERNAL_CONNECT_TIMEOUT_SECONDS,
            read=settings.EXTERNAL_READ_TIMEOUT_SECONDS,
            write=settings.EXTERNAL_WRITE_TIMEOUT_SECONDS,
            pool=settings.EXTERNAL_POOL_TIMEOUT_SECONDS,
        )
        with httpx.Client(timeout=timeout, follow_redirects=False,
                          headers={"User-Agent": "AgriAI-Knowledge-Agent/1.0"}) as client:
            for attempt in range(max(0, settings.EXTERNAL_RETRY_COUNT) + 1):
                current = start_url
                try:
                    for _ in range(4):
                        _validate_remote_url(current, allowed_domain)
                        response = client.get(current)
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                response.raise_for_status()
                            current = _canonical_url(urljoin(current, location))
                            continue
                        response.raise_for_status()
                        if len(response.content) > settings.KNOWLEDGE_AGENT_MAX_BYTES:
                            raise ValueError("Tài liệu nguồn vượt quá giới hạn kích thước tự động.")
                        return response
                    raise ValueError("Nguồn chuyển hướng quá nhiều lần.")
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                    retryable = status is None or status == 429 or status >= 500
                    if not retryable or attempt >= max(0, settings.EXTERNAL_RETRY_COUNT):
                        raise
                    time.sleep(min(2 ** attempt, 4))
        raise RuntimeError("Không thể tải tài liệu sau các lần thử lại.")

    def discover(self, source: dict) -> list[str]:
        start_url = _canonical_url(source["url"])
        if Path(urlparse(start_url).path).suffix.lower() in {".pdf", ".txt", ".md"}:
            return [start_url]
        response = self.fetch(start_url, source["allowed_domain"])
        soup = BeautifulSoup(response.content, "lxml")
        patterns = [str(value).lower() for value in source.get("include_patterns", [])]
        text_patterns = [str(value).lower() for value in source.get("link_text_patterns", [])]
        exclude_patterns = [str(value).lower() for value in source.get("exclude_patterns", [])]
        try:
            regexes = [re.compile(str(value), re.IGNORECASE)
                       for value in source.get("include_regexes", [])]
            exclude_regexes = [re.compile(str(value), re.IGNORECASE)
                               for value in source.get("exclude_regexes", [])]
        except re.error as exc:
            raise ValueError(f"Bộ lọc URL của nguồn không hợp lệ: {exc}") from exc
        found = [start_url] if source.get("include_start_page") else []
        seen = {start_url} if found else set()
        max_documents = int(source.get("max_documents", settings.KNOWLEDGE_AGENT_MAX_DOCUMENTS))
        for anchor in soup.select("a[href]"):
            if len(found) >= max_documents:
                break
            url = _canonical_url(urljoin(str(response.url), anchor.get("href", "")))
            lowered_url = url.lower()
            link_text = anchor.get_text(" ", strip=True).lower()
            path = urlparse(lowered_url).path
            is_document = Path(path).suffix in {".pdf", ".txt", ".md"}
            matches = (any(pattern in lowered_url for pattern in patterns)
                       or any(regex.search(url) for regex in regexes))
            excluded = (any(pattern in lowered_url for pattern in exclude_patterns)
                        or any(regex.search(url) for regex in exclude_regexes))
            text_matches = not text_patterns or any(pattern in link_text for pattern in text_patterns)
            if (url == start_url or url in seen or excluded or not text_matches
                    or (not is_document and not matches)):
                continue
            host = (urlparse(url).hostname or "").lower()
            if host != source["allowed_domain"] and not host.endswith("." + source["allowed_domain"]):
                continue
            seen.add(url)
            found.append(url)
        return found

    def extract(self, url: str, response: httpx.Response) -> dict:
        content_type = response.headers.get("content-type", "").lower()
        suffix = Path(urlparse(url).path).suffix.lower()
        published_at = _parse_date(response.headers.get("last-modified"))
        if suffix == ".pdf" or "application/pdf" in content_type:
            filename = Path(urlparse(url).path).name or "document.pdf"
            pages = extract_pages(filename, response.content,
                                  settings.KNOWLEDGE_AGENT_MAX_BYTES,
                                  settings.KNOWLEDGE_AGENT_MAX_TEXT_CHARS)
            title = Path(filename).stem.replace("-", " ").replace("_", " ").strip()
            filename = Path(filename).stem + ".txt"
        elif suffix in {".txt", ".md"} or content_type.startswith("text/plain"):
            filename = Path(urlparse(url).path).name or "document.txt"
            pages = extract_pages(filename, response.content,
                                  settings.KNOWLEDGE_AGENT_MAX_BYTES,
                                  settings.KNOWLEDGE_AGENT_MAX_TEXT_CHARS)
            title = Path(filename).stem.replace("-", " ").replace("_", " ").strip()
        else:
            soup = BeautifulSoup(response.content, "lxml")
            title_node = None
            for selector in ("meta[property='og:title']", "[itemprop='headline']",
                             ".detail-post h1", ".detail-post h2", ".content-detail h1",
                             ".content-detail h2", "article h1", "article h2"):
                title_node = soup.select_one(selector)
                if title_node:
                    break
            title = ((title_node.get("content") or title_node.get_text(" ", strip=True))
                     if title_node else (soup.title.get_text(" ", strip=True) if soup.title else url))[:300]
            content_root = None
            for selector in ("[itemprop='articleBody']", ".news-details-description",
                             ".noidungchitiet", "article", ".detail-post", ".post-content",
                             ".content-detail", ".entry-content", ".news-detail", "#content", "main"):
                candidate = soup.select_one(selector)
                if candidate and candidate.get_text(" ", strip=True):
                    content_root = candidate
                    break
            content_root = content_root or soup.body or soup
            # ASP.NET/DNN sites wrap the whole page in one form. Keep that wrapper
            # and remove only controls so the article is not deleted with it.
            for selector in ("script", "style", "nav", "footer", "header", "noscript",
                             "input", "button", "select", "textarea"):
                for element in content_root.select(selector):
                    element.decompose()
            text = "\n".join(line.strip() for line in content_root.get_text("\n").splitlines() if line.strip())
            # View/download counters change on every request and must not create a
            # false document version or alter retrieval text.
            for pattern in (
                r"\b(?:số lần xem|lượt xem|xem)\s*:\s*[\d.,]+",
                r"\bsố lần (?:down|tải)\s*:\s*[\d.,]+",
            ):
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            if len(text) > settings.KNOWLEDGE_AGENT_MAX_TEXT_CHARS:
                raise ValueError("Nội dung nguồn vượt quá giới hạn văn bản tự động.")
            pages = [(1, text)]
            filename = (re.sub(r"[^\w.-]+", "-", title, flags=re.UNICODE).strip("-")[:180] or "document") + ".txt"
            for key in ("article:published_time", "datePublished", "date", "pubdate"):
                tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
                if tag and tag.get("content"):
                    published_at = _parse_date(tag["content"]) or published_at
                    break
            published_at = published_at or _parse_date(text[:2000])
        normalized = "\n\n".join(re.sub(r"\s+", " ", text).strip() for _, text in pages if text.strip())
        return {"title": title[:300], "filename": filename, "content": normalized.encode("utf-8"),
                "text": normalized, "published_at": published_at or datetime.utcnow()}

    def quality_report(self, prepared: dict, text: str, questions: list[str]) -> tuple[bool, float, dict]:
        lowered = text.lower()
        term_hits = sorted(term for term in AGRICULTURE_TERMS if term in lowered)
        base_pass = len(text) >= settings.KNOWLEDGE_AGENT_MIN_TEXT_CHARS and len(term_hits) >= 2
        coverage = rag_service.question_coverage(
            prepared, questions or DEFAULT_QUESTIONS, settings.KNOWLEDGE_AGENT_QA_SIMILARITY
        ) if base_pass else {"passed": 0, "total": len(questions or DEFAULT_QUESTIONS), "scores": []}
        semantic_pass = coverage["total"] > 0 and coverage["passed"] > 0
        ratio = coverage["passed"] / coverage["total"] if coverage["total"] else 0
        score = round((0.6 if base_pass else 0.0) + 0.4 * ratio, 4)
        report = {"minimum_length": len(text) >= settings.KNOWLEDGE_AGENT_MIN_TEXT_CHARS,
                  "text_characters": len(text), "agriculture_terms": term_hits,
                  "agriculture_relevant": len(term_hits) >= 2, "question_coverage": coverage}
        return base_pass and semantic_pass, score, report

    def process(self, db: Session, source: dict, url: str) -> str:
        response = self.fetch(url, source["allowed_domain"])
        final_url = str(response.url)
        if "text/html" in response.headers.get("content-type", "").lower():
            soup = BeautifulSoup(response.content, "lxml")
            for anchor in soup.select("a[href]"):
                attachment = _canonical_url(urljoin(final_url, anchor.get("href", "")))
                if Path(urlparse(attachment).path).suffix.lower() != ".pdf":
                    continue
                host = (urlparse(attachment).hostname or "").lower()
                if host == source["allowed_domain"] or host.endswith("." + source["allowed_domain"]):
                    response = self.fetch(attachment, source["allowed_domain"])
                    final_url = str(response.url)
                    break
        extracted = self.extract(final_url, response)
        content_hash = hashlib.sha256(extracted["content"]).hexdigest()
        duplicate = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.ContentHash == content_hash
        ).first()
        if duplicate:
            if duplicate.Status != "failed":
                return "duplicate"
            db.delete(duplicate)
            db.commit()

        canonical = _canonical_url(final_url)
        url_hash = hashlib.sha256(canonical.encode()).hexdigest()
        previous = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.URLHash == url_hash,
            KnowledgeDocument.Status == "approved",
        ).order_by(desc(KnowledgeDocument.Version)).first()
        version = (previous.Version + 1) if previous else 1
        staging = _storage_root() / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        path = staging / f"{content_hash}.txt"
        path.write_bytes(extracted["content"])
        row = KnowledgeDocument(
            SourceName=source["name"], CanonicalURL=canonical, URLHash=url_hash,
            ContentHash=content_hash, Title=extracted["title"], PublishedAt=extracted["published_at"],
            Region=source.get("region") or "Việt Nam", Crop=source.get("crop") or "Nông nghiệp",
            Version=version, Status="pending", StoragePath=str(path),
            SupersedesID=previous.DocumentKey if previous else None,
        )
        db.add(row)
        db.commit()
        try:
            prepared = rag_service.prepare(extracted["filename"], extracted["content"])
            passed, score, report = self.quality_report(
                prepared, extracted["text"], list(source.get("validation_questions") or DEFAULT_QUESTIONS)
            )
            row.QualityScore = score
            row.QualityReport = json.dumps(report, ensure_ascii=False)
            if not passed:
                row.Status = "rejected"
                db.commit()
                return "rejected"
            result = rag_service.publish(SYSTEM_KNOWLEDGE_OWNER, prepared, {
                "source_name": source["name"], "source_url": canonical,
                "published_at": extracted["published_at"].isoformat(), "region": row.Region,
                "crop": row.Crop, "version": version,
            })
            row.RagDocumentID = result["id"]
            row.Status = "approved"
            row.ApprovedAt = datetime.utcnow()
            approved = _storage_root() / "approved"
            approved.mkdir(parents=True, exist_ok=True)
            approved_path = approved / path.name
            path.replace(approved_path)
            row.StoragePath = str(approved_path)
            if previous:
                previous.Status = "superseded"
                if previous.RagDocumentID:
                    rag_service.delete(SYSTEM_KNOWLEDGE_OWNER, previous.RagDocumentID)
            db.commit()
            return "approved"
        except Exception as exc:
            row.Status = "failed"
            row.QualityReport = json.dumps({"error": str(exc)}, ensure_ascii=False)
            db.commit()
            raise

    def run(self, db: Session, force: bool = False) -> dict:
        if not settings.KNOWLEDGE_AGENT_ENABLED and not force:
            return {"status": "disabled", "sources": 0, "discovered": 0}
        sources = configured_sources()
        log = DataIngestionLog(SourceName="configured_sources", JobName="knowledge_agent", Status="running")
        db.add(log)
        db.commit()
        counts = {"approved": 0, "rejected": 0, "duplicate": 0, "failed": 0}
        discovered = 0
        errors = []
        for source in sources:
            try:
                urls = self.discover(source)
            except Exception as exc:
                counts["failed"] += 1
                errors.append(f"{source['name']}: {exc}")
                continue
            discovered += len(urls)
            for url in urls:
                try:
                    counts[self.process(db, source, url)] += 1
                except Exception as exc:
                    counts["failed"] += 1
                    errors.append(f"{url}: {exc}")
                    logger.exception("Knowledge ingestion failed for %s", url)
        log.FinishedAt = datetime.utcnow()
        processed = counts["approved"] + counts["rejected"] + counts["duplicate"]
        log.Status = "success" if not errors else ("partial_success" if processed else "failed")
        log.RecordsFetched = discovered
        log.RecordsSaved = counts["approved"]
        log.ErrorMessage = "\n".join(errors)[:4000] or None
        db.commit()
        return {"status": log.Status, "sources": len(sources), "discovered": discovered, **counts,
                "errors": errors}


knowledge_ingestion_service = KnowledgeIngestionService()
