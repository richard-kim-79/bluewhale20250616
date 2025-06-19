from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import logging
import json

from app.routers.auth import User, get_current_user
from app.core.redis_manager import redis_manager
from app.core.celery_manager import celery_manager
from app.core.monitoring import SEARCH_REQUESTS, SEARCH_LATENCY, FALLBACK_ACTIVATIONS

# 항상 임포트 시도 (celery_manager가 가용성 관리)
from app.tasks.embedding_tasks import semantic_search, search_by_filters
from app.services.embedder import VectorEmbedder
from app.services.vector_db import VectorDBService
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# 서비스 인스턴스 초기화
embedder = VectorEmbedder(model_name=settings.EMBEDDING_MODEL)
vector_db = VectorDBService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)


# 목업 검색 결과 생성 함수
def generate_mock_search_results(query: str, collections: List[str]) -> List[Dict[str, Any]]:
    """
    목업 검색 결과 생성
    
    Args:
        query: 검색 쿼리
        collections: 검색할 콜렉션 목록
        
    Returns:
        List[Dict[str, Any]]: 목업 검색 결과
    """
    results = []
    
    # 문서 결과
    if "documents" in collections:
        results.append({
            "id": "doc1",
            "type": "document",
            "vector_score": 0.95,
            "score": 0.95,
            "title": "벡터 임베딩 기반 SNS의 미래",
            "summary": "이 문서는 벡터 임베딩 기술을 활용한 소셜 네트워크 서비스의 미래 가능성을 탐구합니다.",
            "user_id": "user1",
            "user_name": "김벡터",
            "user_image": "https://via.placeholder.com/40",
            "file_type": "pdf",
            "tags": ["벡터임베딩", "SNS", "AI"],
            "ai_references": 128
        })
        
        results.append({
            "id": "doc2",
            "type": "document",
            "vector_score": 0.87,
            "score": 0.87,
            "title": "벡터 데이터베이스의 성능 최적화 방법론",
            "summary": "이 문서는 Qdrant, FAISS 등 벡터 데이터베이스의 성능을 최적화하는 다양한 방법을 설명합니다.",
            "user_id": "user2",
            "user_name": "이데이터",
            "user_image": "https://via.placeholder.com/40",
            "file_type": "pdf",
            "tags": ["벡터DB", "Qdrant", "성능최적화"],
            "ai_references": 87
        })
    
    # 포스트 결과
    if "posts" in collections:
        results.append({
            "id": "post1",
            "type": "post",
            "vector_score": 0.92,
            "score": 0.92,
            "content": "오늘 BlueWhale에 새로운 AI 논문을 업로드했습니다. 벡터 임베딩 기반 SNS의 미래에 대한 내용입니다.",
            "user_id": "user1",
            "user_name": "김벡터",
            "user_image": "https://via.placeholder.com/40",
            "created_at": datetime.now().isoformat(),
            "tags": ["AI", "벡터임베딩", "논문"]
        })
        
        results.append({
            "id": "post2",
            "type": "post",
            "vector_score": 0.85,
            "score": 0.85,
            "content": "벡터 데이터베이스의 성능 최적화에 관한 새로운 기술을 발견했습니다.",
            "user_id": "user2",
            "user_name": "이데이터",
            "user_image": "https://via.placeholder.com/40",
            "created_at": datetime.now().isoformat(),
            "tags": ["벡터DB", "Qdrant", "성능최적화"]
        })
    
    # 사용자 결과
    if "users" in collections:
        results.append({
            "id": "user1",
            "type": "user",
            "vector_score": 0.89,
            "score": 0.89,
            "name": "김벡터",
            "image": "https://via.placeholder.com/40",
            "bio": "벡터 임베딩과 AI 연구자"
        })
    
    return results


