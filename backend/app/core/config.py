from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # 기본 설정
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "BlueWhale"
    
    # CORS 설정
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://bluewhale2025.vercel.app"]
    
    # 데이터베이스 설정
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "bluewhale"
    
    # JWT 설정
    SECRET_KEY: str = "YOUR_SECRET_KEY_HERE"  # 실제 배포 시 환경 변수로 관리
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24시간
    
    # AWS S3 설정
    AWS_ACCESS_KEY_ID: str = "YOUR_AWS_ACCESS_KEY_ID"  # 실제 배포 시 환경 변수로 관리
    AWS_SECRET_ACCESS_KEY: str = "YOUR_AWS_SECRET_ACCESS_KEY"  # 실제 배포 시 환경 변수로 관리
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: str = "bluewhale-documents"
    
    # Qdrant 설정
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    
    # Redis 설정
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    # 임베딩 모델 설정
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = 'allow'


settings = Settings()
