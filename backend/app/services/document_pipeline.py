import logging
import tempfile
import os
from typing import Dict, Any, Optional, List, Tuple
import asyncio
import time
import uuid
from datetime import datetime

from app.services.document_parser import DocumentParser
from app.services.summarizer import DocumentSummarizer
from app.services.tagger import DocumentTagger
from app.services.embedder import VectorEmbedder
from app.services.vector_db import VectorDBService
from app.services.file_storage import S3FileStorage

logger = logging.getLogger(__name__)

class DocumentProcessingPipeline:
    """
    문서 처리 파이프라인
    업로드된 문서를 파싱, 요약, 태그 추출, 벡터 임베딩 생성 등의 단계로 처리
    """
    
    def __init__(
        self,
        parser: DocumentParser,
        summarizer: DocumentSummarizer,
        tagger: DocumentTagger,
        embedder: VectorEmbedder,
        vector_db: VectorDBService,
        file_storage: S3FileStorage,
        collection_name: str = "documents"
    ):
        """
        문서 처리 파이프라인 초기화
        
        Args:
            parser: 문서 파서
            summarizer: 문서 요약기
            tagger: 태그 추출기
            embedder: 벡터 임베딩 생성기
            vector_db: 벡터 데이터베이스 서비스
            file_storage: 파일 저장소 서비스
            collection_name: 벡터 컬렉션 이름
        """
        self.parser = parser
        self.summarizer = summarizer
        self.tagger = tagger
        self.embedder = embedder
        self.vector_db = vector_db
        self.file_storage = file_storage
        self.collection_name = collection_name
    
    async def initialize(self):
        """
        파이프라인 초기화 (벡터 컬렉션 생성 등)
        """
        # 벡터 컬렉션 생성
        vector_size = self.embedder.get_vector_dimension()
        await self.vector_db.create_collection(self.collection_name, vector_size)
    
    async def process_document(
        self,
        file_path: str,
        file_type: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        문서 처리 파이프라인 실행
        
        Args:
            file_path: 처리할 파일 경로
            file_type: 파일 형식
            metadata: 문서 메타데이터
            
        Returns:
            처리 결과
        """
        start_time = time.time()
        document_id = metadata.get("id", str(uuid.uuid4()))
        
        try:
            logger.info(f"문서 처리 시작: {document_id}")
            
            # 1. 파일 메타데이터 추출
            file_metadata = self.parser.extract_metadata(file_path, file_type)
            
            # 2. 문서 파싱
            logger.info(f"문서 파싱 중: {document_id}")
            text_content = await self.parser.parse_document(file_path, file_type)
            
            if not text_content:
                raise ValueError(f"문서 파싱 실패: {document_id}")
            
            # 3. 문서 요약
            logger.info(f"문서 요약 중: {document_id}")
            summary = await self.summarizer.summarize(text_content)
            
            # 4. 태그 추출
            logger.info(f"태그 추출 중: {document_id}")
            tags = await self.tagger.extract_tags(text_content)
            
            # 5. 벡터 임베딩 생성
            logger.info(f"벡터 임베딩 생성 중: {document_id}")
            document_data = {
                "title": metadata.get("title", ""),
                "summary": summary,
                "content": text_content,
                "tags": tags
            }
            embedding = await self.embedder.embed_document(document_data)
            
            # 6. 벡터 데이터베이스에 저장
            logger.info(f"벡터 데이터베이스에 저장 중: {document_id}")
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
            
            await self.vector_db.upsert_vector(
                collection_name=self.collection_name,
                vector=embedding,
                payload=vector_payload,
                vector_id=document_id
            )
            
            # 7. 결과 반환
            processing_time = time.time() - start_time
            
            result = {
                "document_id": document_id,
                "title": metadata.get("title", ""),
                "summary": summary,
                "tags": tags,
                "file_metadata": file_metadata,
                "vector_id": document_id,
                "processing_time": processing_time,
                "status": "success"
            }
            
            logger.info(f"문서 처리 완료: {document_id} (소요 시간: {processing_time:.2f}초)")
            return result
        
        except Exception as e:
            logger.error(f"문서 처리 중 오류 발생: {str(e)}")
            
            # 실패 결과 반환
            return {
                "document_id": document_id,
                "status": "error",
                "error": str(e),
                "processing_time": time.time() - start_time
            }
    
    async def process_uploaded_file(
        self,
        upload_result: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        업로드된 파일 처리
        
        Args:
            upload_result: 파일 업로드 결과
            metadata: 문서 메타데이터
            
        Returns:
            처리 결과
        """
        try:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            # S3에서 파일 다운로드
            object_name = upload_result.get("object_name")
            await self.file_storage.download_file(object_name, tmp_path)
            
            # 파일 형식 결정
            file_type = metadata.get("file_type", "")
            if not file_type and "." in object_name:
                file_type = object_name.split(".")[-1].lower()
            
            # 문서 처리
            result = await self.process_document(tmp_path, file_type, metadata)
            
            # 임시 파일 삭제
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 중 오류 발생: {str(e)}")
            
            return result
        
        except Exception as e:
            logger.error(f"업로드된 파일 처리 중 오류 발생: {str(e)}")
            return {
                "document_id": metadata.get("id", str(uuid.uuid4())),
                "status": "error",
                "error": str(e)
            }
    
    async def reprocess_document(self, document_id: str) -> Dict[str, Any]:
        """
        기존 문서 재처리
        
        Args:
            document_id: 문서 ID
            
        Returns:
            처리 결과
        """
        # 이 메서드는 실제 구현에서 문서의 원본 파일을 다시 가져와 처리하는 로직 포함
        # 여기서는 간단한 스켈레톤만 제공
        
        logger.info(f"문서 재처리 요청: {document_id}")
        return {
            "document_id": document_id,
            "status": "not_implemented",
            "message": "문서 재처리 기능이 아직 구현되지 않았습니다."
        }