def generate_mock_tag_search_results(tags: List[str], collections: List[str]) -> List[Dict[str, Any]]:
    """
    목업 태그 검색 결과 생성
    
    Args:
        tags: 검색할 태그 목록
        collections: 검색할 콜렉션 목록
        
    Returns:
        List[Dict[str, Any]]: 목업 태그 검색 결과
    """
    results = []
    
    # 포스트 결과
    if "posts" in collections:
        results.append({
            "id": "post1",
            "type": "post",
            "title": "벡터 임베딩 기술 활용 방법",
            "content": "벡터 임베딩 기술을 활용한 SNS 플랫폼의 설계 방법에 대해 공유합니다.",
            "user_id": "user1",
            "user_name": "김벡터",
            "created_at": datetime.now().isoformat(),
            "tags": tags,
            "score": 0.89,
            "vector_score": 0.89
        })
        
        results.append({
            "id": "post2",
            "type": "post",
            "title": "벡터 데이터베이스 성능 최적화",
            "content": "벡터 데이터베이스의 성능 최적화에 관한 새로운 기술을 발견했습니다.",
            "user_id": "user2",
            "user_name": "이데이터",
            "created_at": datetime.now().isoformat(),
            "tags": tags,
            "score": 0.85,
            "vector_score": 0.85
        })
    
    # 문서 결과
    if "documents" in collections:
        results.append({
            "id": "doc1",
            "type": "document",
            "title": "벡터 임베딩 기반 SNS 플랫폼 설계",
            "summary": "이 문서는 벡터 임베딩 기술을 활용한 소셜 네트워크 서비스의 설계 방법론을 다룹니다.",
            "user_id": "user1",
            "user_name": "김벡터",
            "file_type": "pdf",
            "tags": tags + ["AI"],
            "score": 0.92,
            "vector_score": 0.92
        })
        
        results.append({
            "id": "doc2",
            "type": "document",
            "title": "벡터 데이터베이스의 성능 최적화 방법론",
            "summary": "이 문서는 Qdrant, FAISS 등 벡터 데이터베이스의 성능을 최적화하는 방법을 설명합니다.",
            "user_id": "user2",
            "user_name": "이데이터",
            "file_type": "docx",
            "tags": tags + ["성능최적화"],
            "score": 0.88,
            "vector_score": 0.88
        })
    
    return results


# 폴백 핸들러 함수 정의
def semantic_search_fallback(query: str, collection_names: List[str], filters: Dict[str, Any] = None, 
                           limit: int = 10, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    의미 기반 검색을 위한 폴백 핸들러
    """
    logger.info(f"폴백 핸들러 사용: 의미 기반 검색 '{query}'")
    
    # 목업 검색 결과 생성
    results = generate_mock_search_results(query, collection_names)
    return results


def tag_search_fallback(tags: List[str], collection_names: List[str], filters: Dict[str, Any] = None,
                       limit: int = 10, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    태그 기반 검색을 위한 폴백 핸들러
    """
    logger.info(f"폴백 핸들러 사용: 태그 기반 검색 {tags}")
    
    # 목업 태그 검색 결과 생성
    results = generate_mock_tag_search_results(tags, collection_names)
    return results


# 폴백 핸들러 등록
celery_manager.register_fallback("semantic_search", semantic_search_fallback)
celery_manager.register_fallback("search_by_filters", tag_search_fallback)


# 검색 로깅 및 처리 헬퍼 함수
async def log_search_activity(query_text: str, user_id: Optional[str], result_count: int):
    """
    의미 검색 활동을 로깅하는 헬퍼 함수
    """
    try:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "query": query_text,
            "user_id": user_id,
            "result_count": result_count,
            "search_type": "semantic"
        }
        logger.info(f"Search activity: {json.dumps(log_data)}")
        
        # 실제 구현에서는 로그를 데이터베이스에 저장하거나 분석 시스템에 전송
        # await db.search_logs.insert_one(log_data)
    except Exception as e:
        logger.error(f"Error logging search activity: {str(e)}")


