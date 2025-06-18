"""
모니터링 관련 유틸리티 모듈
"""
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from prometheus_client import Counter, Histogram
import time

# 커스텀 메트릭 정의
REDIS_FAILURES = Counter(
    "redis_connection_failures_total",
    "Redis 연결 실패 횟수"
)

CELERY_TASK_FAILURES = Counter(
    "celery_task_failures_total",
    "Celery 태스크 실패 횟수"
)

SEARCH_REQUESTS = Counter(
    "search_requests_total",
    "검색 요청 횟수",
    ["search_type", "status"]
)

SEARCH_LATENCY = Histogram(
    "search_request_duration_seconds",
    "검색 요청 처리 시간 (초)",
    ["search_type"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
)

FALLBACK_ACTIVATIONS = Counter(
    "fallback_activations_total",
    "폴백 메커니즘 활성화 횟수",
    ["service", "reason"]
)

def setup_monitoring(app):
    """
    FastAPI 애플리케이션에 Prometheus 모니터링 설정
    """
    # 기본 메트릭 설정
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics"],
        env_var_name="ENABLE_METRICS",
    )

    # 추가 메트릭 설정
    instrumentator.add(
        metrics.request_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )
    
    instrumentator.add(
        metrics.response_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )
    
    instrumentator.add(
        metrics.latency(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )
    
    # 애플리케이션에 메트릭 엔드포인트 추가
    instrumentator.instrument(app).expose(app, include_in_schema=True)
    
    return instrumentator
