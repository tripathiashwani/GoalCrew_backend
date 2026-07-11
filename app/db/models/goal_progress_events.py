import uuid
from sqlalchemy import (
    Column,
    Index,
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

class GoalProgressEvent(Base):
    __tablename__ = "goal_progress_events"
    __table_args__ = (
        Index("idx_progress_user", "user_id"),
        Index("idx_progress_goal", "goal_id"),
        Index("idx_progress_date", "progress_date"),
        Index("idx_progress_user_goal", "user_id", "goal_id"),
        Index("idx_progress_user_goal_date", "user_id", "goal_id", "progress_date"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pod_id = Column(UUID(as_uuid=True), ForeignKey("pods.id", ondelete="CASCADE"))
    goal_id = Column(UUID(as_uuid=True), ForeignKey("pod_goals.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True),ForeignKey("users.id", ondelete="CASCADE") )
    reflection_id = Column(UUID(as_uuid=True), ForeignKey("reflections.id",ondelete="CASCADE"))
    progress_date = Column(Date, nullable=False)
    frequency_type = Column(String)
    completed = Column(Boolean)
    progress_value = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

    goal = relationship("PodGoal")
    user = relationship("User")
  
