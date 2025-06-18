from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse

from app.routers import auth, posts, documents, search, users, admin
from app.core.config import settings
from app.core.monitoring import setup_monitoring

app = FastAPI(
    title="BlueWhale API",
    description="AI 기반 벡터 SNS 포털 API",
    version="1.0.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus 모니터링 설정
setup_monitoring(app)

# 라우터 등록
app.include_router(auth.router, prefix="/api/auth", tags=["인증"])
app.include_router(posts.router, prefix="/api/posts", tags=["포스트"])
app.include_router(documents.router, prefix="/api/docs", tags=["문서"])
app.include_router(search.router, prefix="/api/search", tags=["검색"])
app.include_router(users.router, prefix="/api/users", tags=["사용자"])

# Prometheus 모니터링 설정
setup_monitoring(app)

@app.get("/api/health")
async def health_check():
    """
    API 서버 상태 확인
    """
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/")
async def root():
    """
    API 루트 경로
    """
    return {"message": "BlueWhale API에 오신 것을 환영합니다. /docs에서 API 문서를 확인하세요."}
