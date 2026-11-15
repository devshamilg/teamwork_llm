from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api import router as api_router
from auth import UserCreate, UserRead, auth_backend, fastapi_users
from views import router as views_router

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)

# Auth routes
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

# Template views & API routes
app.include_router(views_router)
app.include_router(api_router)
