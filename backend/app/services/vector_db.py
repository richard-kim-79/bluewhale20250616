from qdrant_client import QdrantClient
from qdrant_client.http import models
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import uuid

logger = logging.getLogger(__name__)

class VectorDBService:
    """
    Qdrant 벡터 데이터베이스 연결 및 관리 서비스
    문서, 포스트, 사용자 프로필 등의 벡터 임베딩을 저장하고 검색
    """
    
    def __init__(self, host: str = "localhost", port: int = 6333, url: str = None, api_key: str = None, https: bool = False):
        """
        Qdrant 클라이언트 초기화
        
        Args:
            host: Qdrant 서버 호스트 (로컬 또는 클라우드)
            port: Qdrant 서버 포트
            url: Qdrant 클라우드 URL (설정 시 host와 port 대신 사용)
            api_key: Qdrant 클라우드 API 키
            https: HTTPS 사용 여부
        """
        try:
            # URL이 제공된 경우 (클라우드 모드)
            if url:
                # URL에서 호스트와 포트 추출
                if '://' in url:
                    protocol, address = url.split('://')
                    https = protocol.lower() == 'https'
                else:
                    address = url
                
                if ':' in address:
                    host, port_str = address.split(':')
                    port = int(port_str)
                else:
                    host = address
                    # HTTPS의 경우 기본 포트 443, HTTP의 경우 기본 포트 80
                    port = 443 if https else 80
            
            # API 키가 제공된 경우 (클라우드 모드)
            if api_key:
                self.client = QdrantClient(host=host, port=port, api_key=api_key, https=https)
                logger.info(f"Qdrant 클라우드 클라이언트 초기화 완료 ({'https' if https else 'http'}://{host}:{port})")
            else:
                # 로컬 모드
                self.client = QdrantClient(host=host, port=port, https=https)
                logger.info(f"Qdrant 클라이언트 초기화 완료 ({'https' if https else 'http'}://{host}:{port})")
        except Exception as e:
            logger.error(f"Qdrant 클라이언트 초기화 중 오류 발생: {str(e)}")
            raise
    
    def create_collection(self, collection_name: str, vector_size: int) -> bool:
        """
        벡터 컬렉션 생성
        
        Args:
            collection_name: 컬렉션 이름
            vector_size: 벡터 차원 크기
            
        Returns:
            성공 여부
        """
        try:
            # 컬렉션이 이미 존재하는지 확인
            collections = self.client.get_collections().collections
            if any(collection.name == collection_name for collection in collections):
                logger.info(f"컬렉션 '{collection_name}'이(가) 이미 존재함")
                return True
            
            # 새 컬렉션 생성
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )
            
            # 필터링을 위한 페이로드 인덱스 생성
            # 컬렉션 생성 후 별도로 인덱스 추가
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="type",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="test",
                field_schema=models.PayloadSchemaType.BOOL
            )
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="tags",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="title",
                field_schema=models.PayloadSchemaType.TEXT
            )
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="content",
                field_schema=models.PayloadSchemaType.TEXT
            )
            logger.info(f"컬렉션 '{collection_name}' 생성 완료 (벡터 크기: {vector_size}, 페이로드 인덱스 추가)")
            return True
        except Exception as e:
            logger.error(f"컬렉션 생성 중 오류 발생: {str(e)}")
            return False
    
    def upsert_vector(
        self, 
        collection_name: str, 
        vector: np.ndarray, 
        payload: Dict[str, Any],
        vector_id: Optional[str] = None
    ) -> str:
        """
        벡터 및 메타데이터 삽입 또는 업데이트
        
        Args:
            collection_name: 컬렉션 이름
            vector: 벡터 데이터
            payload: 메타데이터
            vector_id: 벡터 ID (없으면 새로 생성)
            
        Returns:
            벡터 ID
        """
        try:
            # ID가 없으면 새로 생성
            if vector_id is None:
                vector_id = str(uuid.uuid4())
            
            # 벡터가 None이면 오류 발생
            if vector is None:
                raise ValueError("Vector cannot be None")
                
            # 벡터 삽입 또는 업데이트
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=vector_id,
                        vector=vector.tolist(),
                        payload=payload
                    )
                ]
            )
            logger.debug(f"벡터 업서트 완료: {collection_name}/{vector_id}")
            return vector_id
        except Exception as e:
            logger.error(f"벡터 업서트 중 오류 발생: {str(e)}")
            raise
    
    def search_vectors(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        벡터 유사도 검색
        
        Args:
            collection_name: 컬렉션 이름
            query_vector: 쿼리 벡터
            limit: 반환할 결과 수
            filters: 필터링 조건
            
        Returns:
            검색 결과 목록
        """
        try:
            # 쿼리 벡터가 None이면 오류 발생
            if query_vector is None:
                raise ValueError("Query vector cannot be None")
                
            # 필터 조건 구성
            filter_condition = None
            if filters:
                filter_conditions = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        # 리스트 값은 OR 조건으로 처리
                        or_conditions = [
                            models.FieldCondition(
                                key=key,
                                match=models.MatchValue(value=v)
                            ) for v in value
                        ]
                        filter_conditions.append(models.Filter(
                            should=or_conditions
                        ))
                    else:
                        # 단일 값은 정확히 일치하는 조건으로 처리
                        filter_conditions.append(models.Filter(
                            must=[
                                models.FieldCondition(
                                    key=key,
                                    match=models.MatchValue(value=value)
                                )
                            ]
                        ))
                
                # 모든 필터 조건을 AND로 결합
                filter_condition = models.Filter(
                    must=filter_conditions
                )
            
            # 벡터 검색 수행
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector.tolist(),
                limit=limit,
                query_filter=filter_condition,
                with_payload=True,
                with_vectors=False  # 벡터 데이터는 반환하지 않음
            )
            
            # 결과 처리
            results = []
            for result in search_results:
                # 결과 객체에 점수 추가
                item = result.payload.copy() if result.payload else {}
                item["id"] = result.id
                item["vector_score"] = float(result.score)
                results.append(item)
            
            return results
        except Exception as e:
            logger.error(f"벡터 검색 중 오류 발생: {str(e)}")
            return []
    
    def delete_vector(self, collection_name: str, vector_id: str) -> bool:
        """
        벡터 삭제
        
        Args:
            collection_name: 컬렉션 이름
            vector_id: 벡터 ID
            
        Returns:
            성공 여부
        """
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(
                    points=[vector_id]
                )
            )
            logger.debug(f"벡터 삭제 완료: {collection_name}/{vector_id}")
            return True
        except Exception as e:
            logger.error(f"벡터 삭제 중 오류 발생: {str(e)}")
            return False
            
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        컬렉션 정보 조회
        
        Args:
            collection_name: 컬렉션 이름
            
        Returns:
            컬렉션 정보
        """
        try:
            collection_info = self.client.get_collection(collection_name=collection_name)
            
            # Qdrant 클라우드와 로컬 버전에서 다른 응답 형식 처리
            info = {
                "name": collection_name,
                "vectors_count": collection_info.vectors_count,
                "status": collection_info.status
            }
            
            # 벡터 크기와 거리 정보 추가
            if hasattr(collection_info, 'config') and hasattr(collection_info.config, 'params'):
                if hasattr(collection_info.config.params, 'vectors'):
                    vectors_info = collection_info.config.params.vectors
                    info["vector_size"] = vectors_info.size
                    info["distance"] = vectors_info.distance
            
            return info
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 중 오류 발생: {str(e)}")
            return {}
    
    def _get_vector_size(self, collection_name: str) -> int:
        """
        컬렉션의 벡터 크기를 반환합니다.
        
        Args:
            collection_name: 컬렉션 이름
            
        Returns:
            벡터 크기 (차원 수)
        """
        try:
            collection_info = self.get_collection_info(collection_name)
            return collection_info.get('vector_size', 1024)  # 기본값 1024 사용
        except Exception as e:
            logger.error(f"벡터 크기 조회 중 오류 발생: {str(e)}")
            return 1024  # 오류 발생 시 기본값 1024 반환
    
    def filter_vectors(
        self,
        collection_name: str,
        filters: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        필터 조건으로 벡터 검색 (태그 기반 검색 등)
        
        Args:
            collection_name: 컬렉션 이름
            filters: 필터링 조건 (예: {"tags": {"$in": ["AI", "벡터DB"]}})
            limit: 반환할 결과 수
            offset: 결과 오프셋 (페이지네이션)
            
        Returns:
            검색 결과 목록
        """
        try:
            # 필터 조건 구성
            filter_condition = self._build_filter_condition(filters)
            
            # search 메서드를 사용하여 필터링 수행 (scroll 대신)
            # 임의의 쿼리 벡터를 사용하지 않고 필터링만 수행
            vector_size = self._get_vector_size(collection_name)
            dummy_vector = [0.0] * vector_size
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=dummy_vector,
                query_filter=filter_condition,
                limit=limit + offset,
                with_payload=True,
                with_vectors=False,
                score_threshold=0.0  # 유사도 점수를 무시하고 필터링만 적용
            )
            
            # 결과 처리
            results = []
            for i, result in enumerate(search_results):
                # 오프셋 이전의 결과는 건너뛰
                if i < offset:
                    continue
                    
                # 결과 객체 구성
                item = result.payload.copy() if result.payload else {}
                item["id"] = result.id
                results.append(item)
                
                # 최대 결과 수에 도달하면 중단
                if len(results) >= limit:
                    break
            
            logger.debug(f"필터 검색 완료: {collection_name} (결과: {len(results)}개)")
            return results
        except Exception as e:
            logger.error(f"필터 검색 중 오류 발생: {str(e)}")
            return []
    
    def _build_filter_condition(self, filters: Dict[str, Any]) -> Optional[models.Filter]:
        """
        필터 조건을 Qdrant Filter 객체로 변환
        
        Args:
            filters: 필터링 조건 딕셔너리
            
        Returns:
            Qdrant Filter 객체
        """
        if not filters:
            return None
            
        must_conditions = []
        should_conditions = []
        must_not_conditions = []
        
        for key, value in filters.items():
            if isinstance(value, dict):
                # 연산자 기반 필터 ($in, $gt, $lt 등)
                for op, op_value in value.items():
                    if op == "$in":
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                match=models.MatchAny(any=op_value)
                            )
                        )
                    elif op == "$nin":
                        must_not_conditions.append(
                            models.FieldCondition(
                                key=key,
                                match=models.MatchAny(any=op_value)
                            )
                        )
                    elif op == "$gt":
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                range=models.Range(gt=op_value)
                            )
                        )
                    elif op == "$gte":
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                range=models.Range(gte=op_value)
                            )
                        )
                    elif op == "$lt":
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                range=models.Range(lt=op_value)
                            )
                        )
                    elif op == "$lte":
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                range=models.Range(lte=op_value)
                            )
                        )
            else:
                # 일반 정확한 매치
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )
        
        # 필터 객체 구성
        if must_conditions or should_conditions or must_not_conditions:
            return models.Filter(
                must=must_conditions if must_conditions else None,
                should=should_conditions if should_conditions else None,
                must_not=must_not_conditions if must_not_conditions else None
            )
        
        return None
        
    def recommend_similar_users(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        유사한 사용자 추천
        
        Args:
            user_id: 사용자 ID
            limit: 추천할 사용자 수
            
        Returns:
            유사한 사용자 목록
        """
        try:
            # 사용자 벡터 조회
            user_vector_result = self.client.retrieve(
                collection_name="users",
                ids=[user_id],
                with_vectors=True
            )
            
            if not user_vector_result or len(user_vector_result) == 0:
                logger.warning(f"사용자 벡터를 찾을 수 없음: {user_id}")
                return []
                
            # 사용자 벡터를 이용해 유사한 사용자 검색
            user_vector = np.array(user_vector_result[0].vector)
            
            # 자기 자신을 제외하는 필터 적용
            filter_condition = models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="id",
                        match=models.MatchValue(
                            value=user_id
                        )
                    )
                ]
            )
            
            # 유사한 사용자 검색
            search_results = self.client.search(
                collection_name="users",
                query_vector=user_vector.tolist(),
                limit=limit,
                filter=filter_condition,
                with_payload=True
            )
            
            # 결과 처리
            results = []
            for result in search_results:
                user_data = result.payload.copy() if result.payload else {}
                user_data["id"] = result.id
                user_data["similarity_score"] = result.score
                results.append(user_data)
                
            logger.debug(f"유사 사용자 추천 완료: {user_id} (결과: {len(results)}개)")
            return results
        except Exception as e:
            logger.error(f"유사 사용자 추천 중 오류 발생: {str(e)}")
            return []
