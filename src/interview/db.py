"""Database session management for the interview module."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.interview.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncSession:
    """Yield an async database session."""
    async with async_session_factory() as session:
        yield session
