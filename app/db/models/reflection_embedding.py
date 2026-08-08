import uuid
from sqlalchemy import Float, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ReflectionEmbedding(Base):
    __tablename__ = "reflection_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    reflection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reflections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
    )