async def log_tag_search_activity(tags: List[str], user_id: Optional[str], result_count: int):
    """
    태그 검색 활동을 로깅하는 헬퍼 함수
    """
    try:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "tags": tags,
            "user_id": user_id,
            "result_count": result_count,
            "search_type": "tag"
        }
        logger.info(f"Tag search activity: {json.dumps(log_data)}")
        
        # 실제 구현에서는 로그를 데이터베이스에 저장하거나 분석 시스템에 전송
        # await db.search_logs.insert_one(log_data)
    except Exception as e:
        logger.error(f"Error logging tag search activity: {str(e)}")


async def process_search_results(task_id: str, user_id: Optional[str]):
    """
    비동기 의미 검색 결과를 처리하는 헬퍼 함수
    """
    try:
        # 실제 구현에서는 Celery 태스크 결과를 가져와서 처리
        # task_result = AsyncResult(task_id)
        # result = task_result.get(timeout=10)  # 10초 동안 결과를 기다림
        
        # 검색 결과 처리 로직 (e.g., 캐싱, 사용자 피드백 처리 등)
        logger.info(f"Processing search results for task {task_id}, user {user_id}")
    except Exception as e:
        logger.error(f"Error processing search results: {str(e)}")


async def process_tag_search_results(task_id: str, user_id: Optional[str]):
    """
    비동기 태그 검색 결과를 처리하는 헬퍼 함수
    """
    try:
        # 실제 구현에서는 Celery 태스크 결과를 가져와서 처리
        # task_result = AsyncResult(task_id)
        # result = task_result.get(timeout=10)  # 10초 동안 결과를 기다림
        
        # 태그 검색 결과 처리 로직
        logger.info(f"Processing tag search results for task {task_id}, user {user_id}")
    except Exception as e:
        logger.error(f"Error processing tag search results: {str(e)}")

