# Backend and RAG context

The backend is a FastAPI application using SQLAlchemy, database-backed user data, scheduled ingestion, and local/remote AI integrations. API responses expose source, freshness, cache, warning, and mock-data metadata.

Persist user-submitted data before reporting success. Optional notification delivery must not destroy an already stored request. Public endpoints require strict validation and rate limiting.
