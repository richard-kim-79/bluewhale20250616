from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Query, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import os
import tempfile

from app.routers.auth import User, get_current_user
from app.tasks.document_tasks import process_document, update_ai_reference_count
from app.services.file_storage import S3FileStorage
from app.core.config import settings

router = APIRouter()

# S3 파일 스토리지 초기화
file_storage = S3FileStorage(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
    bucket_name=settings.S3_BUCKET_NAME
)

# 모델 정의
class DocumentBase(BaseModel):
    title: str
    
class DocumentCreate(DocumentBase):
    pass

class DocumentSummary(BaseModel):
    text: str
    
class DocumentTag(BaseModel):
    name: str
    
class Document(BaseModel):
    id: str
    title: str
    file_name: str
    file_type: str
    file_size: int
    user_id: str
    user_name: str
    uploaded_at: datetime
    summary: Optional[str] = None
    tags: List[str] = []
    ai_references: int = 0
    status: str  # processing, completed, error
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    
    class Config:
        orm_mode = True

# 문서 업로드
@router.post("/upload", response_model=Document, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """
    새 문서 업로드
    """
    # 파일 유효성 검사
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일이 비어있습니다."
        )
    
    # 파일 확장자 확인
    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in ["pdf", "txt", "html", "md"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="지원되지 않는 파일 형식입니다. PDF, TXT, HTML, MD 파일만 업로드 가능합니다."
        )
    
    # 문서 ID 생성
    document_id = f"doc_{uuid.uuid4().hex}"
    uploaded_at = datetime.now()
    
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            content = await file.read()
            temp_file.write(content)
        
        # S3에 파일 업로드
        s3_key = f"documents/{current_user.id}/{document_id}/{file.filename}"
        await file_storage.upload_file(temp_path, s3_key)
        
        # 임시 파일 삭제
        os.unlink(temp_path)
        
        # 문서 메타데이터
        metadata = {
            "title": title,
            "file_name": file.filename,
            "file_type": file_ext,
            "file_size": len(content),
            "user_id": current_user.id,
            "user_name": current_user.name,
            "uploaded_at": uploaded_at.isoformat()
        }
        
        # 실제 구현: MongoDB에 문서 메타데이터 저장
        # await db.documents.insert_one({
        #     "_id": document_id,
        #     **metadata,
        #     "summary": "이 문서는 처리 중입니다. 잠시 후 다시 확인해주세요.",
        #     "tags": [],
        #     "ai_references": 0,
        #     "status": "processing"
        # })
        
        # 백그라운드 작업: 문서 처리 작업 시작
        background_tasks.add_task(process_document.delay, document_id, s3_key, file_ext, metadata)
        
        # 응답 생성
        document = Document(
            id=document_id,
            title=title,
            file_name=file.filename,
            file_type=file_ext,
            file_size=len(content),
            user_id=current_user.id,
            user_name=current_user.name,
            uploaded_at=uploaded_at,
            summary="이 문서는 처리 중입니다. 잠시 후 다시 확인해주세요.",
            tags=[],
            ai_references=0,
            status="processing"
        )
        
        return document
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문서 업로드 중 오류가 발생했습니다: {str(e)}"
        )

