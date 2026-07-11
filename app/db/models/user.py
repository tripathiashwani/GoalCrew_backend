import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, DateTime
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    firebase_uid: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    username = mapped_column(
        String(45),
        unique=True,
        index=True,
        nullable=True,
    )
    country_code = mapped_column(String(5), nullable=True)  
    phone_number = mapped_column(String(20), nullable=True)

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role = mapped_column(String(20), nullable=True, default='user')
    is_verified = mapped_column(Boolean, default=False)
    is_phone_verified = mapped_column(Boolean, default=False)
    otp_code = mapped_column(String(6), nullable=True)
    is_onboarded = mapped_column(Boolean, default=False)
    verification_token = mapped_column(String, nullable=True)
    reset_token = mapped_column(String, nullable=True)
    profile_photo_url = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    pods_created = relationship("Pod", back_populates="creator")
    preferences = relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
