"""Bounded, human-reviewed discovery of new knowledge sources.

The nightly crawler follows links found on configured registry pages. A
query-scoped crop search can additionally inspect isolated browser search
results, but accepts only registered or official Vietnamese domains. Neither
path asks an LLM to invent URLs or promotes a new source into the RAG allow-list
automatically.
"""

import hashlib
import ipaddress
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeSourceCandidate
from app.services.ai_intent_service import normalize_user_text
from app.services.knowledge_ingestion_service import KnowledgeIngestionService, configured_sources
from app.services.private_browser_search_service import private_browser_search_service

logger = logging.getLogger(__name__)


class SourceDiscoveryService:
    """Discover external source links while keeping trust and approval explicit."""

    _blocked_extensions = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".mp4", ".css", ".js"}
    _blocked_hosts = {"facebook.com", "www.facebook.com", "youtube.com", "www.youtube.com", "tiktok.com", "www.tiktok.com"}

    def __init__(self):
        self.ingestion = KnowledgeIngestionService()

    @staticmethod
    def _canonical(url: str) -> str:
        return urldefrag(url.strip())[0].rstrip("/") or url

    @staticmethod
    def _is_public_host(host: str) -> bool:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return True
        return address.is_global

    @staticmethod
    def _is_official_domain(host: str) -> bool:
        return host == "gov.vn" or host.endswith(".gov.vn") or host.endswith(".edu.vn")

    @staticmethod
    def _looks_agricultural(url: str, text: str) -> bool:
        haystack = f"{url} {text}".lower()
        return any(term in haystack for term in (
            "agri", "nong", "nông", "crop", "farm", "canh", "lua", "lúa",
            "rice", "soil", "dat", "đất", "weather", "thuy", "thủy",
            "guide", "huong", "hướng",
        ))

    def _candidate_from_anchor(
        self,
        seed: dict,
        href: str,
        text: str,
        known_domains: set[str],
        *,
        allow_seed_domain: bool = False,
    ) -> dict | None:
        url = self._canonical(urljoin(seed["url"], href or ""))
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not host or not self._is_public_host(host):
            return None
        if host in self._blocked_hosts or any(host.endswith("." + blocked) for blocked in self._blocked_hosts):
            return None
        if parsed.path.lower().endswith(tuple(self._blocked_extensions)):
            return None
        seed_domain = (seed.get("allowed_domain") or urlparse(seed["url"]).hostname or "").lower()
        if not allow_seed_domain and (host == seed_domain or host.endswith("." + seed_domain) or host in known_domains):
            return None
        official = self._is_official_domain(host)
        if not official and not self._looks_agricultural(url, text):
            return None
        confidence = 0.9 if official else (0.65 if host.endswith(".vn") else 0.4)
        return {
            "name": (text.strip() or host)[:200],
            "url": url,
            "domain": host,
            "discovered_from": seed.get("name") or seed["url"],
            "discovery_reason": "Liên kết được tìm thấy trên trang nguồn đã cấu hình.",
            "confidence_score": confidence,
            "is_official_domain": official,
            "status": "pending",
        }

    @staticmethod
    def _query_variants(
        keywords: list[str],
        *,
        crop: str | None = None,
        region: str | None = None,
    ) -> list[str]:
        """Build a few deterministic, source-oriented browser queries.

        The browser receives extracted topic fields only.  Crop questions get
        an explicit official-domain search so a full legacy registry cannot
        hide newer government or university material.
        """
        crop_text = " ".join(str(crop or "").split())
        region_text = " ".join(str(region or "").split())
        normalized_crop = normalize_user_text(crop_text)
        normalized_keywords = [str(value).strip() for value in keywords if str(value).strip()]
        variants: list[str] = []

        phrase = next(
            (value for value in normalized_keywords
             if normalized_crop and normalize_user_text(value).startswith(normalized_crop + " ")),
            None,
        )
        if crop_text:
            topic = phrase or crop_text
            first = " ".join(part for part in (topic, "kỹ thuật trồng", region_text, "site:gov.vn") if part)
            variants.append(first)
            variants.append(" ".join(part for part in (crop_text, "khuyến nông", region_text, "site:gov.vn") if part))
            variants.append(" ".join(part for part in (crop_text, "cultivation", region_text, "site:edu.vn") if part))

        base = " ".join(dict.fromkeys(
            part for part in (crop_text, region_text, *normalized_keywords) if part
        ))
        if base:
            variants.append(base)

        return list(dict.fromkeys(" ".join(value.split()) for value in variants if value.strip()))

    @staticmethod
    def _topic_source_hints(crop: str | None) -> list[dict]:
        """Load verified topic fallbacks when a search provider returns noise.

        These are source URLs, not generated answers.  They are still sent
        through the normal fetch, hash, embedding, and quality gates; a hint
        can never bypass ingestion validation.
        """
        crop_term = normalize_user_text(crop or "")
        if not crop_term:
            return []
        path = Path(__file__).resolve().parents[2] / "config" / "knowledge_topic_sources.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, json.JSONDecodeError):
            logger.warning("Could not load topic source hints from %s", path)
            return []
        hints = payload.get(crop_term, []) if isinstance(payload, dict) else []
        return [item for item in hints if isinstance(item, dict) and item.get("url") and item.get("allowed_domain")]

    def _discover_browser_candidates(
        self,
        keywords: list[str],
        *,
        crop: str | None,
        region: str | None,
        seeds: list[dict],
        terms: list[str],
        crop_terms: set[str],
        seen: set[str],
        limit: int,
        warnings: list[str] | None,
    ) -> tuple[list[dict], list[tuple[str, dict]]]:
        """Search the browser first and return only safe candidate URLs.

        This method never opens a result destination.  The returned URLs are
        still fetched by the ingestion service, where hash, extraction,
        quality, question checks and embedding decide whether they enter RAG.
        """
        allowed_sources: list[tuple[str, dict]] = []
        for seed in seeds:
            allowed_domain = (seed.get("allowed_domain") or urlparse(seed["url"]).hostname or "").lower()
            if allowed_domain:
                allowed_sources.append((allowed_domain, seed))

        web_candidates: list[dict] = []
        for query in self._query_variants(keywords, crop=crop, region=region):
            try:
                web_results = private_browser_search_service.search(
                    query, max_results=getattr(settings, "KNOWLEDGE_BROWSER_SEARCH_MAX_RESULTS", 10),
                )
                for result in web_results:
                    url = self._canonical(result.get("url", ""))
                    parsed = urlparse(url)
                    host = (parsed.hostname or "").lower().rstrip(".")
                    if not url or url in seen or parsed.scheme not in {"http", "https"}:
                        continue
                    if not self._is_public_host(host):
                        continue
                    if any(host == blocked or host.endswith("." + blocked) for blocked in self._blocked_hosts):
                        continue
                    if parsed.path.lower().endswith(tuple(self._blocked_extensions)):
                        continue

                    source = next((source for domain, source in allowed_sources
                                   if host == domain or host.endswith("." + domain)), None)
                    official = self._is_official_domain(host)
                    if source is None and not official:
                        continue
                    source_is_new = source is None

                    searchable_text = normalize_user_text(
                        f"{url} {result.get('title', '')} {result.get('snippet', '')}"
                    )
                    if crop_terms and not any(term in searchable_text for term in crop_terms):
                        continue
                    if terms and not any(term in searchable_text for term in terms):
                        continue

                    if source is None:
                        source = {
                            "name": (result.get("title") or host)[:150],
                            "url": url,
                            "allowed_domain": host,
                            "max_documents": 8,
                            "include_start_page": True,
                            "region": region or "Việt Nam",
                            "crop": crop or "Nông nghiệp",
                        }
                    if source is not None and not source_is_new and (crop or region):
                        # A configured domain can serve multiple crops. Keep
                        # its allow-list identity while attaching this
                        # query scope to the ingested document metadata.
                        source = {
                            **source,
                            "crop": crop or source.get("crop"),
                            "region": region or source.get("region"),
                        }
                    candidate = {
                        "name": (result.get("title") or host)[:200],
                        "url": url,
                        "domain": host,
                        "discovered_from": "Tìm kiếm web trong phiên trình duyệt riêng.",
                        "discovery_reason": (
                            "Tìm thấy qua tìm kiếm web theo chủ đề cây trồng; "
                            "miền chính thức chưa có trong registry."
                            if source_is_new else
                            "Kết quả khớp từ khóa trên miền đã cấu hình."
                        ),
                        "confidence_score": 0.9 if official else 1.0,
                        "is_official_domain": official,
                        "source_is_new": source_is_new,
                        "source": source,
                    }
                    seen.add(url)
                    web_candidates.append(candidate)

                # One accepted new official source is enough to give the
                # worker a fresh domain. Avoid repeated browser launches when
                # the first query already found one.
                if crop_terms and any(item.get("source_is_new") for item in web_candidates):
                    break
                if not crop_terms and len(web_candidates) >= limit:
                    break
            except Exception as exc:
                logger.warning("Private browser search unavailable for %r: %s", query, exc)
                if warnings is not None and not warnings:
                    warnings.append("Không dùng được trình duyệt tìm kiếm; kiểm tra Playwright, Chromium và kết nối mạng.")

        # Search providers can return unrelated pages or be temporarily
        # degraded. Keep a small, verified catalog of crop-specific official
        # pages as a deterministic fallback. These hints are treated exactly
        # like browser results and remain subject to ingestion quality gates.
        if crop_terms and not any(item.get("source_is_new") for item in web_candidates):
            for hint in self._topic_source_hints(crop):
                url = self._canonical(hint.get("url", ""))
                parsed = urlparse(url)
                host = (parsed.hostname or "").lower().rstrip(".")
                if not url or url in seen or parsed.scheme not in {"http", "https"}:
                    continue
                if not self._is_public_host(host) or not self._is_official_domain(host):
                    continue
                source = next((source for domain, source in allowed_sources
                               if host == domain or host.endswith("." + domain)), None)
                source_is_new = source is None
                if source is None:
                    source = hint
                elif crop or region:
                    source = {
                        **source,
                        "crop": crop or source.get("crop"),
                        "region": region or source.get("region"),
                    }
                searchable_text = normalize_user_text(
                    f"{url} {hint.get('name', '')} {hint.get('crop', '')}"
                )
                if not any(term in searchable_text for term in crop_terms):
                    continue
                if terms and not any(term in searchable_text for term in terms):
                    continue
                web_candidates.append({
                    "name": (hint.get("name") or host)[:200],
                    "url": url,
                    "domain": host,
                    "discovered_from": "Danh mục nguồn chính thức theo chủ đề cây trồng.",
                    "discovery_reason": (
                        "Nguồn chính thức được gợi ý theo chủ đề cây trồng sau khi "
                        "tìm kiếm web không trả kết quả phù hợp."
                    ),
                    "confidence_score": 0.9,
                    "is_official_domain": True,
                    "source_is_new": source_is_new,
                    "source": source,
                })
                seen.add(url)
                if sum(1 for item in web_candidates if item.get("source_is_new")) >= limit:
                    break

        return web_candidates, allowed_sources

    def discover_for_query(
        self,
        keywords: list[str],
        *,
        crop: str | None = None,
        region: str | None = None,
        sources: list[dict] | None = None,
        max_candidates: int | None = None,
        warnings: list[str] | None = None,
    ) -> list[dict]:
        """Search the browser first, then supplement it with configured registries."""
        seeds = sources if sources is not None else configured_sources()
        terms = [normalize_user_text(term) for term in keywords if normalize_user_text(term)]
        crop_term = normalize_user_text(crop or "")
        crop_terms = {crop_term} if crop_term else set()
        if crop_term == "nho":
            crop_terms.update({"grape", "vitis"})
        limit = max(1, int(max_candidates or getattr(settings, "KNOWLEDGE_QUERY_DISCOVERY_MAX_CANDIDATES", 3)))
        seen: set[str] = set()

        # This service is called after RAG has no usable answer. Start with a
        # fresh browser search so missing topics can expand beyond the static
        # registry. The registry remains a trusted supplement when search is
        # unavailable or returns fewer candidates than requested.
        web_candidates: list[dict] = []
        allowed_sources: list[tuple[str, dict]] = []
        browser_enabled = getattr(settings, "KNOWLEDGE_BROWSER_SEARCH_ENABLED", True)
        if browser_enabled or crop_terms:
            web_candidates, allowed_sources = self._discover_browser_candidates(
                keywords,
                crop=crop,
                region=region,
                seeds=seeds,
                terms=terms,
                crop_terms=crop_terms,
                seen=seen,
                limit=limit,
                warnings=warnings,
            )

        # Browser results are the primary candidates. For crop queries, newly
        # discovered official domains are preferred over already configured
        # domains. Registry candidates are appended below only if quota remains.
        if crop_terms:
            fresh = [item for item in web_candidates if item.get("source_is_new")]
            existing = [item for item in web_candidates if not item.get("source_is_new")]
            found = (fresh + existing)[:limit]
        else:
            found = web_candidates[:limit]

        for seed in seeds:
            if len(found) >= limit:
                break
            try:
                response = self.ingestion.fetch(seed["url"], seed["allowed_domain"])
                content_type = response.headers.get("content-type", "").lower()
                if "html" not in content_type and not response.text.lstrip().startswith("<"):
                    continue
                soup = BeautifulSoup(response.content, "lxml")
                labels = {
                    self._canonical(urljoin(str(response.url), anchor.get("href", ""))): anchor.get_text(" ", strip=True)
                    for anchor in soup.select("a[href]")
                }
                # Reuse each source's configured include/exclude filters. This
                # prevents a query from turning ordinary navigation links into
                # ingestion candidates.
                urls = self.ingestion.discover(seed, scan_limit=max(limit * 4, limit))
                for url in urls:
                    if len(found) >= limit or url in seen:
                        continue
                    label = labels.get(url, "")
                    candidate = self._candidate_from_anchor(
                        seed, url, label, set(), allow_seed_domain=True,
                    )
                    if not candidate:
                        continue
                    document_text = normalize_user_text(f"{candidate['url']} {label}")
                    # A crop-scoped question must not ingest a generic
                    # cultivation page just because "trồng trọt" appears
                    # in the seed registry name.
                    if crop_terms and not any(term in document_text for term in crop_terms):
                        continue
                    haystack = normalize_user_text(f"{document_text} {seed.get('name', '')}")
                    if terms and not any(term in haystack for term in terms):
                        continue
                    seen.add(candidate["url"])
                    candidate["source"] = seed
                    candidate["discovery_reason"] = "Khớp từ khóa của câu hỏi trên nguồn chính thức đã cấu hình."
                    found.append(candidate)
            except Exception as exc:
                # One unavailable registry must not prevent other configured
                # official sources from answering the same question.
                logger.warning("Query discovery skipped source %s: %s", seed.get("name") or seed.get("url"), exc)
        return found[:limit]

    def record_query_source_candidate(self, db: Session, candidate: dict) -> dict:
        """Save a newly found official domain for explicit future source approval."""
        url = self._canonical(candidate["url"])
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        existing = db.query(KnowledgeSourceCandidate).filter_by(URLHash=url_hash).first()
        if existing:
            return self.serialize(existing)

        row = KnowledgeSourceCandidate(
            Name=(candidate.get("name") or candidate.get("domain") or "Nguồn web")[:200],
            URL=url,
            URLHash=url_hash,
            Domain=(candidate.get("domain") or urlparse(url).hostname or "").lower(),
            DiscoveredFrom=candidate.get("discovered_from"),
            DiscoveryReason=candidate.get("discovery_reason"),
            ConfidenceScore=candidate.get("confidence_score"),
            Status="pending",
            IsOfficialDomain=bool(candidate.get("is_official_domain")),
            CheckedAt=datetime.utcnow(),
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            existing = db.query(KnowledgeSourceCandidate).filter_by(URLHash=url_hash).first()
            if existing:
                return self.serialize(existing)
            raise
        return self.serialize(row)

    def discover(self, sources: list[dict] | None = None, *, max_candidates: int | None = None) -> list[dict]:
        sources = sources if sources is not None else configured_sources()
        limit = max(1, int(max_candidates or getattr(settings, "SOURCE_DISCOVERY_MAX_CANDIDATES", 100)))
        known_domains = {
            (source.get("allowed_domain") or urlparse(source["url"]).hostname or "").lower()
            for source in sources
        }
        found: list[dict] = []
        seen: set[str] = set()
        for seed in sources:
            if len(found) >= limit:
                break
            response = self.ingestion.fetch(seed["url"], seed["allowed_domain"])
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type and not response.text.lstrip().startswith("<"):
                continue
            soup = BeautifulSoup(response.content, "lxml")
            anchors = list(soup.select("a[href]"))
            anchors.extend(soup.select("link[href]"))
            for anchor in anchors:
                candidate = self._candidate_from_anchor(
                    seed,
                    anchor.get("href", ""),
                    anchor.get_text(" ", strip=True),
                    known_domains,
                )
                if not candidate or candidate["url"] in seen:
                    continue
                seen.add(candidate["url"])
                found.append(candidate)
                if len(found) >= limit:
                    break
        return found

    def run(self, db: Session, *, sources: list[dict] | None = None, max_candidates: int | None = None) -> dict:
        sources = sources if sources is not None else configured_sources()
        total_limit = max(1, int(max_candidates or getattr(settings, "SOURCE_DISCOVERY_MAX_CANDIDATES", 100)))
        candidates: list[dict] = []
        source_results: list[dict] = []
        errors = 0
        for seed in sources:
            remaining = total_limit - sum(item["discovered"] for item in source_results)
            if remaining <= 0:
                break
            try:
                discovered = self.discover([seed], max_candidates=remaining)
                created = duplicates = 0
                for item in discovered:
                    url_hash = hashlib.sha256(item["url"].encode("utf-8")).hexdigest()
                    if db.query(KnowledgeSourceCandidate).filter_by(URLHash=url_hash).first():
                        duplicates += 1
                        continue
                    db.add(KnowledgeSourceCandidate(
                        Name=item["name"], URL=item["url"], URLHash=url_hash,
                        Domain=item["domain"], DiscoveredFrom=item["discovered_from"],
                        DiscoveryReason=item["discovery_reason"],
                        ConfidenceScore=item["confidence_score"],
                        Status="pending", IsOfficialDomain=item["is_official_domain"],
                        CheckedAt=datetime.utcnow(),
                    ))
                    created += 1
                    candidates.append(item)
                source_results.append({"source_name": seed.get("name"), "discovered": len(discovered), "created": created, "duplicates": duplicates, "error": None})
            except Exception as exc:
                errors += 1
                source_results.append({"source_name": seed.get("name"), "discovered": 0, "created": 0, "duplicates": 0, "error": str(exc)})
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # A concurrent run can win the unique URL race; report the run as
            # completed and let the next run deduplicate from the database.
            logger.info("source discovery encountered a concurrent duplicate")
        return {
            "status": "partial_success" if errors else "success",
            "sources_scanned": len(sources),
            "discovered": sum(item["discovered"] for item in source_results),
            "created": len(candidates),
            "duplicates": sum(item["duplicates"] for item in source_results),
            "errors": errors,
            "source_results": source_results,
            "candidates": candidates,
        }

    def list_candidates(self, db: Session, status: str | None = "pending", limit: int = 100) -> list[dict]:
        query = db.query(KnowledgeSourceCandidate)
        if status and status != "all":
            query = query.filter(KnowledgeSourceCandidate.Status == status)
        rows = query.order_by(desc(KnowledgeSourceCandidate.CreatedAt)).limit(limit).all()
        return [self.serialize(row) for row in rows]

    @staticmethod
    def serialize(row: KnowledgeSourceCandidate) -> dict:
        return {
            "id": row.CandidateID,
            "name": row.Name,
            "url": row.URL,
            "domain": row.Domain,
            "discovered_from": row.DiscoveredFrom,
            "discovery_reason": row.DiscoveryReason,
            "confidence_score": row.ConfidenceScore,
            "status": row.Status,
            "is_official_domain": row.IsOfficialDomain,
            "checked_at": row.CheckedAt.isoformat() if row.CheckedAt else None,
            "created_at": row.CreatedAt.isoformat() if row.CreatedAt else None,
            "last_error": row.LastError,
        }

    def set_status(self, db: Session, candidate_id: int, status: str) -> dict:
        if status not in {"pending", "approved", "rejected"}:
            raise ValueError("Trạng thái nguồn không hợp lệ.")
        row = db.get(KnowledgeSourceCandidate, candidate_id)
        if not row:
            raise LookupError("Không tìm thấy nguồn đang chờ kiểm tra.")
        row.Status = status
        row.UpdatedAt = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return self.serialize(row)


source_discovery_service = SourceDiscoveryService()
