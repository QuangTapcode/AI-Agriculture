from app.core.database import SessionLocal
from app.core.redis_client import redis_client
from app.integrations.market_price_client import market_price_client
from app.repositories.ingestion_repository import finish_ingestion_log, start_ingestion_log
from app.repositories.price_repository import bulk_upsert_market_prices
from app.services.data_quality_service import clean_price_records, save_quarantine, warn_count_mismatch
from app.tasks.celery_app import celery_app


def refresh_market_prices_task(source_name: str | None = None, crop_filter: str | None = None) -> dict:
    db = SessionLocal()
    log = start_ingestion_log(db, "refresh_market_prices", source_name)
    try:
        raw_records = market_price_client.fetch_all(source_name=source_name, crop_filter=crop_filter)
        records, rejected = clean_price_records(raw_records)
        save_quarantine(rejected, source=source_name or "market_price_client")
        result = bulk_upsert_market_prices(db, records)
        warn_count_mismatch(source_name or "market_price_client", len(records), result)
        for record in records:
            redis_client.delete(
                f"price:{record.get('crop_name')}:{record.get('region')}:{record.get('quality_grade', 'grade_1')}"
            )
        status = "success" if not result["errors"] else "partial_success"
        finish_ingestion_log(
            db,
            log,
            status=status,
            records_fetched=len(raw_records),
            records_saved=result["records_saved"] + result["records_updated"],
            error_message="; ".join(result["errors"]) if result["errors"] else None,
        )
        return {
            "status": status,
            "source_name": source_name,
            "records_fetched": len(raw_records),
            "records_clean": len(records),
            **result,
        }
    except Exception as exc:
        finish_ingestion_log(db, log, status="failed", error_message=str(exc))
        return {"status": "failed", "source_name": source_name, "error": str(exc)}
    finally:
        db.close()


def refresh_market_prices() -> dict:
    return refresh_market_prices_task()


if celery_app:
    celery_refresh_market_prices_task = celery_app.task(name="refresh_market_prices_task")(refresh_market_prices_task)
