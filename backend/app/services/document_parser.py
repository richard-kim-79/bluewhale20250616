import trafilatura
import pdfplumber
from typing import Dict, Any, Optional, List
import os
import logging

logger = logging.getLogger(__name__)

class DocumentParser:
    """
    다양한 형식의 문서를 파싱하여 텍스트 추출
    지원 형식: PDF, HTML, TXT
    """
    
    @staticmethod
    async def parse_document(file_path: str, file_type: str) -> Optional[str]:
        """
        파일 형식에 맞는 파서를 사용하여 문서 내용 추출
        
        Args:
            file_path: 파일 경로
            file_type: 파일 형식 (pdf, html, txt 등)
            
        Returns:
            추출된 텍스트 내용
        """
        try:
            if file_type.lower() == 'pdf':
                return DocumentParser.parse_pdf(file_path)
            elif file_type.lower() == 'html':
                return DocumentParser.parse_html(file_path)
            elif file_type.lower() == 'txt':
                return DocumentParser.parse_text(file_path)
            else:
                logger.warning(f"지원하지 않는 파일 형식: {file_type}")
                return None
        except Exception as e:
            logger.error(f"문서 파싱 중 오류 발생: {str(e)}")
            return None
    
    @staticmethod
    def parse_pdf(file_path: str) -> str:
        """PDF 파일에서 텍스트 추출"""
        text_content = []
        
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
        
        return "\n\n".join(text_content)
    
    @staticmethod
    def parse_html(file_path: str) -> str:
        """HTML 파일에서 텍스트 추출"""
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # trafilatura를 사용하여 HTML에서 주요 콘텐츠 추출
        extracted_text = trafilatura.extract(html_content)
        
        if extracted_text:
            return extracted_text
        else:
            # 추출 실패 시 기본 HTML 태그 제거
            from html.parser import HTMLParser
            
            class MLStripper(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.reset()
                    self.strict = False
                    self.convert_charrefs = True
                    self.text = []
                
                def handle_data(self, d):
                    self.text.append(d)
                
                def get_data(self):
                    return ''.join(self.text)
            
            stripper = MLStripper()
            stripper.feed(html_content)
            return stripper.get_data()
    
    @staticmethod
    def parse_text(file_path: str) -> str:
        """일반 텍스트 파일에서 텍스트 추출"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @staticmethod
    def extract_metadata(file_path: str, file_type: str) -> Dict[str, Any]:
        """
        파일에서 메타데이터 추출
        
        Args:
            file_path: 파일 경로
            file_type: 파일 형식
            
        Returns:
            메타데이터 딕셔너리
        """
        metadata = {
            "file_size": os.path.getsize(file_path),
            "file_name": os.path.basename(file_path),
            "file_type": file_type,
        }
        
        if file_type.lower() == 'pdf':
            try:
                with pdfplumber.open(file_path) as pdf:
                    metadata["page_count"] = len(pdf.pages)
                    if pdf.metadata:
                        metadata["title"] = pdf.metadata.get('Title')
                        metadata["author"] = pdf.metadata.get('Author')
                        metadata["creation_date"] = pdf.metadata.get('CreationDate')
            except Exception as e:
                logger.error(f"PDF 메타데이터 추출 중 오류: {str(e)}")
        
        return metadata
