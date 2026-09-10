from sqlalchemy import Column, DateTime, ForeignKey, Integer, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class AIConversation(Base):
    __tablename__ = "AIConversations"

    ConvID = Column("ConvID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=True, index=True)
    SessionID = Column("SessionID", Unicode(100), nullable=True)
    UserMessage = Column("UserMessage", UnicodeText, nullable=False)
    AIResponse = Column("AIResponse", UnicodeText, nullable=False)
    Topic = Column("Topic", Unicode(50), nullable=True)
    RelatedCropID = Column("RelatedCropID", Integer, ForeignKey("CropTypes.CropID"), nullable=True)
    ContextSnapshot = Column("ContextSnapshot", UnicodeText, nullable=True)
    Provider = Column("Provider", Unicode(50), nullable=True)
    ModelName = Column("ModelName", Unicode(100), nullable=True)
    TokenUsage = Column("TokenUsage", UnicodeText, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True, index=True)

    id = synonym("ConvID")
    user_id = synonym("UserID")
    session_id = synonym("SessionID")
    user_message = synonym("UserMessage")
    ai_response = synonym("AIResponse")
    topic = synonym("Topic")
    related_crop_id = synonym("RelatedCropID")
    context_snapshot = synonym("ContextSnapshot")
    provider = synonym("Provider")
    model_name = synonym("ModelName")
    token_usage = synonym("TokenUsage")
    created_at = synonym("CreatedAt")
