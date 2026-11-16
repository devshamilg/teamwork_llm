from celery import Celery

celery_app = Celery(
    "teamwork_llm",
    broker="redis://localhost:6380/1",
    backend="redis://localhost:6380/2",
    include=["utils.ai"],
)

