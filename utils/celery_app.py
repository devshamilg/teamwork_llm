import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6380/1")
backend_url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6380/2")

celery_app = Celery(
    "teamwork_llm",
    broker=broker_url,
    backend=backend_url,
    include=["utils.ai"],
)