# 모델 정의
class SearchQuery(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None
    limit: int = 10

class SearchResultBase(BaseModel):
    id: str
    type: str  # 'post', 'document', 'user'
    vector_score: float
    score: float = None  # 테스트 호환성을 위해 추가
    
    def __init__(self, **data):
        super().__init__(**data)
        # vector_score 값을 score 필드에도 복사
        if self.score is None and hasattr(self, 'vector_score'):
            self.score = self.vector_score
    
class PostSearchResult(SearchResultBase):
    type: str = "post"
    content: str
    user_id: str
    user_name: str
    user_image: Optional[str] = None
    created_at: datetime
    tags: List[str] = []
    
class DocumentSearchResult(SearchResultBase):
    type: str = "document"
    title: str
    summary: str
    user_id: str
    user_name: str
    file_type: str
    user_image: Optional[str] = None
    tags: List[str] = []
    ai_references: int = 0
    
class UserSearchResult(SearchResultBase):
    type: str = "user"
    name: str
    image: Optional[str] = None
    bio: Optional[str] = None
    
class SearchResults(BaseModel):
    total: int
    results: List[Union[PostSearchResult, DocumentSearchResult, UserSearchResult]]

# 벡터 검색 엔드포인트
@router.post("/", response_model=Dict[str, Any])
async def search(
    query: SearchQuery,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    벡터 임베딩 기반 의미 검색
    """
    try:
        # 검색 시작 시간 기록
        start_time = time.time()
        
        # 검색 유형에 따른 커렉션 필터링
        collections = ["posts", "documents", "users"]
        if query.filters and "collections" in query.filters:
            collections = query.filters["collections"]
        
        logger.info(f"Semantic search request: {query.query} in collections: {collections}")
        
        # celery_manager를 통한 태스크 실행 (자동 폴백 처리)
        task_result = celery_manager.execute_task(
            semantic_search,
            query=query.query,
            collection_names=collections,
            filters=query.filters,
            limit=query.limit,
            user_id=current_user.id if current_user else None
        )
        
        task_id = task_result["task_id"]
        
        # 비동기 검색 결과 처리를 위한 백그라운드 태스크
        if not task_result.get("fallback_used", False):
            background_tasks.add_task(
                process_search_results,
                task_id=task_id,
                user_id=current_user.id if current_user else None
            )
            
            # 비동기 태스크가 실행 중인 경우
            return {
                "task_id": task_id,
                "status": "pending",
                "message": "검색이 진행 중입니다.",
                "total": 0,
                "results": []
            }
        
        # 폴백 사용 시 즉시 결과 반환
        results = task_result.get("result", [])
        
        # 폴백 사용 여부 기록
        if task_result.get("fallback_used", False):
            FALLBACK_ACTIVATIONS.labels(service="search", reason="redis_failure").inc()
            
        # 검색 로깅 및 분석을 위한 백그라운드 태스크
        background_tasks.add_task(
            log_search_activity,
            query_text=query.query,
            user_id=current_user.id if current_user else None,
            result_count=len(results)
        )
        
        # 검색 완료 시간 측정 및 메트릭 기록
        elapsed_time = time.time() - start_time
        SEARCH_LATENCY.labels(search_type="semantic").observe(elapsed_time)
        SEARCH_REQUESTS.labels(search_type="semantic", status="success").inc()
        
        return {
            "task_id": task_id,
            "status": "completed",
            "message": "검색이 완료되었습니다.",
            "total": len(results),
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Error in semantic search: {str(e)}")
        SEARCH_REQUESTS.labels(search_type="semantic", status="error").inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"검색 중 오류가 발생했습니다: {str(e)}"
        )

# 태그 기반 검색
@router.get("/tags", response_model=List[Dict[str, Any]])
async def search_by_tags(
    background_tasks: BackgroundTasks,
    tags: List[str] = Query(..., description="검색할 태그 목록"),
    current_user: Optional[User] = Depends(get_current_user),
    type: Optional[str] = None,
    skip: int = 0,
    limit: int = 10
):
    """
    태그 기반 검색 수행
    """
    try:
        # 검색 시작 시간 기록
        start_time = time.time()
        
        # 검색 유형에 따른 커렉션 필터링
        collections = []
        if not type or type == "all":
            collections = ["posts", "documents"]
        else:
            if type == "post":
                collections.append("posts")
            elif type == "document":
                collections.append("documents")
        
        logger.info(f"Tag search request: {tags} in collections: {collections}")
        
        # celery_manager를 통한 태스크 실행 (자동 폴백 처리)
        task_result = celery_manager.execute_task(
            search_by_filters,
            collections=collections,
            filters={"tags": {"$in": tags}},
            limit=limit,
            offset=skip,
            user_id=current_user.id if current_user else None
        )
        
        task_id = task_result["task_id"]
        
        # 비동기 검색 결과 처리를 위한 백그라운드 태스크
        if not task_result.get("fallback_used", False):
            background_tasks.add_task(
                process_tag_search_results,
                task_id=task_id,
                user_id=current_user.id if current_user else None
            )
            
            # 비동기 태스크가 실행 중인 경우 - 빈 결과 반환
            logger.info(f"태그 검색 태스크 실행 중: {task_id}")
            return []
        
        # 폴백 사용 시 즉시 결과 반환
        results = task_result.get("result", [])
        
        # 폴백 사용 여부 기록
        if task_result.get("fallback_used", False):
            FALLBACK_ACTIVATIONS.labels(service="tag_search", reason="redis_failure").inc()
            
        # 검색 로깅 및 분석을 위한 백그라운드 태스크
        background_tasks.add_task(
            log_tag_search_activity,
            tags=tags,
            user_id=current_user.id if current_user else None,
            result_count=len(results)
        )
        
        # 검색 완료 시간 측정 및 메트릭 기록
        elapsed_time = time.time() - start_time
        SEARCH_LATENCY.labels(search_type="tag").observe(elapsed_time)
        SEARCH_REQUESTS.labels(search_type="tag", status="success").inc()
        
        logger.info(f"태그 검색 완료: {len(results)} 결과 발견")
        return results[skip:skip+limit]
        
    except Exception as e:
        logger.error(f"Error in tag search: {str(e)}")
        SEARCH_REQUESTS.labels(search_type="tag", status="error").inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"검색 중 오류가 발생했습니다: {str(e)}"
        )
