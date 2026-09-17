from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText, UniqueConstraint
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


class KnowledgeSourceCandidate(Base):
    """A source URL discovered from an allow-listed knowledge source.

    Candidates are deliberately separate from ``KnowledgeDocument`` and the
    active JSON registry. Discovery may suggest a source, but it must never
    silently change what the RAG agent trusts.
    """

    __tablename__ = "KnowledgeSourceCandidates"
    __table_args__ = (UniqueConstraint("URLHash", name="uq_knowledge_source_candidate_url_hash"),)

    CandidateID = Column("CandidateID", Integer, primary_key=True, index=True)
    Name = Column("Name", Unicode(200), nullable=False)
    URL = Column("URL", UnicodeText, nullable=False)
    URLHash = Column("URLHash", Unicode(64), nullable=False, index=True)
    Domain = Column("Domain", Unicode(255), nullable=False, index=True)
    DiscoveredFrom = Column("DiscoveredFrom", Unicode(200), nullable=True)
    DiscoveryReason = Column("DiscoveryReason", UnicodeText, nullable=True)
    ConfidenceScore = Column("ConfidenceScore", Float, nullable=True)
    Status = Column("Status", Unicode(30), nullable=False, default="pending", index=True)
    IsOfficialDomain = Column("IsOfficialDomain", Boolean, nullable=False, default=False)
    CheckedAt = Column("CheckedAt", DateTime, nullable=True)
    LastError = Column("LastError", UnicodeText, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, nullable=False, server_default=func.now())
    UpdatedAt = Column("UpdatedAt", DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    id = synonym("CandidateID")
    url = synonym("URL")
    status = synonym("Status")


class KnowledgeDiscoveryJob(Base):
    """A bounded, asynchronous source discovery request started by a chat query."""

    __tablename__ = "KnowledgeDiscoveryJobs"

    JobID = Column("JobID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, nullable=True, index=True)
    Question = Column("Question", UnicodeText, nullable=False)
    QuestionHash = Column("QuestionHash", Unicode(64), nullable=False, index=True)
    Keywords = Column("Keywords", UnicodeText, nullable=False, default="[]")
    Intent = Column("Intent", Unicode(50), nullable=True, index=True)
    Crop = Column("Crop", Unicode(100), nullable=True)
    Region = Column("Region", Unicode(100), nullable=True)
    Status = Column("Status", Unicode(30), nullable=False, default="queued", index=True)
    CandidatesFound = Column("CandidatesFound", Integer, nullable=False, default=0)
    DocumentsProcessed = Column("DocumentsProcessed", Integer, nullable=False, default=0)
    DocumentsIndexed = Column("DocumentsIndexed", Integer, nullable=False, default=0)
    ErrorMessage = Column("ErrorMessage", UnicodeText, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, nullable=False, server_default=func.now())
    StartedAt = Column("StartedAt", DateTime, nullable=True)
    FinishedAt = Column("FinishedAt", DateTime, nullable=True)

    id = synonym("JobID")
    status = synonym("Status")
