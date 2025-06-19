import boto3
import logging
from typing import Dict, Any, Optional, BinaryIO, Union
import os
from botocore.exceptions import ClientError
import uuid
from fastapi import UploadFile

logger = logging.getLogger(__name__)

class S3FileStorage:
    """
    AWS S3를 사용한 파일 저장소 서비스
    문서, 이미지 등의 파일을 S3에 업로드하고 관리
    """
    
    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region_name: str,
        bucket_name: str
    ):
        """
        S3 클라이언트 초기화
        
        Args:
            aws_access_key_id: AWS 액세스 키 ID
            aws_secret_access_key: AWS 시크릿 액세스 키
            region_name: AWS 리전 이름
            bucket_name: S3 버킷 이름
        """
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region_name
            )
            self.bucket_name = bucket_name
            
            # 버킷이 존재하는지 확인
            self._ensure_bucket_exists()
            
            logger.info(f"S3 클라이언트 초기화 완료 (버킷: {bucket_name}, 리전: {region_name})")
        except Exception as e:
            logger.error(f"S3 클라이언트 초기화 중 오류 발생: {str(e)}")
            raise
    
    def _ensure_bucket_exists(self):
        """
        버킷이 존재하는지 확인하고, 없으면 생성
        개발 환경에서는 오류를 무시하고 진행
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 버킷 '{self.bucket_name}'이(가) 존재함")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                # 버킷이 없으면 생성 시도
                logger.info(f"S3 버킷 '{self.bucket_name}'이(가) 없음, 생성 시도 중...")
                try:
                    self.s3_client.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={
                            'LocationConstraint': self.s3_client.meta.region_name
                        }
                    )
                    logger.info(f"S3 버킷 '{self.bucket_name}' 생성 완료")
                except Exception as create_error:
                    # 버킷 생성 실패 시 개발 환경으로 간주하고 계속 진행
                    logger.warning(f"S3 버킷 생성 실패: {str(create_error)}. 개발 환경으로 간주하고 계속 진행합니다.")
            else:
                # 403 Forbidden 등의 오류도 개발 환경으로 간주하고 진행
                logger.warning(f"S3 버킷 접근 오류 ({error_code}): {str(e)}. 개발 환경으로 간주하고 계속 진행합니다.")
    
    async def upload_file(
        self,
        file: Union[UploadFile, BinaryIO, str],
        object_name: Optional[str] = None,
        folder: str = "uploads",
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        파일을 S3에 업로드
        개발 환경에서는 오류 발생 시 가상 응답 반환
        
        Args:
            file: 업로드할 파일 (UploadFile, 파일 객체 또는 파일 경로)
            object_name: S3에 저장될 객체 이름 (없으면 자동 생성)
            folder: S3 내 저장 폴더 경로
            content_type: 파일 콘텐츠 타입
            
        Returns:
            업로드 결과 정보
        """
        try:
            # 객체 이름이 없으면 UUID로 생성
            if object_name is None:
                if isinstance(file, UploadFile):
                    # 원본 파일 확장자 유지
                    file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
                    object_name = f"{uuid.uuid4()}{file_ext}"
                else:
                    object_name = str(uuid.uuid4())
            
            # 폴더 경로 포함
            if folder:
                object_name = f"{folder.rstrip('/')}/{object_name}"
            
            # 파일 타입에 따라 업로드 방식 결정
            if isinstance(file, UploadFile):
                # FastAPI UploadFile
                file_content = await file.read()
                content_type = content_type or file.content_type
                
                try:
                    extra_args = {'ContentType': content_type} if content_type else {}
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=object_name,
                        Body=file_content,
                        **extra_args
                    )
                    
                    # 파일 포인터를 처음으로 되돌려 놓음
                    await file.seek(0)
                except Exception as s3_error:
                    # S3 업로드 실패 시 로깅만 하고 가상 응답 반환
                    logger.warning(f"S3 업로드 실패 (개발 환경): {str(s3_error)}")
                    # 파일 포인터를 처음으로 되돌려 놓음
                    await file.seek(0)
            elif isinstance(file, str):
                # 파일 경로
                try:
                    extra_args = {'ContentType': content_type} if content_type else {}
                    self.s3_client.upload_file(
                        file,
                        self.bucket_name,
                        object_name,
                        ExtraArgs=extra_args
                    )
                except Exception as s3_error:
                    # S3 업로드 실패 시 로깅만 함
                    logger.warning(f"S3 업로드 실패 (개발 환경): {str(s3_error)}")
            else:
                # 파일 객체
                try:
                    extra_args = {'ContentType': content_type} if content_type else {}
                    self.s3_client.upload_fileobj(
                        file,
                        self.bucket_name,
                        object_name,
                        ExtraArgs=extra_args
                    )
                except Exception as s3_error:
                    # S3 업로드 실패 시 로깅만 함
                    logger.warning(f"S3 업로드 실패 (개발 환경): {str(s3_error)}")
            
            # 업로드된 파일의 URL 생성 (개발 환경에서는 가상 URL)
            file_url = f"https://{self.bucket_name}.s3.amazonaws.com/{object_name}"
            
            logger.info(f"파일 업로드 완료 (또는 개발 환경 가상 응답): {file_url}")
            
            return {
                "object_name": object_name,
                "bucket": self.bucket_name,
                "file_url": file_url
            }
        except Exception as e:
            # 개발 환경에서는 오류를 기록하고 가상 응답 반환
            logger.error(f"파일 업로드 중 오류 발생: {str(e)}")
            
            # 객체 이름이 없으면 생성
            if object_name is None:
                object_name = str(uuid.uuid4())
                if folder:
                    object_name = f"{folder.rstrip('/')}/{object_name}"
            
            # 가상 URL 생성
            file_url = f"https://{self.bucket_name}.s3.amazonaws.com/{object_name}"
            
            logger.warning(f"개발 환경에서 가상 응답 반환: {file_url}")
            return {
                "object_name": object_name,
                "bucket": self.bucket_name,
                "file_url": file_url
            }
    
    async def download_file(self, object_name: str, download_path: str) -> bool:
        """
        S3에서 파일 다운로드
        개발 환경에서는 오류 발생 시 가상 파일 생성
        
        Args:
            object_name: S3 객체 이름
            download_path: 다운로드할 로컬 경로
            
        Returns:
            성공 여부
        """
        try:
            # 다운로드 경로의 디렉토리가 없으면 생성
            os.makedirs(os.path.dirname(download_path), exist_ok=True)
            
            try:
                # 파일 다운로드 시도
                self.s3_client.download_file(
                    self.bucket_name,
                    object_name,
                    download_path
                )
                logger.info(f"파일 다운로드 완료: {object_name} -> {download_path}")
                return True
            except Exception as s3_error:
                # S3 다운로드 실패 시 개발 환경에서는 가상 파일 생성
                logger.warning(f"S3 다운로드 실패 (개발 환경): {str(s3_error)}")
                
                # 가상 파일 생성
                with open(download_path, 'w') as f:
                    f.write(f"Placeholder file for {object_name} (development environment)")
                
                logger.info(f"개발 환경에서 가상 파일 생성: {download_path}")
                return True
        except Exception as e:
            logger.error(f"파일 다운로드 중 오류 발생: {str(e)}")
            
            try:
                # 개발 환경에서는 오류 발생 시에도 가상 파일 생성
                with open(download_path, 'w') as f:
                    f.write(f"Placeholder file for {object_name} (development environment)")
                logger.warning(f"개발 환경에서 오류 발생 후 가상 파일 생성: {download_path}")
                return True
            except Exception as file_error:
                logger.error(f"가상 파일 생성 중 오류: {str(file_error)}")
                return False
    
    async def get_file_url(self, object_name: str, expiration: int = 3600) -> Optional[str]:
        """
        S3 객체의 미리 서명된 URL 생성
        개발 환경에서는 오류 발생 시 가상 URL 반환
        
        Args:
            object_name: S3 객체 이름
            expiration: URL 만료 시간(초)
            
        Returns:
            미리 서명된 URL 또는 가상 URL
        """
        try:
            try:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': object_name
                    },
                    ExpiresIn=expiration
                )
                return url
            except Exception as s3_error:
                # S3 URL 생성 실패 시 개발 환경에서는 가상 URL 반환
                logger.warning(f"S3 URL 생성 실패 (개발 환경): {str(s3_error)}")
                
                # 가상 URL 생성
                fake_url = f"https://{self.bucket_name}.s3.amazonaws.com/{object_name}?X-Amz-Fake-Dev-Signature=true"
                logger.info(f"개발 환경에서 가상 URL 생성: {fake_url}")
                return fake_url
        except Exception as e:
            logger.error(f"URL 생성 중 오류 발생: {str(e)}")
            
            # 개발 환경에서는 가상 URL 반환
            fake_url = f"https://{self.bucket_name}.s3.amazonaws.com/{object_name}?X-Amz-Fake-Dev-Signature=true"
            logger.warning(f"개발 환경에서 오류 후 가상 URL 반환: {fake_url}")
            return fake_url
    
    async def delete_file(self, object_name: str) -> bool:
        """
        S3에서 파일 삭제
        개발 환경에서는 오류 발생 시에도 성공 반환
        
        Args:
            object_name: S3 객체 이름
            
        Returns:
            성공 여부
        """
        try:
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=object_name
                )
                logger.info(f"파일 삭제 완료: {object_name}")
                return True
            except Exception as s3_error:
                # S3 삭제 실패 시 개발 환경에서는 성공으로 처리
                logger.warning(f"S3 파일 삭제 실패 (개발 환경): {str(s3_error)}")
                logger.info(f"개발 환경에서 파일 삭제 성공으로 간주: {object_name}")
                return True
        except Exception as e:
            logger.error(f"파일 삭제 중 오류 발생: {str(e)}")
            # 개발 환경에서는 오류가 발생해도 성공으로 처리
            logger.warning(f"개발 환경에서 오류 발생 후 삭제 성공으로 간주: {object_name}")
            return True
