from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings

router = APIRouter()

# 모델 정의
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    id: str
    email: str
    name: str
    image: Optional[str] = None
    
class UserInDB(User):
    hashed_password: str

# OAuth2 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

# JWT 토큰 생성
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# 토큰 검증 및 사용자 가져오기
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않은 인증 정보",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    # 실제 구현에서는 데이터베이스에서 사용자 정보를 가져옵니다
    # user = get_user(token_data.username)
    # if user is None:
    #     raise credentials_exception
    
    # 목업 사용자 정보
    user = User(
        id="user1",
        email=token_data.username,
        name="김벡터",
        image="https://via.placeholder.com/40"
    )
    return user

# 로그인 엔드포인트
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # 실제 구현에서는 데이터베이스에서 사용자 검증
    # user = authenticate_user(form_data.username, form_data.password)
    # if not user:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="잘못된 이메일 또는 비밀번호",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    
    # 목업 구현: 항상 성공
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 소셜 로그인 엔드포인트 (Google OAuth)
@router.post("/social", response_model=Token)
async def social_login(provider: str, token: str):
    """
    소셜 로그인 처리 (Google, 등)
    """
    # 실제 구현에서는 소셜 제공자의 토큰을 검증하고 사용자 정보를 가져옵니다
    # 여기서는 목업 구현만 제공합니다
    
    if provider != "google":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="지원하지 않는 소셜 로그인 제공자입니다"
        )
    
    # 목업: 항상 성공
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": "user@example.com"}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 현재 사용자 정보 가져오기
@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    현재 로그인한 사용자 정보 반환
    """
    return current_user
