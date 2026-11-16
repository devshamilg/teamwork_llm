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

# Detect test execution environment
IS_TESTING = bool(
    os.getenv("TESTING")
    or os.getenv("MODE", "").upper() == "TEST"
    or os.getenv("ENVIRONMENT", "").lower() == "test"
    or "pytest" in sys.modules
    or os.getenv("PYTEST_CURRENT_TEST")
)

# Test database configuration (chat_app_test)
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "chat_app_test")
TEST_DATABASE_URL_ENV = os.getenv("TEST_DATABASE_URL")
if TEST_DATABASE_URL_ENV:
    TEST_DATABASE_URL = TEST_DATABASE_URL_ENV
else:
    TEST_DATABASE_URL = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=TEST_DB_NAME,
    )

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_async_session_maker = async_sessionmaker(
    test_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# Default / production database configuration
DATABASE_URL_ENV = os.getenv("DATABASE_URL")
if IS_TESTING:
    DATABASE_URL = TEST_DATABASE_URL
    engine = test_engine
    async_session_maker = test_async_session_maker
elif DATABASE_URL_ENV:
    DATABASE_URL = DATABASE_URL_ENV
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
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


async def get_test_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session for the test database."""
    async with test_async_session_maker() as session:
        yield session


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
    "TEST_DATABASE_URL",
    "engine",
    "test_engine",
    "async_session_maker",
    "test_async_session_maker",
    "get_async_session",
    "get_test_async_session",
    "get_user_db",
    "Base",
    "User",
]
