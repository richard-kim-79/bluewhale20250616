from celery import Celery
from app.core.config import settings

# Celery 앱 초기화
celery_app = Celery(
    "bluewhale",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
)

# 작업 자동 로드 설정
celery_app.autodiscover_tasks(["app.tasks"])

# 작업 라우팅 설정
celery_app.conf.task_routes = {
    "app.tasks.document_tasks.*": {"queue": "documents"},
    "app.tasks.embedding_tasks.*": {"queue": "embeddings"},
    "app.tasks.notification_tasks.*": {"queue": "notifications"}
}

# 기타 Celery 설정
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True
)
