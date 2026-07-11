# app/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import config

# Create async engine
engine = create_async_engine(
    config.DATABASE_URL,
    future=True,
    echo=False,
)

# Create async session factory
async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ⭐ FastAPI dependency for DB session
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
