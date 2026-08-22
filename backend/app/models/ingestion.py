from sqlalchemy import Column, DateTime, Integer, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class DataIngestionLog(Base):
    __tablename__ = "DataIngestionLogs"

    LogID = Column("LogID", Integer, primary_key=True, index=True)
    SourceName = Column("SourceName", Unicode(100), nullable=True, index=True)
    JobName = Column("JobName", Unicode(100), nullable=False, index=True)
    StartedAt = Column("StartedAt", DateTime, nullable=False, server_default=func.now())
    FinishedAt = Column("FinishedAt", DateTime, nullable=True)
    Status = Column("Status", Unicode(30), nullable=False, default="running")
    RecordsFetched = Column("RecordsFetched", Integer, nullable=False, default=0)
    RecordsSaved = Column("RecordsSaved", Integer, nullable=False, default=0)
    ErrorMessage = Column("ErrorMessage", UnicodeText, nullable=True)

    id = synonym("LogID")
    source_name = synonym("SourceName")
    job_name = synonym("JobName")
    started_at = synonym("StartedAt")
    finished_at = synonym("FinishedAt")
    status = synonym("Status")
    records_fetched = synonym("RecordsFetched")
    records_saved = synonym("RecordsSaved")
    error_message = synonym("ErrorMessage")
