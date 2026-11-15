import os
import secrets
import sys
import uuid
import warnings
from types import ModuleType
from typing import Optional, Tuple

warnings.filterwarnings("ignore", message="Valid config keys have changed in V2.*")
warnings.filterwarnings("ignore", message=".*inherit from .BaseModel. before generic classes.*")

# Fallback for passlib's legacy import of pkg_resources in Python 3.12+
try:
    import pkg_resources
except ImportError:
    sys.modules["pkg_resources"] = ModuleType("pkg_resources")

import bcrypt
from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, schemas
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.password import PasswordHelperProtocol
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from pydantic import ConfigDict

from database.engine import get_user_db
from database.tables import User

SECRET = os.getenv("SECRET_KEY", "SECRET")


class BcryptPasswordHelper(PasswordHelperProtocol):
    def verify_and_update(
        self, plain_password: str, hashed_password: str
    ) -> Tuple[bool, str]:
        verified = bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
        return verified, None  # type: ignore[return-value]

    def hash(self, password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8")[:72],
            bcrypt.gensalt(),
        ).decode("utf-8")

    def generate(self) -> str:
        return secrets.token_urlsafe(16)


password_helper = BcryptPasswordHelper()


class UserRead(schemas.BaseUser[uuid.UUID]):
    id: uuid.UUID
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(schemas.BaseUserCreate):
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
):
    yield UserManager(user_db, password_helper)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)
