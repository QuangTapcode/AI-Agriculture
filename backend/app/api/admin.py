import json
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.ingestion import DataIngestionLog
from app.services.market_news_service import market_news_service
from app.tasks.alert_tasks import check_price_alerts_task
from app.tasks.crawler_tasks import run_price_crawler as crawl_sources_task
from app.tasks.forecast_tasks import refresh_harvest_forecasts_task

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/ingestion/run")
async def run_ingestion(job_name: str, source_name: str | None = None, crop_filter: str | None = None):
    if job_name == "price_crawler":
        return crawl_sources_task(source_name=source_name, crop_filter=crop_filter)
    if job_name == "market_news":
        return market_news_service.refresh_news()
    if job_name == "price_alerts":
        return check_price_alerts_task()
    if job_name == "harvest_forecasts":
        return refresh_harvest_forecasts_task()
    return {
        "status": "failed",
        "error": "Unsupported job_name",
        "supported_jobs": ["price_crawler", "market_news", "price_alerts", "harvest_forecasts"],
    }


@router.get("/quarantine")
async def get_quarantine(
    days: int = Query(1, ge=1, le=30, description="Số ngày gần nhất"),
    source: str | None = Query(None, description="Lọc theo source"),
    reason: str | None = Query(None, description="Lọc theo reject reason"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Xem rejected price records trong quarantine store.

    GET /api/admin/quarantine?days=7&source=thitruongnongsan_price
    """
    base = Path(getattr(settings, "FIRECRAWL_RAW_STORAGE_PATH", "storage/raw_crawl")) / "quarantine"
    entries: list[dict] = []

    for offset in range(days):
        day = date.today() - timedelta(days=offset)
        path = base / f"{day.strftime('%Y%m%d')}.jsonl"
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if source and entry.get("source") != source:
                    continue
                if reason and reason not in (entry.get("reason") or ""):
                    continue
                entries.append(entry)
        except Exception:
            continue

    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)
    total = len(entries)
    summary: dict[str, int] = {}
    for e in entries:
        r = e.get("reason", "unknown")
        summary[r] = summary.get(r, 0) + 1

    return {
        "total": total,
        "shown": min(total, limit),
        "summary": summary,
        "entries": entries[:limit],
    }


@router.get("/ingestion-logs")
async def get_ingestion_logs(
    job_name: str | None = Query(None, description="Lọc theo job (e.g. refresh_market_news)"),
    status: str | None = Query(None, description="success | failed | partial_success"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Xem lịch sử ingestion logs.

    GET /api/admin/ingestion-logs?job_name=refresh_market_prices&days=3
    """
    since = date.today() - timedelta(days=days)
    q = db.query(DataIngestionLog).filter(DataIngestionLog.StartedAt >= since)
    if job_name:
        q = q.filter(DataIngestionLog.JobName == job_name)
    if status:
        q = q.filter(DataIngestionLog.Status == status)
    rows = q.order_by(desc(DataIngestionLog.StartedAt)).limit(limit).all()

    return {
        "total": len(rows),
        "logs": [
            {
                "log_id": r.LogID,
                "job_name": r.JobName,
                "source_name": r.SourceName,
                "status": r.Status,
                "records_fetched": r.RecordsFetched,
                "records_saved": r.RecordsSaved,
                "started_at": r.StartedAt.isoformat() if r.StartedAt else None,
                "finished_at": r.FinishedAt.isoformat() if r.FinishedAt else None,
                "error": r.ErrorMessage,
            }
            for r in rows
        ],
    }


@router.get("/crawler/status")
async def get_crawler_status(db: Session = Depends(get_db)):
    """Trạng thái crawler: lần chạy gần nhất của mỗi job.

    GET /api/admin/crawler/status
    """
    rows = (
        db.query(DataIngestionLog)
        .order_by(desc(DataIngestionLog.StartedAt))
        .limit(200)
        .all()
    )
    # Keep most recent log per job_name
    seen: set[str] = set()
    latest: list[dict] = []
    for r in rows:
        key = r.JobName or "unknown"
        if key in seen:
            continue
        seen.add(key)
        elapsed = None
        if r.StartedAt and r.FinishedAt:
            elapsed = int((r.FinishedAt - r.StartedAt).total_seconds())
        latest.append({
            "job_name": r.JobName,
            "source_name": r.SourceName,
            "status": r.Status,
            "records_fetched": r.RecordsFetched,
            "records_saved": r.RecordsSaved,
            "last_run": r.StartedAt.isoformat() if r.StartedAt else None,
            "duration_seconds": elapsed,
            "error": r.ErrorMessage,
        })
    return {"jobs": latest}
