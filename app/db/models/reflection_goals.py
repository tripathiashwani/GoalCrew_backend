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


class ReflectionGoal(Base):
    __tablename__ = "reflection_goals"
    __table_args__ = (
        Index("idx_reflection_goals_goal", "goal_id"),
        Index("idx_reflection_goals_reflection", "reflection_id"),
        Index("idx_reflection_goals_completed", "completed"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reflection_id = Column(UUID(as_uuid=True), ForeignKey("reflections.id", ondelete="CASCADE"))
    goal_id = Column(UUID(as_uuid=True), ForeignKey("pod_goals.id",ondelete="CASCADE"))
    completed = Column(Boolean, default=False)
    weekly_progress_value = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

    reflection = relationship("Reflection")
    goal = relationship("PodGoal")
