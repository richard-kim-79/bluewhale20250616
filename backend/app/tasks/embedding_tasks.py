import logging
from typing import Dict, Any, Optional, List, Union
import numpy as np
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.services.embedder import VectorEmbedder
from app.services.vector_db import VectorDBService

logger = logging.getLogger(__name__)

# 서비스 인스턴스 초기화
embedder = VectorEmbedder(model_name=settings.EMBEDDING_MODEL)
vector_db = VectorDBService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

@celery_app.task(name="app.tasks.embedding_tasks.embed_post")
def embed_post(post_id: str, post_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    포스트 임베딩 생성 및 저장 작업
    
    Args:
        post_id: 포스트 ID
        post_data: 포스트 데이터
        
    Returns:
        처리 결과
    """
    try:
        logger.info(f"포스트 임베딩 작업 시작: {post_id}")
        
        # 포스트 데이터에서 텍스트 추출
        content = post_data.get("content", "")
        tags = post_data.get("tags", [])
        
        # 텍스트가 비어있으면 오류
        if not content:
            raise ValueError(f"포스트 내용이 비어있음: {post_id}")
        
        # 임베딩 생성
        embedding = embedder.embed_text(content)
        
        # 벡터 데이터베이스에 저장
        vector_payload = {
            "post_id": post_id,
            "content": content,
            "tags": tags,
            "user_id": post_data.get("user_id", ""),
            "created_at": post_data.get("created_at", datetime.now().isoformat()),
            "type": "post"
        }
        
        vector_db.upsert_vector(
            collection_name="posts",
            vector=embedding,
            payload=vector_payload,
            vector_id=post_id
        )
        
        logger.info(f"포스트 임베딩 작업 완료: {post_id}")
        
        return {
            "post_id": post_id,
            "status": "success",
            "vector_id": post_id
        }
    
    except Exception as e:
        logger.error(f"포스트 임베딩 작업 중 오류 발생: {str(e)}")
        
        return {
            "post_id": post_id,
            "status": "error",
            "error": str(e)
        }

@celery_app.task(name="app.tasks.embedding_tasks.embed_user_profile")
def embed_user_profile(user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 프로필 임베딩 생성 및 저장 작업
    
    Args:
        user_id: 사용자 ID
        user_data: 사용자 프로필 데이터
        
    Returns:
        처리 결과
    """
    try:
        logger.info(f"사용자 프로필 임베딩 작업 시작: {user_id}")
        
        # 임베딩 생성
        embedding = embedder.embed_user_profile(user_data)
        
        # 벡터 데이터베이스에 저장
        vector_payload = {
            "user_id": user_id,
            "name": user_data.get("name", ""),
            "bio": user_data.get("bio", ""),
            "interests": user_data.get("interests", []),
            "updated_at": datetime.now().isoformat(),
            "type": "user"
        }
        
        vector_db.upsert_vector(
            collection_name="users",
            vector=embedding,
            payload=vector_payload,
            vector_id=user_id
        )
        
        logger.info(f"사용자 프로필 임베딩 작업 완료: {user_id}")
        
        return {
            "user_id": user_id,
            "status": "success",
            "vector_id": user_id
        }
    
    except Exception as e:
        logger.error(f"사용자 프로필 임베딩 작업 중 오류 발생: {str(e)}")
        
        return {
            "user_id": user_id,
            "status": "error",
            "error": str(e)
        }

@celery_app.task(name="app.tasks.embedding_tasks.find_similar_users")
def find_similar_users(user_id: str, limit: int = 10) -> Dict[str, Any]:
    """
    유사한 사용자 찾기 작업
    
    Args:
        user_id: 사용자 ID
        limit: 찾을 사용자 수
        
    Returns:
        유사한 사용자 목록
    """
    try:
        logger.info(f"유사 사용자 검색 작업 시작: {user_id}")
        
        # 사용자 벡터 조회
        user_vector = vector_db.search_vectors(
            collection_name="users",
            query_vector=np.zeros(embedder.get_vector_dimension()),  # 실제로는 사용자 ID로 벡터 조회
            filters={"user_id": user_id},
            limit=1
        )
        
        if not user_vector:
            raise ValueError(f"사용자 벡터를 찾을 수 없음: {user_id}")
        
        # 유사한 사용자 검색
        similar_users = vector_db.search_vectors(
            collection_name="users",
            query_vector=np.array(user_vector[0].get("vector", [])),
            limit=limit + 1,  # 자기 자신 제외
            filters={"type": "user"}
        )
        
        # 자기 자신 제외
        similar_users = [user for user in similar_users if user.get("user_id") != user_id]
        
        logger.info(f"유사 사용자 검색 작업 완료: {user_id} (결과: {len(similar_users)}개)")
        
        return {
            "user_id": user_id,
            "status": "success",
            "similar_users": similar_users[:limit]
        }
    
    except Exception as e:
        logger.error(f"유사 사용자 검색 작업 중 오류 발생: {str(e)}")
        
        return {
            "user_id": user_id,
            "status": "error",
            "error": str(e)
        }

@celery_app.task(name="app.tasks.embedding_tasks.semantic_search")
def semantic_search(
    query: str,
    collection_names: List[str] = ["documents", "posts", "users"],
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    의미 기반 검색 작업
    
    Args:
        query: 검색 쿼리
        collection_names: 검색할 컬렉션 목록
        filters: 검색 필터
        limit: 반환할 결과 수
        user_id: 검색 요청한 사용자 ID (선택적)
        
    Returns:
        검색 결과
    """
    try:
        logger.info(f"의미 검색 작업 시작: '{query}' (사용자: {user_id})")
        
        # 쿼리 임베딩 생성
        query_embedding = embedder.embed_text(query)
        
        # 각 컬렉션에서 검색
        results = {}
        for collection_name in collection_names:
            collection_results = vector_db.search_vectors(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit,
                filters=filters
            )
            results[collection_name] = collection_results
        
        # 모든 결과 결합 및 점수 기준 정렬
        all_results = []
        for collection_name, collection_results in results.items():
            for item in collection_results:
                item["collection"] = collection_name
                all_results.append(item)
        
        all_results.sort(key=lambda x: x.get("vector_score", 0), reverse=True)
        
        logger.info(f"의미 검색 작업 완료: '{query}' (결과: {len(all_results)}개)")
        
        return {
            "query": query,
            "status": "success",
            "results": all_results[:limit],
            "user_id": user_id
        }
    
    except Exception as e:
        logger.error(f"의미 검색 작업 중 오류 발생: {str(e)}")
        
        return {
            "query": query,
            "status": "error",
            "error": str(e),
            "user_id": user_id
        }


@celery_app.task(name="app.tasks.embedding_tasks.search_by_filters")
def search_by_filters(
    collections: List[str],
    filters: Dict[str, Any],
    limit: int = 10,
    offset: int = 0,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    필터 기반 검색 작업 (태그 검색 등)
    
    Args:
        collections: 검색할 컬렉션 목록
        filters: 검색 필터 (예: {"tags": {"$in": ["AI", "벡터DB"]}})
        limit: 반환할 결과 수
        offset: 결과 오프셋 (페이지네이션)
        user_id: 검색 요청한 사용자 ID (선택적)
        
    Returns:
        검색 결과
    """
    try:
        logger.info(f"필터 검색 작업 시작: 컬렉션={collections}, 필터={filters} (사용자: {user_id})")
        
        # 각 컬렉션에서 검색
        results = {}
        for collection_name in collections:
            collection_results = vector_db.filter_vectors(
                collection_name=collection_name,
                filters=filters,
                limit=limit,
                offset=offset
            )
            results[collection_name] = collection_results
        
        # 모든 결과 결합
        all_results = []
        for collection_name, collection_results in results.items():
            for item in collection_results:
                item["collection"] = collection_name
                all_results.append(item)
        
        # 결과 정렬 (최신순)
        all_results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        logger.info(f"필터 검색 작업 완료: 컬렉션={collections} (결과: {len(all_results)}개)")
        
        return {
            "filters": filters,
            "status": "success",
            "results": all_results[offset:offset+limit],
            "total": len(all_results),
            "user_id": user_id
        }
    
    except Exception as e:
        logger.error(f"필터 검색 작업 중 오류 발생: {str(e)}")
        
        return {
            "filters": filters,
            "status": "error",
            "error": str(e),
            "user_id": user_id
        }
