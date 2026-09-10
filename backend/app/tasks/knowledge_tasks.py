from app.core.database import SessionLocal
from app.services.knowledge_ingestion_service import knowledge_ingestion_service
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.knowledge_tasks.ingest_knowledge_sources")
def ingest_knowledge_sources():
    db = SessionLocal()
    try:
        return knowledge_ingestion_service.run(db)
    finally:
        db.close()
