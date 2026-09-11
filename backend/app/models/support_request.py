from sqlalchemy import Column, DateTime, Integer, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class SupportRequest(Base):
    __tablename__ = "SupportRequests"

    RequestID = Column("RequestID", Integer, primary_key=True, index=True)
    Name = Column("Name", Unicode(100), nullable=False)
    Email = Column("Email", Unicode(254), nullable=True)
    Phone = Column("Phone", Unicode(30), nullable=True)
    Topic = Column("Topic", Unicode(50), nullable=False)
    Message = Column("Message", UnicodeText, nullable=False)
    Status = Column("Status", Unicode(20), nullable=False, default="new", index=True)
    IpHash = Column("IpHash", Unicode(64), nullable=False, index=True)
    ContactHash = Column("ContactHash", Unicode(64), nullable=False, index=True)
    CreatedAt = Column("CreatedAt", DateTime, nullable=False, server_default=func.now(), index=True)

    id = synonym("RequestID")
    name = synonym("Name")
    email = synonym("Email")
    phone = synonym("Phone")
    topic = synonym("Topic")
    message = synonym("Message")
    status = synonym("Status")
    created_at = synonym("CreatedAt")
