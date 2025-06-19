"""
Redis 연결 관리 및 상태 모니터링을 위한 모듈
"""
import logging
import time
import redis
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.monitoring import REDIS_FAILURES, FALLBACK_ACTIVATIONS

logger = logging.getLogger(__name__)

class RedisManager:
    """Redis 연결 관리 및 상태 모니터링 클래스"""
    
    def __init__(self, host: str = settings.REDIS_HOST, 
                 port: int = settings.REDIS_PORT,
                 max_retries: int = 3,
                 retry_interval: int = 5):
        """
        Redis 매니저 초기화
        
        Args:
            host: Redis 호스트
            port: Redis 포트
            max_retries: 최대 재시도 횟수
            retry_interval: 재시도 간격(초)
        """
        self.host = host
        self.port = port
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self._client: Optional[redis.Redis] = None
        self._is_connected = False
        self._last_error: Optional[Exception] = None
        self._connection_stats: Dict[str, Any] = {
            "attempts": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "last_connected_at": None,
            "last_error_at": None,
        }
        self._health_stats: Dict[str, Any] = {
            "failed_operations": 0,
        }
    
    @property
    def client(self) -> Optional[redis.Redis]:
        """Redis 클라이언트 인스턴스 반환, 연결되지 않은 경우 연결 시도"""
        if not self._client or not self._is_connected:
            self.connect()
        return self._client
    
    @property
    def is_connected(self) -> bool:
        """현재 Redis 연결 상태 반환"""
        return self._is_connected
    
    @property
    def connection_stats(self) -> Dict[str, Any]:
        """Redis 연결 통계 반환"""
        return self._connection_stats
    
    @property
    def health_stats(self) -> Dict[str, Any]:
        """Redis 상태 통계 반환"""
        return self._health_stats
    
    @property
    def last_error(self) -> Optional[Exception]:
        """마지막 발생한 오류 반환"""
        return self._last_error
    
    def connect(self) -> bool:
        """
        Redis에 연결 시도, 실패 시 재시도
        
        Returns:
            bool: 연결 성공 여부
        """
        self._connection_stats["attempts"] += 1
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Redis 연결 시도 중... (시도 {attempt + 1}/{self.max_retries})")
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    decode_responses=True
                )
                
                # 연결 테스트
                self._client.ping()
                
                self._is_connected = True
                self._connection_stats["successful_connections"] += 1
                self._connection_stats["last_connected_at"] = time.time()
                logger.info(f"Redis 연결 성공: {self.host}:{self.port}")
                return True
                
            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.warning(f"Redis 연결 실패 (시도 {attempt + 1}/{self.max_retries}): {str(e)}")
                self._last_error = e
                self._connection_stats["last_error_at"] = time.time()
                
                if attempt < self.max_retries - 1:
                    logger.info(f"{self.retry_interval}초 후 재시도...")
                    time.sleep(self.retry_interval)
            except Exception as e:
                logger.error(f"Redis 연결 중 예상치 못한 오류: {str(e)}")
                self._last_error = e
                self._connection_stats["last_error_at"] = time.time()
                break
        
        self._is_connected = False
        self._connection_stats["failed_connections"] += 1
        logger.error(f"Redis 연결 실패: 최대 재시도 횟수({self.max_retries}) 초과")
        
        # Prometheus 메트릭 업데이트
        REDIS_FAILURES.inc()
        
        return False
    
    def disconnect(self) -> None:
        """Redis 연결 종료"""
        if self._client:
            try:
                self._client.close()
                logger.info("Redis 연결 종료")
            except Exception as e:
                logger.error(f"Redis 연결 종료 중 오류: {str(e)}")
            finally:
                self._client = None
                self._is_connected = False
    
    def check_health(self) -> Dict[str, Any]:
        """
        Redis 연결 상태 확인
        
        Returns:
            Dict[str, Any]: 상태 정보
        """
        health_info = {
            "is_connected": self._is_connected,
            "host": self.host,
            "port": self.port,
            **self._connection_stats
        }
        
        if self._is_connected:
            try:
                # 추가 상태 정보 수집
                start_time = time.time()
                self._client.ping()
                latency = time.time() - start_time
                health_info["latency_ms"] = round(latency * 1000, 2)
                health_info["status"] = "healthy"
            except Exception as e:
                health_info["status"] = "degraded"
                health_info["error"] = str(e)
                self._is_connected = False
        else:
            health_info["status"] = "disconnected"
            if self._last_error:
                health_info["error"] = str(self._last_error)
        
        return health_info

# 싱글톤 인스턴스
redis_manager = RedisManager()
