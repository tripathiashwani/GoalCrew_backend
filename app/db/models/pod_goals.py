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

class PodGoal(Base):
    __tablename__ = "pod_goals"
    __table_args__ = (
        Index("idx_pod_goals_pod", "pod_id"),
        Index("idx_pod_goals_status", "status"),
        Index("idx_pod_goals_category", "category"),
        Index("idx_pod_goals_frequency", "frequency_type"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pod_id = Column(UUID(as_uuid=True), ForeignKey("pods.id", ondelete="CASCADE"))
    # Core identity
    title = Column(String, nullable=False)
    category = Column(String)

    # Measurement
    requires_measurement = Column(Boolean, default=False, nullable=True)
    description = Column(Text)
    measurement_unit = Column(String, nullable=True)   # "minutes", "ounces", "Liters"
    measurement_target = Column(Float, nullable=True)  # 30, 64, etc

    #not used
    why_it_matters = Column(Text)
    success_definition = Column(Text)
    
    # Frequency 
    frequency_type = Column(String)
    frequency_value = Column(Integer)

    # Lifecycle
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String, default="active")

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    pod = relationship("Pod", back_populates="goals")
    participants = relationship("PodGoalParticipant", cascade="all, delete-orphan")
    # milestones = relationship("PodGoalMilestone", cascade="all, delete-orphan")
    streaks = relationship("GoalStreak", cascade="all, delete-orphan")
