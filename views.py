from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

router = APIRouter(tags=["views"])


@router.get("/")
async def landing_page():
    return FileResponse(TEMPLATES_DIR / "index.html")


@router.get("/login")
async def login_page():
    return FileResponse(TEMPLATES_DIR / "login.html")


@router.get("/register")
async def register_page():
    return FileResponse(TEMPLATES_DIR / "register.html")


@router.get("/home")
async def home_page():
    return FileResponse(TEMPLATES_DIR / "home.html")
