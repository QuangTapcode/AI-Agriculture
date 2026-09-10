from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText, UniqueConstraint
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class KnowledgeDocument(Base):
    """A discovered document and its promotion state in the shared knowledge base."""

    __tablename__ = "KnowledgeDocuments"
    __table_args__ = (UniqueConstraint("ContentHash", name="uq_knowledge_documents_content_hash"),)

    DocumentKey = Column("DocumentKey", Integer, primary_key=True, index=True)
    SourceName = Column("SourceName", Unicode(150), nullable=False, index=True)
    CanonicalURL = Column("CanonicalURL", UnicodeText, nullable=False)
    URLHash = Column("URLHash", Unicode(64), nullable=False, index=True)
    ContentHash = Column("ContentHash", Unicode(64), nullable=False)
    Title = Column("Title", Unicode(300), nullable=False)
    PublishedAt = Column("PublishedAt", DateTime, nullable=True)
    Region = Column("Region", Unicode(100), nullable=True)
    Crop = Column("Crop", Unicode(100), nullable=True)
    Version = Column("Version", Integer, nullable=False, default=1)
    Status = Column("Status", Unicode(30), nullable=False, default="pending", index=True)
    QualityScore = Column("QualityScore", Float, nullable=True)
    QualityReport = Column("QualityReport", UnicodeText, nullable=True)
    RagDocumentID = Column("RagDocumentID", Unicode(64), nullable=True, index=True)
    StoragePath = Column("StoragePath", Unicode(500), nullable=True)
    FetchedAt = Column("FetchedAt", DateTime, nullable=False, server_default=func.now())
    ApprovedAt = Column("ApprovedAt", DateTime, nullable=True)
    SupersedesID = Column("SupersedesID", Integer, ForeignKey("KnowledgeDocuments.DocumentKey"), nullable=True)

    id = synonym("DocumentKey")
    source_name = synonym("SourceName")
    canonical_url = synonym("CanonicalURL")
    content_hash = synonym("ContentHash")
    status = synonym("Status")