# 문서 목록 조회
@router.get("/", response_model=List[Document])
async def get_documents(
    skip: int = 0,
    limit: int = 10,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    문서 목록 조회
    """
    # 실제 구현에서는 데이터베이스에서 문서 목록 조회
    # await db.documents.find({"user_id": current_user.id}).skip(skip).limit(limit)
    
    # 목업 데이터 제공
    documents = [
        Document(
            id="doc1",
            title="벡터 임베딩 기반 SNS 플랫폼 설계",
            file_name="vector_sns_design.pdf",
            file_type="pdf",
            file_size=1024000,
            user_id="user1",
            user_name="김벡터",
            uploaded_at=datetime.now(),
            summary="이 문서는 벡터 임베딩 기술을 활용한 소셜 네트워크 서비스의 설계 방법론을 다룹니다. 문서 처리, 벡터 임베딩 생성, 유사도 검색 등의 핵심 기술을 설명하고, 이를 통해 사용자 경험을 향상시키는 방법을 제시합니다.",
            tags=["벡터임베딩", "SNS", "설계", "AI"],
            ai_references=42,
            status="completed"
        ),
        Document(
            id="doc2",
            title="벡터 데이터베이스의 성능 최적화 방법론",
            file_name="vector_db_optimization.pdf",
            file_type="pdf",
            file_size=2048000,
            user_id="user2",
            user_name="이데이터",
            uploaded_at=datetime.now(),
            summary="이 문서는 Qdrant, FAISS 등 벡터 데이터베이스의 성능을 최적화하는 다양한 방법을 설명합니다. 벡터 데이터베이스의 특성과 성능 최적화 전략을 다룹니다.",
            tags=["벡터DB", "Qdrant", "성능최적화"],
            ai_references=21,
            status="completed"
        )
    ]
    
    return documents[skip:skip+limit]

# 문서 상세 조회
@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    문서 상세 정보 조회
    """
    # 실제 구현에서는 데이터베이스에서 문서 조회
    # await db.documents.find_one({"_id": document_id})
    
    # AI 참조 횟수 증가 (백그라운드 작업)
    background_tasks.add_task(update_ai_reference_count.delay, document_id, 1)
    
    # 목업 데이터 제공
    document = Document(
        id=document_id,
        title="벡터 임베딩 기반 SNS 플랫폼 설계",
        file_name="vector_sns_design.pdf",
        file_type="pdf",
        file_size=1024000,
        user_id="user1",
        user_name="김벡터",
        uploaded_at=datetime.now(),
        summary="이 문서는 벡터 임베딩 기술을 활용한 소셜 네트워크 서비스의 설계 방법론을 다룹니다. 문서 처리, 벡터 임베딩 생성, 유사도 검색 등의 핵심 기술을 설명하고, 이를 통해 사용자 경험을 향상시키는 방법을 제시합니다.",
        tags=["벡터임베딩", "SNS", "설계", "AI"],
        ai_references=42,
        status="completed"
    )
    
    # 실제 구현에서는 문서가 없을 경우 404 오류 반환
    # if not document:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="문서를 찾을 수 없습니다."
    #     )
    
    # 다운로드 URL 생성 (실제 구현에서 활성화)
    # document.download_url = await file_storage.generate_presigned_url(
    #     f"documents/{document.user_id}/{document.id}/{document.file_name}",
    #     expires_in=3600
    # )
    
    return document

# AI 참조 순위 상위 문서 조회
@router.get("/top-ai-reference", response_model=List[Document])
async def get_top_ai_reference_documents(
    limit: int = Query(10, description="반환할 문서 수"),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    AI가 가장 많이 참조한 문서 순위 조회
    """
    # 실제 구현에서는 데이터베이스에서 AI 참조 수 기준으로 정렬하여 조회
    # 여기서는 목업 데이터 제공
    
    documents = [
        Document(
            id="doc1",
            title="벡터 임베딩 기반 SNS의 미래",
            user_id="user1",
            user_name="김벡터",
            user_image="https://via.placeholder.com/40",
            file_url="https://example.com/documents/doc1.pdf",
            file_type="pdf",
            file_size=1024 * 1024,  # 1MB
            summary="이 문서는 벡터 임베딩 기술을 활용한 소셜 네트워크 서비스의 미래 가능성을 탐구합니다.",
            tags=["벡터임베딩", "SNS", "AI"],
            ai_references=128,
            created_at=datetime.now()
        ),
        Document(
            id="doc2",
            title="벡터 데이터베이스의 성능 최적화 방법론",
            user_id="user2",
            user_name="이데이터",
            user_image="https://via.placeholder.com/40",
            file_url="https://example.com/documents/doc2.pdf",
            file_type="pdf",
            file_size=2 * 1024 * 1024,  # 2MB
            summary="이 문서는 Qdrant, FAISS 등 벡터 데이터베이스의 성능을 최적화하는 다양한 방법을 설명합니다.",
            tags=["벡터DB", "Qdrant", "성능최적화"],
            ai_references=87,
            created_at=datetime.now()
        )
    ]
    
    # AI 참조 수 기준으로 정렬
    documents.sort(key=lambda x: x.ai_references, reverse=True)
    
    return documents[:limit]
