from app.core.config import settings
from app.core.database import SessionLocal
from app.services.source_discovery_service import source_discovery_service
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.source_discovery_tasks.discover_knowledge_sources")
def discover_knowledge_sources():
    if not settings.SOURCE_DISCOVERY_ENABLED:
        return {"status": "disabled", "created": 0, "discovered": 0}
    db = SessionLocal()
    try:
        return source_discovery_service.run(db)
    finally:
        db.close()
