"""
approval_manager.py - 승인 관리 시스템

검역된 분자들의 승인/거부 처리 및 상태 관리
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import json
import uuid

from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)

class ApprovalManager:
    """승인 관리 시스템"""
    
    def __init__(self, sheets_service: SheetsService):
        self.sheets_service = sheets_service
        logger.info("ApprovalManager 초기화 완료")

    async def get_quarantine_queue(self) -> List[Dict]:
        """검토가 필요한(ready_for_review) 분자 목록 조회"""
        molecules = await self.sheets_service.get_molecules()
        # WFO 테스트가 끝나고 검토 대기 중인 항목만 필터링
        return [m for m in molecules if m.get("Status", "").lower() == "ready_for_review"]

    async def approve_molecule(self, molecule_id: str, approver: str, 
                             approval_notes: str = '') -> bool:
        """분자 승인 처리"""
        logger.info(f"분자 승인 프로세스 시작: {molecule_id} by {approver}")
        
        # ✅ 1단계 수정: sheets_service의 업데이트 함수 호출
        update_payload = {
            "Status": "active",
            "Approved_Date": datetime.now(timezone.utc).isoformat(),
            "Approved_By": approver
        }
        success = await self.sheets_service.update_molecule_info(molecule_id, update_payload)

        if success:
            # ✅ 1단계 수정: sheets_service의 로그 함수 호출
            log_payload = {
                "Log_ID": str(uuid.uuid4()),
                "Molecule_ID": molecule_id,
                "Action": "APPROVED",
                "Reviewer": approver,
                "Review_Notes": approval_notes,
                "Previous_Status": "ready_for_review",
                "New_Status": "active"
            }
            await self.sheets_service.log_approval_action(log_payload)
            logger.info(f"분자 승인 완료 및 로그 기록: {molecule_id}")
            return True
        else:
            logger.error(f"분자 승인 실패 (DB 업데이트 오류): {molecule_id}")
            return False

    async def reject_molecule(self, molecule_id: str, reviewer: str, 
                            rejection_reason: str) -> bool:
        """분자 거부 처리"""
        if not rejection_reason:
            logger.warning("거부 시에는 반드시 사유를 입력해야 합니다.")
            return False
            
        logger.info(f"분자 거부 프로세스 시작: {molecule_id} by {reviewer}")

        # ✅ 1단계 수정: sheets_service의 업데이트 함수 호출
        update_payload = {
            "Status": "deprecated", # 거부된 전략은 비활성화 처리
            "Approved_Date": datetime.now(timezone.utc).isoformat(),
            "Approved_By": reviewer # 거부자 정보 기록
        }
        success = await self.sheets_service.update_molecule_info(molecule_id, update_payload)

        if success:
            # ✅ 1단계 수정: sheets_service의 로그 함수 호출
            log_payload = {
                "Log_ID": str(uuid.uuid4()),
                "Molecule_ID": molecule_id,
                "Action": "REJECTED",
                "Reviewer": reviewer,
                "Review_Notes": rejection_reason,
                "Previous_Status": "ready_for_review",
                "New_Status": "deprecated"
            }
            await self.sheets_service.log_approval_action(log_payload)
            logger.info(f"분자 거부 완료 및 로그 기록: {molecule_id}")
            return True
        else:
            logger.error(f"분자 거부 실패 (DB 업데이트 오류): {molecule_id}")
            return False
