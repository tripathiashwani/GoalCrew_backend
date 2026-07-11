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


class GoalStreak(Base):
    __tablename__ = "goal_streaks"
    __table_args__ = (
        UniqueConstraint("goal_id", "user_id"),
        Index("idx_streaks_user", "user_id"),
        Index("idx_streaks_goal", "goal_id"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("pod_goals.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_completed_date = Column(Date)
    updated_at = Column(DateTime, onupdate=func.now())

    goal = relationship("PodGoal")
    user = relationship("User")
