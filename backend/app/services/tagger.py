from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
from keybert import KeyBERT
import logging
from typing import List, Dict, Any, Optional
import torch
import re

logger = logging.getLogger(__name__)

class DocumentTagger:
    """
    문서에서 태그 추출 서비스
    NER(Named Entity Recognition)과 KeyBERT를 사용하여 키워드 추출
    """
    
    def __init__(
        self, 
        ner_model_name: str = "dslim/bert-base-NER",
        keyword_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    ):
        """
        태그 추출 모델 초기화
        
        Args:
            ner_model_name: NER용 Hugging Face 모델 이름
            keyword_model_name: KeyBERT용 모델 이름
        """
        self.ner_model_name = ner_model_name
        self.keyword_model_name = keyword_model_name
        self.ner = None
        self.keyword_model = None
        self.device = 0 if torch.cuda.is_available() else -1
        
        # NER 모델 초기화
        self._init_ner_model()
        
        # KeyBERT 모델 초기화
        self._init_keybert_model()
    
    def _init_ner_model(self):
        """
        NER 모델 초기화 - 호환성 문제 처리
        """
        try:
            # 안전하게 파이프라인 초기화 시도
            try:
                self.ner = pipeline("ner", model=self.ner_model_name, device=self.device)
                logger.info(f"NER 모델 '{self.ner_model_name}' 로드 완료 (pipeline 방식)")
            except Exception as pipeline_error:
                # 파이프라인 초기화 실패 시 직접 모델과 토크나이저 로드 시도
                logger.warning(f"NER Pipeline 초기화 실패, 대체 방법 시도: {str(pipeline_error)}")
                try:
                    tokenizer = AutoTokenizer.from_pretrained(self.ner_model_name)
                    model = AutoModelForTokenClassification.from_pretrained(self.ner_model_name)
                    if torch.cuda.is_available():
                        model = model.to("cuda")
                    
                    # 커스텀 NER 함수 정의
                    def custom_ner(text):
                        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
                        if torch.cuda.is_available():
                            inputs = {k: v.to("cuda") for k, v in inputs.items()}
                        
                        with torch.no_grad():
                            outputs = model(**inputs)
                        
                        # 예측 결과 처리
                        predictions = torch.argmax(outputs.logits, dim=2)
                        tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
                        
                        results = []
                        for i, (token, prediction) in enumerate(zip(tokens, predictions[0].tolist())):
                            if token.startswith("##"):
                                # 이전 토큰에 붙이기
                                if results:
                                    results[-1]["word"] += token.replace("##", "")
                            else:
                                tag_idx = prediction
                                tag = model.config.id2label[tag_idx]
                                if tag != "O":  # O는 개체가 아님
                                    results.append({
                                        "word": token,
                                        "entity": tag,
                                        "score": 0.9,  # 임의의 점수
                                    })
                        
                        return results
                    
                    self.ner = custom_ner
                    logger.info(f"NER 모델 '{self.ner_model_name}' 로드 완료 (직접 로드 방식)")
                except Exception as model_error:
                    logger.error(f"NER 모델 직접 로드 실패: {str(model_error)}")
                    # 더미 NER 함수 생성
                    self.ner = lambda text: []
                    logger.warning("더미 NER 함수로 대체됨")
        except Exception as e:
            logger.error(f"NER 모델 로드 중 오류 발생: {str(e)}")
            # 더미 NER 함수 생성
            self.ner = lambda text: []
            logger.warning("더미 NER 함수로 대체됨")
    
    def _init_keybert_model(self):
        """
        KeyBERT 모델 초기화 - 호환성 문제 처리
        """
        try:
            # KeyBERT 모델 로드 시도
            self.keyword_model = KeyBERT(self.keyword_model_name)
            logger.info(f"KeyBERT 모델 '{self.keyword_model_name}' 로드 완료")
        except Exception as e:
            logger.error(f"KeyBERT 모델 로드 중 오류 발생: {str(e)}")
            # 더미 키워드 추출 함수 생성
            self.keyword_model = None
            logger.warning("키워드 추출 기능이 비활성화됨")
    
    async def extract_tags(self, text: str, max_tags: int = 10) -> List[str]:
        """
        텍스트에서 태그 추출
        
        Args:
            text: 태그를 추출할 텍스트
            max_tags: 추출할 최대 태그 수
            
        Returns:
            추출된 태그 목록
        """
        try:
            # 두 가지 방법으로 태그 추출
            ner_tags = await self._extract_entities(text)
            keyword_tags = await self._extract_keywords(text)
            
            # 태그 결합 및 중복 제거
            all_tags = list(set(ner_tags + keyword_tags))
            
            # 최대 태그 수로 제한
            return all_tags[:max_tags]
        except Exception as e:
            logger.error(f"태그 추출 중 오류 발생: {str(e)}")
            return []
    
    async def _extract_entities(self, text: str) -> List[str]:
        """
        NER을 사용하여 개체명 추출
        
        Args:
            text: 개체명을 추출할 텍스트
            
        Returns:
            추출된 개체명 목록
        """
        try:
            # 텍스트가 너무 길면 앞부분만 사용
            if len(text) > 5000:
                text = text[:5000]
                
            # NER 수행
            entities = self.ner(text)
            
            # 개체 그룹화 및 중복 제거
            grouped_entities = {}
            
            for entity in entities:
                # 낮은 신뢰도 항목 필터링
                if entity['score'] < 0.8:
                    continue
                    
                # 개체 그룹화
                if entity['word'].startswith('##'):
                    # 이전 개체에 병합
                    last_key = list(grouped_entities.keys())[-1] if grouped_entities else None
                    if last_key:
                        grouped_entities[last_key] = grouped_entities[last_key] + entity['word'].replace('##', '')
                else:
                    # 새 개체 추가
                    grouped_entities[entity['word']] = entity['word']
            
            # 중복 제거 및 정리
            unique_entities = list(set(grouped_entities.values()))
            
            # 너무 짧은 개체 필터링 (2글자 미만)
            filtered_entities = [e.strip() for e in unique_entities if len(e.strip()) > 1]
            
            return filtered_entities
        except Exception as e:
            logger.warning(f"개체명 추출 중 오류 발생: {str(e)}")
            return []
    
    async def _extract_keywords(self, text: str) -> List[str]:
        """
        KeyBERT를 사용하여 키워드 추출
        
        Args:
            text: 키워드를 추출할 텍스트
            
        Returns:
            추출된 키워드 목록
        """
        # KeyBERT 모델이 로드되지 않았으면 간단한 키워드 추출 로직 사용
        if self.keyword_model is None:
            logger.warning("KeyBERT 모델이 로드되지 않아 간단한 키워드 추출 로직을 사용합니다.")
            try:
                # 간단한 키워드 추출 대체 로직
                # 일반적인 불용어 목록
                stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
                            'when', 'where', 'how', 'who', 'which', 'this', 'that', 'these', 'those',
                            'then', 'just', 'so', 'than', 'such', 'both', 'through', 'about', 'for',
                            'is', 'of', 'while', 'during', 'to', 'from', 'in', 'on', 'by', 'with'}
                
                # 텍스트가 너무 길면 앞부분만 사용
                if len(text) > 5000:
                    text = text[:5000]
                
                # 단어 분리 및 정제
                words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
                words = [word for word in words if word not in stopwords]
                
                # 단어 빈도 계산
                word_freq = {}
                for word in words:
                    if word in word_freq:
                        word_freq[word] += 1
                    else:
                        word_freq[word] = 1
                
                # 빈도순으로 정렬하여 상위 키워드 추출
                sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
                extracted_keywords = [word for word, _ in sorted_words[:15]]
                
                return extracted_keywords
            except Exception as e:
                logger.warning(f"간단한 키워드 추출 중 오류 발생: {str(e)}")
                return []
        
        # KeyBERT 모델이 있으면 정상적으로 처리
        try:
            # 텍스트가 너무 길면 앞부분만 사용
            if len(text) > 10000:
                text = text[:10000]
                
            # KeyBERT로 키워드 추출
            keywords = self.keyword_model.extract_keywords(
                text, 
                keyphrase_ngram_range=(1, 2),  # 1~2 단어 키워드 추출
                stop_words='english',  # 영어 불용어 제거
                top_n=15  # 상위 15개 키워드 추출
            )
            
            # (키워드, 점수) 튜플에서 키워드만 추출
            extracted_keywords = [keyword for keyword, _ in keywords]
            
            return extracted_keywords
        except Exception as e:
            logger.warning(f"키워드 추출 중 오류 발생: {str(e)}")
            return []
