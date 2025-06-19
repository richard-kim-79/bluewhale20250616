from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.routers.auth import User, get_current_user

router = APIRouter()

# 모델 정의
class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    image: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    followers_count: int = 0
    following_count: int = 0
    
class UserRecommendation(BaseModel):
    id: str
    name: str
    image: Optional[str] = None
    bio: Optional[str] = None
    vector_score: float
    common_interests: List[str] = []

# 사용자 프로필 조회
@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    사용자 프로필 조회
    """
    # 실제 구현에서는 데이터베이스에서 사용자 정보 조회
    # 여기서는 목업 데이터 제공
    
    if user_id == "user1":
        return UserProfile(
            id="user1",
            name="김벡터",
            email="vector@example.com",
            image="https://via.placeholder.com/40",
            bio="벡터 임베딩과 AI 연구자",
            created_at=datetime.now(),
            followers_count=128,
            following_count=56
        )
    elif user_id == "user2":
        return UserProfile(
            id="user2",
            name="이데이터",
            email="data@example.com",
            image="https://via.placeholder.com/40",
            bio="벡터 데이터베이스 전문가",
            created_at=datetime.now(),
            followers_count=87,
            following_count=42
        )
    elif user_id == "user3":
        return UserProfile(
            id="user3",
            name="박인공지능",
            email="ai@example.com",
            image="https://via.placeholder.com/40",
            bio="NLP 및 문서 파싱 전문가",
            created_at=datetime.now(),
            followers_count=156,
            following_count=98
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )

# 사용자 포스트 조회
@router.get("/{user_id}/posts", response_model=List)
async def get_user_posts(
    user_id: str,
    skip: int = 0,
    limit: int = 10,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    사용자가 작성한 포스트 조회
    """
    # 실제 구현에서는 데이터베이스에서 사용자의 포스트 조회
    # 여기서는 목업 데이터 제공
    
    if user_id == "user1":
        return [
            {
                "id": "post1",
                "content": "오늘 BlueWhale에 새로운 AI 논문을 업로드했습니다. 벡터 임베딩 기반 SNS의 미래에 대한 내용입니다.",
                "created_at": datetime.now(),
                "likes": 42,
                "comments": 7,
                "tags": ["AI", "벡터임베딩", "논문"]
            }
        ]
    else:
        return []

# 사용자 문서 조회
@router.get("/{user_id}/documents", response_model=List)
async def get_user_documents(
    user_id: str,
    skip: int = 0,
    limit: int = 10,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    사용자가 업로드한 문서 조회
    """
    # 실제 구현에서는 데이터베이스에서 사용자의 문서 조회
    # 여기서는 목업 데이터 제공
    
    if user_id == "user1":
        return [
            {
                "id": "doc1",
                "title": "벡터 임베딩 기반 SNS의 미래",
                "summary": "이 문서는 벡터 임베딩 기술을 활용한 소셜 네트워크 서비스의 미래 가능성을 탐구합니다.",
                "file_type": "pdf",
                "created_at": datetime.now(),
                "ai_references": 128,
                "tags": ["벡터임베딩", "SNS", "AI"]
            }
        ]
    else:
        return []

# 벡터 기반 친구 추천
@router.get("/recommendations", response_model=List[UserRecommendation])
async def get_user_recommendations(
    limit: int = Query(10, description="반환할 추천 사용자 수"),
    current_user: User = Depends(get_current_user)
):
    """
    벡터 유사도 기반 친구 추천
    """
    # 실제 구현에서는 사용자의 벡터 임베딩을 기반으로 유사한 사용자 검색
    # 여기서는 목업 데이터 제공
    
    recommendations = [
        UserRecommendation(
            id="user2",
            name="이데이터",
            image="https://via.placeholder.com/40",
            bio="벡터 데이터베이스 전문가",
            vector_score=0.92,
            common_interests=["벡터임베딩", "데이터베이스", "AI"]
        ),
        UserRecommendation(
            id="user3",
            name="박인공지능",
            image="https://via.placeholder.com/40",
            bio="NLP 및 문서 파싱 전문가",
            vector_score=0.87,
            common_interests=["AI", "NLP", "문서파싱"]
        ),
        UserRecommendation(
            id="user4",
            name="최검색",
            image="https://via.placeholder.com/40",
            bio="검색 엔진 개발자",
            vector_score=0.82,
            common_interests=["검색엔진", "벡터검색", "정보검색"]
        )
    ]
    
    return recommendations[:limit]

# 사용자 팔로우
@router.post("/{user_id}/follow", status_code=status.HTTP_200_OK)
async def follow_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    사용자 팔로우 토글
    """
    # 실제 구현에서는 데이터베이스에서 팔로우 상태 토글
    # 여기서는 성공 응답만 반환
    
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자기 자신을 팔로우할 수 없습니다"
        )
    
    return {"status": "success", "message": "팔로우 상태가 토글되었습니다"}
