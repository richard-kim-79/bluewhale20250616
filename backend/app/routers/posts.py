from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from app.routers.auth import User, get_current_user
from app.tasks.embedding_tasks import embed_post
from app.tasks.notification_tasks import send_notification

router = APIRouter()

# 모델 정의
class PostBase(BaseModel):
    content: str
    
class PostCreate(PostBase):
    tags: Optional[List[str]] = Field(default=[])

class Post(PostBase):
    id: str
    user_id: str
    user_name: str
    user_image: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    likes: int = 0
    comments: int = 0
    tags: List[str] = []
    
    class Config:
        orm_mode = True

# 포스트 작성
@router.post("/", response_model=Post, status_code=status.HTTP_201_CREATED)
async def create_post(
    post: PostCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    새 포스트 작성
    """
    # 텍스트에서 해시태그 추출
    tags = post.tags or []
    
    if not tags:
        words = post.content.split()
        for word in words:
            if word.startswith('#'):
                tag = word[1:].strip()
                if tag and tag not in tags:
                    tags.append(tag)
    
    # 포스트 ID 생성
    post_id = f"post_{uuid.uuid4().hex}"
    created_at = datetime.now()
    
    # 포스트 생성
    new_post = Post(
        id=post_id,
        user_id=current_user.id,
        user_name=current_user.name,
        user_image=current_user.image,
        content=post.content,
        created_at=created_at,
        updated_at=created_at,
        likes=0,
        comments=0,
        tags=tags
    )
    
    # 실제 구현: MongoDB에 포스트 저장
    # await db.posts.insert_one(new_post.dict())
    
    # 백그라운드 작업: 벡터 임베딩 생성 및 저장
    post_data = {
        "content": post.content,
        "tags": tags,
        "user_id": current_user.id,
        "created_at": created_at.isoformat()
    }
    background_tasks.add_task(embed_post.delay, post_id, post_data)
    
    # 팔로워에게 알림 전송 (실제 구현에서는 팔로워 목록 조회 후 전송)
    # followers = await db.followers.find({"followed_id": current_user.id}).to_list(None)
    # for follower in followers:
    #     background_tasks.add_task(
    #         send_notification.delay,
    #         follower["follower_id"],
    #         "new_post",
    #         f"{current_user.name}님의 새 포스트",
    #         post.content[:50] + "...",
    #         {"post_id": post_id}
    #     )
    
    return new_post

# 피드 가져오기
@router.get("/feed", response_model=List[Post])
async def get_feed(
    feed_type: str = Query("forYou", description="피드 타입: forYou, local, global"),
    skip: int = 0,
    limit: int = 10,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    사용자 피드 가져오기
    """
    # 실제 구현에서는 데이터베이스에서 피드 가져오기
    # 여기서는 목업 데이터 제공
    
    posts = [
        Post(
            id="post1",
            user_id="user1",
            user_name="김벡터",
            user_image="https://via.placeholder.com/40",
            content="오늘 BlueWhale에 새로운 AI 논문을 업로드했습니다. 벡터 임베딩 기반 SNS의 미래에 대한 내용입니다.",
            created_at=datetime.now(),
            likes=42,
            comments=7,
            tags=["AI", "벡터임베딩", "논문"]
        ),
        Post(
            id="post2",
            user_id="user2",
            user_name="이데이터",
            user_image="https://via.placeholder.com/40",
            content="벡터 데이터베이스의 성능 최적화에 관한 새로운 기술을 발견했습니다. 관심 있으신 분들은 첨부된 문서를 확인해보세요.",
            created_at=datetime.now(),
            likes=28,
            comments=12,
            tags=["벡터DB", "Qdrant", "성능최적화"]
        ),
        Post(
            id="post3",
            user_id="user3",
            user_name="박인공지능",
            user_image="https://via.placeholder.com/40",
            content="최근 개발한 문서 파싱 알고리즘의 정확도가 95%를 넘었습니다! 곧 BlueWhale에 적용될 예정입니다.",
            created_at=datetime.now(),
            likes=56,
            comments=9,
            tags=["문서파싱", "NLP", "정확도"]
        ),
    ]
    
    return posts[skip:skip+limit]

# 포스트 상세 조회
@router.get("/{post_id}", response_model=Post)
async def get_post(
    post_id: str,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    포스트 상세 정보 조회
    """
    # 실제 구현에서는 데이터베이스에서 포스트 조회
    # 여기서는 목업 데이터 제공
    
    post = Post(
        id=post_id,
        user_id="user1",
        user_name="김벡터",
        user_image="https://via.placeholder.com/40",
        content="오늘 BlueWhale에 새로운 AI 논문을 업로드했습니다. 벡터 임베딩 기반 SNS의 미래에 대한 내용입니다.",
        created_at=datetime.now(),
        likes=42,
        comments=7,
        tags=["AI", "벡터임베딩", "논문"]
    )
    
    return post

# 포스트 좋아요
@router.post("/{post_id}/like", status_code=status.HTTP_200_OK)
async def like_post(
    post_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    포스트 좋아요 토글
    """
    # 실제 구현에서는 데이터베이스에서 좋아요 상태 토글
    # liked = await toggle_like(post_id, current_user.id)
    liked = True  # 목업: 항상 좋아요 상태로 가정
    
    # 실제 구현: 포스트 작성자에게 알림 전송
    # post = await db.posts.find_one({"_id": post_id})
    # if post and liked and post["user_id"] != current_user.id:
    #     background_tasks.add_task(
    #         send_notification.delay,
    #         post["user_id"],
    #         "like",
    #         f"{current_user.name}님이 회원님의 포스트를 좋아합니다",
    #         "",
    #         {"post_id": post_id, "user_id": current_user.id}
    #     )
    
    return {"status": "success", "message": "좋아요가 토글되었습니다", "liked": liked}

class CommentCreate(BaseModel):
    content: str

class Comment(BaseModel):
    id: str
    post_id: str
    user_id: str
    user_name: str
    user_image: Optional[str] = None
    content: str
    created_at: datetime
    likes: int = 0
    
    class Config:
        orm_mode = True

# 포스트 댓글 작성
@router.post("/{post_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
async def create_comment(
    post_id: str,
    comment: CommentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    포스트에 댓글 작성
    """
    # 실제 구현에서는 데이터베이스에 댓글 저장
    # await db.comments.insert_one(new_comment.dict())
    
    comment_id = f"comment_{uuid.uuid4().hex}"
    created_at = datetime.now()
    
    new_comment = Comment(
        id=comment_id,
        post_id=post_id,
        user_id=current_user.id,
        user_name=current_user.name,
        user_image=current_user.image,
        content=comment.content,
        created_at=created_at,
        likes=0
    )
    
    # 실제 구현: 포스트 작성자에게 알림 전송
    # post = await db.posts.find_one({"_id": post_id})
    # if post and post["user_id"] != current_user.id:
    #     background_tasks.add_task(
    #         send_notification.delay,
    #         post["user_id"],
    #         "comment",
    #         f"{current_user.name}님이 회원님의 포스트에 댓글을 남겼습니다",
    #         comment.content[:50] + ("..." if len(comment.content) > 50 else ""),
    #         {"post_id": post_id, "comment_id": comment_id}
    #     )
    
    # 댓글에서 언급된 사용자에게 알림 전송
    # words = comment.content.split()
    # for word in words:
    #     if word.startswith('@'):
    #         username = word[1:].strip()
    #         if username:
    #             # 사용자 이름으로 사용자 ID 조회
    #             user = await db.users.find_one({"username": username})
    #             if user and user["_id"] != current_user.id:
    #                 background_tasks.add_task(
    #                     send_notification.delay,
    #                     user["_id"],
    #                     "mention",
    #                     f"{current_user.name}님이 댓글에서 회원님을 언급했습니다",
    #                     comment.content[:50] + ("..." if len(comment.content) > 50 else ""),
    #                     {"post_id": post_id, "comment_id": comment_id}
    #                 )
    
    return new_comment
