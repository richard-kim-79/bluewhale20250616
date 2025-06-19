from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import logging
from typing import List, Dict, Any, Optional
import torch

logger = logging.getLogger(__name__)

class DocumentSummarizer:
    """
    문서 요약 서비스
    Hugging Face의 transformers 라이브러리를 사용하여 문서 요약 수행
    """
    
    def __init__(self, model_name: str = "facebook/bart-large-cnn"):
        """
        요약 모델 초기화
        
        Args:
            model_name: Hugging Face 모델 이름
        """
        self.model_name = model_name
        self.summarizer = None
        
        try:
            # GPU 사용 가능 여부 확인
            device = 0 if torch.cuda.is_available() else -1
            
            # 안전하게 파이프라인 초기화 시도
            try:
                self.summarizer = pipeline("summarization", model=model_name, device=device)
                logger.info(f"요약 모델 '{model_name}' 로드 완료 (pipeline 방식)")
            except Exception as pipeline_error:
                # 파이프라인 초기화 실패 시 직접 모델과 토크나이저 로드 시도
                logger.warning(f"Pipeline 초기화 실패, 대체 방법 시도: {str(pipeline_error)}")
                try:
                    tokenizer = AutoTokenizer.from_pretrained(model_name)
                    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
                    if torch.cuda.is_available():
                        model = model.to("cuda")
                    
                    # 커스텀 summarizer 함수 정의
                    def custom_summarize(text, max_length=150, min_length=40, do_sample=False):
                        inputs = tokenizer(text, return_tensors="pt", max_length=1024, truncation=True)
                        if torch.cuda.is_available():
                            inputs = {k: v.to("cuda") for k, v in inputs.items()}
                        
                        summary_ids = model.generate(
                            inputs["input_ids"], 
                            max_length=max_length, 
                            min_length=min_length,
                            do_sample=do_sample
                        )
                        
                        summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
                        return [{"summary_text": summary}]
                    
                    self.summarizer = custom_summarize
                    logger.info(f"요약 모델 '{model_name}' 로드 완료 (직접 로드 방식)")
                except Exception as model_error:
                    logger.error(f"모델 직접 로드 실패: {str(model_error)}")
                    # 더미 요약기 생성
                    self.summarizer = lambda text, **kwargs: [{"summary_text": text[:150] + "... (요약 불가)"}]
                    logger.warning("더미 요약기로 대체됨")
        except Exception as e:
            logger.error(f"요약 모델 로드 중 오류 발생: {str(e)}")
            # 더미 요약기 생성
            self.summarizer = lambda text, **kwargs: [{"summary_text": text[:150] + "... (요약 불가)"}]
            logger.warning("더미 요약기로 대체됨")
    
    async def summarize(self, text: str, max_length: int = 150, min_length: int = 40) -> str:
        """
        텍스트 요약 수행
        
        Args:
            text: 요약할 텍스트
            max_length: 요약문의 최대 길이
            min_length: 요약문의 최소 길이
            
        Returns:
            요약된 텍스트
        """
        try:
            # 텍스트가 너무 길면 청크로 나누어 요약
            if len(text) > 1024:
                return await self._summarize_long_text(text, max_length, min_length)
            
            # 일반적인 요약 수행
            summary = self.summarizer(text, max_length=max_length, min_length=min_length, do_sample=False)
            return summary[0]['summary_text']
        except Exception as e:
            logger.error(f"텍스트 요약 중 오류 발생: {str(e)}")
            # 오류 발생 시 원본 텍스트의 일부를 반환
            return text[:max_length] + "... (요약 실패)"
    
    async def _summarize_long_text(self, text: str, max_length: int = 150, min_length: int = 40) -> str:
        """
        긴 텍스트를 여러 청크로 나누어 요약
        
        Args:
            text: 요약할 긴 텍스트
            max_length: 최종 요약문의 최대 길이
            min_length: 최종 요약문의 최소 길이
            
        Returns:
            요약된 텍스트
        """
        # 텍스트를 단락으로 분할
        paragraphs = text.split("\n\n")
        
        # 각 단락을 요약
        chunk_size = 5  # 한 번에 처리할 단락 수
        summaries = []
        
        for i in range(0, len(paragraphs), chunk_size):
            chunk = "\n".join(paragraphs[i:i+chunk_size])
            if len(chunk) > 100:  # 너무 짧은 청크는 요약하지 않음
                try:
                    chunk_summary = self.summarizer(
                        chunk, 
                        max_length=max(30, max_length // 2), 
                        min_length=min(20, min_length // 2),
                        do_sample=False
                    )
                    summaries.append(chunk_summary[0]['summary_text'])
                except Exception as e:
                    logger.warning(f"청크 요약 중 오류 발생: {str(e)}")
                    # 오류 발생 시 원본 청크의 일부를 사용
                    summaries.append(chunk[:100] + "...")
            elif len(chunk) > 0:
                summaries.append(chunk)
        
        # 모든 청크 요약을 결합하여 최종 요약 생성
        combined_summary = " ".join(summaries)
        
        # 최종 요약이 너무 길면 다시 요약
        if len(combined_summary) > max_length * 2:
            try:
                final_summary = self.summarizer(
                    combined_summary,
                    max_length=max_length,
                    min_length=min_length,
                    do_sample=False
                )
                return final_summary[0]['summary_text']
            except Exception as e:
                logger.error(f"최종 요약 중 오류 발생: {str(e)}")
                return combined_summary[:max_length] + "..."
        
        return combined_summary
