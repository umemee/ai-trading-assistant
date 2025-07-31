"""
version_controller.py - 버전 관리 및 롤백 시스템

아톰/분자 DB의 변경 이력 추적 및 롤백 기능 제공
- 모든 변경사항 자동 기록
- 버전별 차이점 비교
- 안전한 롤백 기능
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import json
import hashlib
from dataclasses import dataclass, asdict
import uuid

from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)

@dataclass
class VersionRecord:
    """버전 기록 데이터 클래스"""
    History_ID: str
    Molecule_ID: str
    Version: int
    Changed_Fields: List[str]
    Old_Values: Dict[str, Any]
    New_Values: Dict[str, Any]
    Changed_By: str
    Changed_Date: str
    Change_Reason: str

class VersionController:
    """버전 관리 시스템"""
    
    def __init__(self, sheets_service: SheetsService):
        self.sheets_service = sheets_service
        logger.info("VersionController 초기화 완료")

    async def track_change(self, object_id: str, old_data: Dict, new_data: Dict, 
                           changed_by: str, change_reason: str = '') -> Optional[str]:
        """분자 또는 아톰의 변경 사항을 추적하고 기록"""
        
        changed_fields = self._identify_changed_fields(old_data, new_data)
        if not changed_fields:
            logger.info(f"추적할 변경 사항 없음: {object_id}")
            return None

        try:
            # 다음 버전 번호 가져오기 (시뮬레이션)
            next_version = await self._get_next_version_number(object_id)

            version_record = VersionRecord(
                History_ID=str(uuid.uuid4()),
                Molecule_ID=object_id,
                Version=next_version,
                Changed_Fields=changed_fields,
                Old_Values={k: old_data.get(k) for k in changed_fields},
                New_Values={k: new_data.get(k) for k in changed_fields},
                Changed_By=changed_by,
                Changed_Date=datetime.now(timezone.utc).isoformat(),
                Change_Reason=change_reason
            )

            # ✅ 1단계 수정: sheets_service의 새 함수 호출
            success = await self.sheets_service.save_version_record(asdict(version_record))
            
            if success:
                logger.info(f"버전 기록 성공: {object_id} (v{next_version})")
                return version_record.History_ID
            else:
                logger.error(f"버전 기록 실패: {object_id}")
                return None

        except Exception as e:
            logger.error(f"변경 사항 추적 실패 ({object_id}): {e}", exc_info=True)
            return None

    def _identify_changed_fields(self, old_data: Dict, new_data: Dict) -> List[str]:
        """두 딕셔너리를 비교하여 변경된 필드 목록 반환"""
        all_keys = set(old_data.keys()) | set(new_data.keys())
        changed_fields = []
        for key in all_keys:
            if old_data.get(key) != new_data.get(key):
                changed_fields.append(key)
        return changed_fields

    async def _get_next_version_number(self, object_id: str) -> int:
        """다음 버전 번호를 결정 (실제로는 Version_History 시트 조회 필요)"""
        # 현재는 시뮬레이션으로, 항상 1을 더한 값을 반환하는 것처럼 동작
        # TODO: 실제 구현 시에는 Version_History 시트에서 해당 object_id의 최대 버전을 찾아 +1 해야 함
        return np.random.randint(1, 100) # 임시 버전 번호

    async def rollback_to_version(self, molecule_id: str, target_version: int, 
                                  rollback_by: str, rollback_reason: str) -> bool:
        """특정 버전으로 롤백 (시뮬레이션)"""
        logger.warning("롤백 기능은 아직 완전히 구현되지 않았습니다.")
        # 1. Version_History 시트에서 target_version의 New_Values 조회
        # 2. 현재 분자 데이터 가져오기
        # 3. 변경사항 추적 (track_change 호출)
        # 4. sheets_service.update_molecule_info를 사용하여 데이터 복원
        
        # 롤백 이벤트 기록
        await self.track_change(
            object_id=molecule_id,
            old_data={"status": "active"}, # 예시
            new_data={"status": "rolled_back"}, # 예시
            changed_by=rollback_by,
            change_reason=f"롤백 to v{target_version}: {rollback_reason}"
        )
        return True
