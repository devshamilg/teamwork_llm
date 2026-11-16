import os
import sys
from types import ModuleType
from typing import AsyncGenerator

# Fallback for passlib's legacy import of pkg_resources in Python 3.12+
try:
    import pkg_resources
except ImportError:
    sys.modules["pkg_resources"] = ModuleType("pkg_resources")

from dotenv import load_dotenv
from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.tables import Base, User

load_dotenv()

DATABASE_URL_ENV = os.getenv("DATABASE_URL")
if DATABASE_URL_ENV:
    DATABASE_URL = DATABASE_URL_ENV
else:
    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME"),
    )

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with async_session_maker() as session:
        yield session


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    """Dependency that yields a FastAPI Users SQLAlchemy database adapter."""
    yield SQLAlchemyUserDatabase(session, User)


__all__ = [
    "DATABASE_URL",
    "engine",
    "async_session_maker",
    "get_async_session",
    "get_user_db",
    "Base",
    "User",
]
