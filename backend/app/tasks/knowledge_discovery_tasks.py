from app.core.database import SessionLocal
from app.services.knowledge_discovery_service import knowledge_discovery_service
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.knowledge_discovery_tasks.discover_for_question")
def discover_for_question(job_id: int):
    db = SessionLocal()
    try:
        return knowledge_discovery_service.run(db, job_id)
    finally:
        db.close()

