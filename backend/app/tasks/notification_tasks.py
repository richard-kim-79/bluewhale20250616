import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.notification_tasks.send_notification")
def send_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    사용자에게 알림 전송
    
    Args:
        user_id: 수신자 사용자 ID
        notification_type: 알림 유형 (예: 'like', 'comment', 'mention', 'follow')
        title: 알림 제목
        message: 알림 내용
        data: 추가 데이터
        
    Returns:
        전송 결과
    """
    try:
        logger.info(f"알림 전송: {user_id} ({notification_type})")
        
        # 실제 구현에서는 데이터베이스에 알림 저장 및 웹소켓 등으로 전송
        # 여기서는 성공 응답만 반환
        
        notification_id = f"notif_{datetime.now().timestamp()}"
        
        return {
            "notification_id": notification_id,
            "user_id": user_id,
            "status": "success",
            "sent_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"알림 전송 중 오류 발생: {str(e)}")
        
        return {
            "user_id": user_id,
            "status": "error",
            "error": str(e)
        }

@celery_app.task(name="app.tasks.notification_tasks.send_batch_notifications")
def send_batch_notifications(
    user_ids: List[str],
    notification_type: str,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    여러 사용자에게 일괄 알림 전송
    
    Args:
        user_ids: 수신자 사용자 ID 목록
        notification_type: 알림 유형
        title: 알림 제목
        message: 알림 내용
        data: 추가 데이터
        
    Returns:
        전송 결과
    """
    try:
        logger.info(f"일괄 알림 전송: {len(user_ids)}명 ({notification_type})")
        
        # 각 사용자에게 개별 알림 전송
        results = []
        for user_id in user_ids:
            result = send_notification(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                data=data
            )
            results.append(result)
        
        # 성공 및 실패 수 집계
        success_count = sum(1 for r in results if r.get("status") == "success")
        
        return {
            "status": "success",
            "total": len(user_ids),
            "success_count": success_count,
            "failure_count": len(user_ids) - success_count,
            "sent_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"일괄 알림 전송 중 오류 발생: {str(e)}")
        
        return {
            "status": "error",
            "error": str(e)
        }

@celery_app.task(name="app.tasks.notification_tasks.send_document_recommendation")
def send_document_recommendation(
    user_id: str,
    document_id: str,
    document_title: str,
    similarity_score: float,
    reason: str = "관심 있을 만한 문서"
) -> Dict[str, Any]:
    """
    사용자에게 문서 추천 알림 전송
    
    Args:
        user_id: 수신자 사용자 ID
        document_id: 추천 문서 ID
        document_title: 추천 문서 제목
        similarity_score: 유사도 점수
        reason: 추천 이유
        
    Returns:
        전송 결과
    """
    try:
        logger.info(f"문서 추천 알림: {user_id} (문서: {document_id})")
        
        # 알림 메시지 구성
        title = "문서 추천"
        message = f"'{document_title}' - {reason}"
        
        # 추가 데이터
        data = {
            "document_id": document_id,
            "document_title": document_title,
            "similarity_score": similarity_score,
            "reason": reason
        }
        
        # 알림 전송
        return send_notification(
            user_id=user_id,
            notification_type="document_recommendation",
            title=title,
            message=message,
            data=data
        )
    
    except Exception as e:
        logger.error(f"문서 추천 알림 전송 중 오류 발생: {str(e)}")
        
        return {
            "user_id": user_id,
            "document_id": document_id,
            "status": "error",
            "error": str(e)
        }

@celery_app.task(name="app.tasks.notification_tasks.send_friend_recommendation")
def send_friend_recommendation(
    user_id: str,
    recommended_user_id: str,
    recommended_user_name: str,
    similarity_score: float,
    common_interests: List[str] = []
) -> Dict[str, Any]:
    """
    사용자에게 친구 추천 알림 전송
    
    Args:
        user_id: 수신자 사용자 ID
        recommended_user_id: 추천 사용자 ID
        recommended_user_name: 추천 사용자 이름
        similarity_score: 유사도 점수
        common_interests: 공통 관심사
        
    Returns:
        전송 결과
    """
    try:
        logger.info(f"친구 추천 알림: {user_id} (추천: {recommended_user_id})")
        
        # 알림 메시지 구성
        title = "친구 추천"
        
        if common_interests:
            interests_text = ", ".join(common_interests[:3])
            if len(common_interests) > 3:
                interests_text += f" 외 {len(common_interests) - 3}개"
            message = f"{recommended_user_name}님과 공통 관심사: {interests_text}"
        else:
            message = f"{recommended_user_name}님이 관심 있을 만한 사용자입니다."
        
        # 추가 데이터
        data = {
            "recommended_user_id": recommended_user_id,
            "recommended_user_name": recommended_user_name,
            "similarity_score": similarity_score,
            "common_interests": common_interests
        }
        
        # 알림 전송
        return send_notification(
            user_id=user_id,
            notification_type="friend_recommendation",
            title=title,
            message=message,
            data=data
        )
    
    except Exception as e:
        logger.error(f"친구 추천 알림 전송 중 오류 발생: {str(e)}")
        
        return {
            "user_id": user_id,
            "recommended_user_id": recommended_user_id,
            "status": "error",
            "error": str(e)
        }
