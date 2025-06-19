from sentence_transformers import SentenceTransformer
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Union
import torch

logger = logging.getLogger(__name__)

class VectorEmbedder:
    """
    텍스트를 벡터로 임베딩하는 서비스
    sentence-transformers 라이브러리를 사용하여 텍스트를 고차원 벡터 공간에 매핑
    """
    
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        """
        임베딩 모델 초기화
        
        Args:
            model_name: sentence-transformers 모델 이름
                        기본값은 BAAI/bge-m3 (다국어 지원 모델)
        """
        try:
            # GPU 사용 가능 여부 확인
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # 모델 로드
            self.model = SentenceTransformer(model_name, device=device)
            self.vector_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"임베딩 모델 '{model_name}' 로드 완료 (차원: {self.vector_dim})")
        except Exception as e:
            logger.error(f"임베딩 모델 로드 중 오류 발생: {str(e)}")
            raise
    
    def embed_text(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        텍스트를 벡터로 임베딩
        
        Args:
            text: 임베딩할 텍스트 또는 텍스트 목록
            
        Returns:
            임베딩 벡터 또는 벡터 배열
        """
        try:
            # 빈 텍스트 처리
            if not text:
                if isinstance(text, str):
                    return np.zeros(self.vector_dim)
                else:
                    return np.zeros((len(text), self.vector_dim))
                    
            # 단일 텍스트 또는 텍스트 목록 처리
            if isinstance(text, str):
                # 텍스트가 너무 길면 잘라내기
                if len(text) > 10000:
                    logger.warning(f"텍스트가 너무 길어 잘라냄: {len(text)} -> 10000")
                    text = text[:10000]
                
                embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
                return embedding
            else:
                # 빈 목록 처리
                if len(text) == 0:
                    return np.zeros((0, self.vector_dim))
                    
                # 텍스트 목록의 각 항목이 너무 길면 잘라내기
                processed_texts = [t[:10000] if len(t) > 10000 else t for t in text]
                embeddings = self.model.encode(processed_texts, convert_to_numpy=True, normalize_embeddings=True)
                return embeddings
        except Exception as e:
            logger.error(f"텍스트 임베딩 중 오류 발생: {str(e)}")
            # 오류 발생 시 0으로 채워진 벡터 반환
            if isinstance(text, str):
                return np.zeros(self.vector_dim)
            else:
                return np.zeros((len(text), self.vector_dim))
    
    def embed_document(self, document: Dict[str, Any]) -> np.ndarray:
        """
        문서 객체를 벡터로 임베딩
        
        Args:
            document: 문서 객체 (제목, 요약, 내용 등 포함)
            
        Returns:
            임베딩 벡터
        """
        try:
            # 문서의 다양한 필드를 결합하여 임베딩
            text_parts = []
            
            if "title" in document and document["title"]:
                text_parts.append(document["title"])
                
            if "summary" in document and document["summary"]:
                text_parts.append(document["summary"])
                
            if "content" in document and document["content"]:
                # 내용이 너무 길면 앞부분만 사용
                content = document["content"]
                if len(content) > 5000:
                    logger.warning(f"문서 내용이 너무 길어 잘라냄: {len(content)} -> 5000")
                    content = content[:5000]
                text_parts.append(content)
                
            if "tags" in document and document["tags"]:
                if isinstance(document["tags"], list):
                    text_parts.append(" ".join(document["tags"]))
                    
            # 모든 텍스트 부분 결합
            combined_text = " ".join(text_parts)
            
            # 결합된 텍스트 임베딩
            return self.embed_text(combined_text)
        except Exception as e:
            logger.error(f"문서 임베딩 중 오류 발생: {str(e)}")
            return np.zeros(self.vector_dim)
    
    def embed_user_profile(self, user_profile: Dict[str, Any]) -> np.ndarray:
        """
        사용자 프로필을 벡터로 임베딩
        
        Args:
            user_profile: 사용자 프로필 객체
            
        Returns:
            임베딩 벡터
        """
        try:
            # 사용자 프로필의 다양한 필드를 결합하여 임베딩
            text_parts = []
            
            if "name" in user_profile and user_profile["name"]:
                text_parts.append(user_profile["name"])
                
            if "bio" in user_profile and user_profile["bio"]:
                text_parts.append(user_profile["bio"])
                
            if "interests" in user_profile and user_profile["interests"]:
                if isinstance(user_profile["interests"], list):
                    text_parts.append(" ".join(user_profile["interests"]))
                    
            # 모든 텍스트 부분 결합
            combined_text = " ".join(text_parts)
            
            # 결합된 텍스트 임베딩
            return self.embed_text(combined_text)
        except Exception as e:
            logger.error(f"사용자 프로필 임베딩 중 오류 발생: {str(e)}")
            return np.zeros(self.vector_dim)
            
    def get_vector_dimension(self) -> int:
        """
        임베딩 벡터의 차원 반환
        
        Returns:
            벡터 차원
        """
        return self.vector_dim
