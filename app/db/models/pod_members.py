import uuid
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Float,
    Text,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

class PodMember(Base):
    __tablename__ = "pod_members"
    __table_args__ = (UniqueConstraint("pod_id", "user_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pod_id = Column(UUID(as_uuid=True), ForeignKey("pods.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))
    role = Column(String, default="member")
    joined_via = Column(String)
    joined_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)

    pod = relationship("Pod", back_populates="members")
    user = relationship("User")
