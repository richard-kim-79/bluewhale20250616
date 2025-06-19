"""
Celery 연결 관리 및 상태 모니터링을 위한 모듈
"""
import logging
import time
import uuid
from typing import Optional, Dict, Any, Callable, List
from functools import wraps
from celery.result import AsyncResult
from app.core.monitoring import CELERY_TASK_FAILURES, FALLBACK_ACTIVATIONS
from app.core.redis_manager import redis_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

class CeleryManager:
    """Celery 태스크 관리 및 상태 모니터링 클래스"""
    
    def __init__(self):
        """Celery 매니저 초기화"""
        self._is_available = False
        self._last_error: Optional[Exception] = None
        self._task_stats: Dict[str, int] = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "fallback_used": 0
        }
        self._fallback_handlers: Dict[str, Callable] = {}
        
        # Celery 앱 가용성 확인
        self._check_availability()
    
    def _check_availability(self) -> bool:
        """
        Celery 가용성 확인
        
        Returns:
            bool: Celery 사용 가능 여부
        """
        try:
            # Redis 연결 확인
            if not redis_manager.is_connected and not redis_manager.connect():
                logger.warning("Redis 연결 실패로 Celery를 사용할 수 없습니다")
                self._is_available = False
                return False
            
            # Celery 앱 임포트
            from app.tasks.celery_app import celery_app
            
            # Celery 앱 상태 확인
            celery_app.control.inspect().stats()
            
            self._is_available = True
            logger.info("Celery 사용 가능 상태 확인됨")
            return True
            
        except ImportError as e:
            logger.error(f"Celery 앱 임포트 실패: {str(e)}")
            self._last_error = e
            self._is_available = False
        except Exception as e:
            logger.error(f"Celery 가용성 확인 중 오류: {str(e)}")
            self._last_error = e
            self._is_available = False
        
        return False
    
    @property
    def is_available(self) -> bool:
        """Celery 사용 가능 여부 반환"""
        # 주기적으로 상태 재확인
        if not self._is_available and (time.time() % 60) < 1:  # 약 1분마다 재시도
            self._check_availability()
        return self._is_available
    
    @property
    def task_stats(self) -> Dict[str, int]:
        """태스크 통계 반환"""
        return self._task_stats
    
    def register_fallback(self, task_name: str, fallback_handler: Callable) -> None:
        """
        특정 태스크에 대한 폴백 핸들러 등록
        
        Args:
            task_name: 태스크 이름
            fallback_handler: 폴백 처리 함수
        """
        self._fallback_handlers[task_name] = fallback_handler
        logger.info(f"'{task_name}' 태스크에 대한 폴백 핸들러 등록됨")
    
    def execute_task(self, task_name: str, *args, **kwargs) -> Dict[str, Any]:
        """
        Celery 태스크를 실행하고 결과를 반환합니다.
        Redis 연결 실패 시 폴백 핸들러를 사용합니다.
        """
        try:
            # 태스크 실행 시도
            task = self.celery_app.send_task(task_name, args=args, kwargs=kwargs)
            task_id = task.id
            
            # 태스크 결과 확인
            result = task.get(timeout=self.task_timeout)
            
            return {
                "task_id": task_id,
                "result": result,
                "fallback_used": False
            }
        except Exception as e:
            self.logger.error(f"Celery task execution failed: {str(e)}")
            
            # Prometheus 메트릭 증가
            CELERY_TASK_FAILURES.inc()
            
            # 태스크 이름에 따른 폴백 핸들러 호출
            if task_name in self._fallback_handlers:
                self.logger.info(f"Using fallback handler for {task_name}")
                fallback_result = self._fallback_handlers[task_name](*args, **kwargs)
                
                # 폴백 활성화 메트릭 증가
                FALLBACK_ACTIVATIONS.labels(service="celery", reason="task_failure").inc()
                
                # 폴백 결과에 모의 태스크 ID 추가
                mock_task_id = f"mock_{uuid.uuid4()}"
                
                return {
                    "task_id": mock_task_id,
                    "result": fallback_result,
                    "fallback_used": True
                }
            else:
                # 폴백 핸들러가 없는 경우 예외 전파
                raise
        return {
            "task_id": f"error-{task_name}-{int(time.time())}",
            "status": "error",
            "fallback_used": True,
            "error": str(self._last_error) if self._last_error else "Unknown error"
        }
    
    def get_task_result(self, task_id: str, timeout: int = 1) -> Dict[str, Any]:
        """
        태스크 결과 조회
        
        Args:
            task_id: 태스크 ID
            timeout: 결과 대기 시간(초)
            
        Returns:
            Dict[str, Any]: 태스크 결과 정보
        """
        # 목업 태스크 ID 처리
        if task_id.startswith(("mock-", "error-")):
            return {
                "task_id": task_id,
                "status": "mock_completed" if task_id.startswith("mock-") else "mock_error",
                "fallback_used": True
            }
        
        if not self.is_available:
            return {
                "task_id": task_id,
                "status": "unavailable",
                "error": "Celery is not available"
            }
        
        try:
            # 실제 태스크 결과 조회
            result = AsyncResult(task_id)
            
            if timeout > 0:
                try:
                    # 지정된 시간 동안 결과 대기
                    task_result = result.get(timeout=timeout, propagate=False)
                    
                    if result.successful():
                        self._task_stats["successful_tasks"] += 1
                        return {
                            "task_id": task_id,
                            "status": "completed",
                            "result": task_result
                        }
                    elif result.failed():
                        self._task_stats["failed_tasks"] += 1
                        return {
                            "task_id": task_id,
                            "status": "failed",
                            "error": str(result.result) if result.result else "Unknown error"
                        }
                except Exception as e:
                    # 타임아웃 또는 기타 오류
                    pass
            
            # 현재 상태 반환
            return {
                "task_id": task_id,
                "status": result.status,
                "ready": result.ready()
            }
            
        except Exception as e:
            logger.error(f"태스크 결과 조회 중 오류 (태스크 ID: {task_id}): {str(e)}")
            return {
                "task_id": task_id,
                "status": "error",
                "error": str(e)
            }
    
    def check_health(self) -> Dict[str, Any]:
        """
        Celery 상태 확인
        
        Returns:
            Dict[str, Any]: 상태 정보
        """
        health_info = {
            "is_available": self.is_available,
            "redis_status": redis_manager.check_health()["status"],
            "task_stats": self._task_stats
        }
        
        if self.is_available:
            try:
                from app.tasks.celery_app import celery_app
                
                # 워커 상태 확인
                i = celery_app.control.inspect()
                active_workers = i.active()
                
                if active_workers:
                    health_info["status"] = "healthy"
                    health_info["active_workers"] = len(active_workers)
                else:
                    health_info["status"] = "degraded"
                    health_info["error"] = "No active workers found"
            except Exception as e:
                health_info["status"] = "degraded"
                health_info["error"] = str(e)
        else:
            health_info["status"] = "unavailable"
            if self._last_error:
                health_info["error"] = str(self._last_error)
        
        return health_info

# 싱글톤 인스턴스
celery_manager = CeleryManager()
