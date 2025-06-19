import logging
from typing import Dict, Any, Optional
import os
import tempfile
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.services.document_parser import DocumentParser
from app.services.summarizer import DocumentSummarizer
from app.services.tagger import DocumentTagger
from app.services.embedder import VectorEmbedder
from app.services.vector_db import VectorDBService
from app.services.file_storage import S3FileStorage

logger = logging.getLogger(__name__)

# 서비스 인스턴스 초기화
parser = DocumentParser()
summarizer = DocumentSummarizer(model_name=settings.EMBEDDING_MODEL)
tagger = DocumentTagger()
embedder = VectorEmbedder(model_name=settings.EMBEDDING_MODEL)
vector_db = VectorDBService(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
file_storage = S3FileStorage(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
    bucket_name=settings.S3_BUCKET_NAME
)

@celery_app.task(name="app.tasks.document_tasks.process_document")
def process_document(document_id: str, file_path: str, file_type: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    문서 처리 작업
    
    Args:
        document_id: 문서 ID
        file_path: S3 객체 이름 또는 파일 경로
        file_type: 파일 형식
        metadata: 문서 메타데이터
        
    Returns:
        처리 결과
    """
    try:
        logger.info(f"문서 처리 작업 시작: {document_id}")
        
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # S3에서 파일 다운로드
        file_storage.download_file(file_path, tmp_path)
        
        # 문서 파싱
        text_content = parser.parse_document(tmp_path, file_type)
        
        if not text_content:
            raise ValueError(f"문서 파싱 실패: {document_id}")
        
        # 문서 요약
        summary = summarizer.summarize(text_content)
        
        # 태그 추출
        tags = tagger.extract_tags(text_content)
        
        # 벡터 임베딩 생성
        document_data = {
            "title": metadata.get("title", ""),
            "summary": summary,
            "content": text_content,
            "tags": tags
        }
        embedding = embedder.embed_document(document_data)
        
        # 벡터 데이터베이스에 저장
        vector_payload = {
            "document_id": document_id,
            "title": metadata.get("title", ""),
            "summary": summary,
            "tags": tags,
            "user_id": metadata.get("user_id", ""),
            "file_type": file_type,
            "created_at": datetime.now().isoformat(),
            "type": "document"
        }
        
        vector_db.upsert_vector(
            collection_name="documents",
            vector=embedding,
            payload=vector_payload,
            vector_id=document_id
        )
        
        # 임시 파일 삭제
        try:
            os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"임시 파일 삭제 중 오류 발생: {str(e)}")
        
        # 처리 결과 반환
        result = {
            "document_id": document_id,
            "title": metadata.get("title", ""),
            "summary": summary,
            "tags": tags,
            "vector_id": document_id,
            "status": "success"
        }
        
        logger.info(f"문서 처리 작업 완료: {document_id}")
        return result
    
    except Exception as e:
        logger.error(f"문서 처리 작업 중 오류 발생: {str(e)}")
        
        # 실패 결과 반환
        return {
            "document_id": document_id,
            "status": "error",
            "error": str(e)
        }

@celery_app.task(name="app.tasks.document_tasks.update_ai_reference_count")
def update_ai_reference_count(document_id: str, increment: int = 1) -> Dict[str, Any]:
    """
    문서의 AI 참조 횟수 업데이트
    
    Args:
        document_id: 문서 ID
        increment: 증가시킬 값
        
    Returns:
        업데이트 결과
    """
    try:
        logger.info(f"AI 참조 횟수 업데이트: {document_id} (+{increment})")
        
        # 실제 구현에서는 MongoDB에서 문서의 ai_references 필드 업데이트
        # 여기서는 성공 응답만 반환
        
        return {
            "document_id": document_id,
            "status": "success",
            "message": f"AI 참조 횟수 업데이트 완료 (+{increment})"
        }
    
    except Exception as e:
        logger.error(f"AI 참조 횟수 업데이트 중 오류 발생: {str(e)}")
        
        return {
            "document_id": document_id,
            "status": "error",
            "error": str(e)
        }
