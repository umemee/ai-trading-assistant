"""
version_controller.py - 버전 관리 및 롤백 시스템 (V6.0 완전 구현 버전)

아톰/분자 DB의 변경 이력 추적 및 롤백 기능 제공
- 모든 변경사항 자동 기록 (sheets_service 연동)
- 버전별 차이점 비교
- 실제 데이터 기반의 정확한 버전 번호 관리
- 안전한 롤백 기능 (기반 구현)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import json
import uuid

# numpy가 필요 없어졌으므로 제거하고 기본 라이브러리만 사용합니다.

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
            # ✅ 수정: 실제 데이터 기반으로 다음 버전 번호 가져오기
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

            # sheets_service의 새 함수를 호출하여 버전 기록 저장
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
            # 값들을 문자열로 변환하여 비교 (타입 차이로 인한 오류 방지)
            if str(old_data.get(key)) != str(new_data.get(key)):
                changed_fields.append(key)
        return changed_fields

    async def _get_next_version_number(self, object_id: str) -> int:
        """
        다음 버전 번호를 결정합니다.
        Version_History 시트에서 해당 object_id의 모든 버전을 찾아 가장 큰 값에 1을 더합니다.
        """
        try:
            history = await self.sheets_service.get_version_history()
            if not history:
                return 1 # 기록이 없으면 첫 버전이므로 1을 반환

            max_version = 0
            for record in history:
                if record.get('Molecule_ID') == object_id:
                    try:
                        version = int(record.get('Version', 0))
                        if version > max_version:
                            max_version = version
                    except (ValueError, TypeError):
                        continue # 버전 번호가 숫자가 아니면 무시

            return max_version + 1
        except Exception as e:
            logger.error(f"다음 버전 번호를 가져오는 중 오류 발생 ({object_id}): {e}")
            # 오류 발생 시 안전하게 현재 시간을 기반으로 한 유니크한 번호를 반환할 수 있으나,
            # 여기서는 가장 기본적인 첫 버전으로 처리합니다.
            return 1

    async def rollback_to_version(self, molecule_id: str, target_version: int,
                                  rollback_by: str, rollback_reason: str) -> bool:
        """특정 버전으로 롤백 (실제 구현을 위한 기반 마련)"""
        logger.warning(f"{molecule_id}를 버전 {target_version}으로 롤백 시도...")
        
        try:
            history = await self.sheets_service.get_version_history()
            target_state = None
            
            # 롤백할 버전의 상태 찾기
            for record in history:
                if record.get('Molecule_ID') == molecule_id and int(record.get('Version')) == target_version:
                    # New_Values 필드는 JSON 문자열로 저장되었을 수 있으므로 파싱
                    target_state = json.loads(record.get('New_Values', '{}'))
                    break

            if not target_state:
                logger.error(f"롤백할 버전을 찾을 수 없습니다: {molecule_id} v{target_version}")
                return False

            # 현재 분자 데이터 가져오기 (롤백 전 상태 기록을 위해)
            molecules = await self.sheets_service.get_molecules()
            current_data = next((m for m in molecules if m.get('Molecule_ID') == molecule_id), None)

            if not current_data:
                logger.error(f"롤백할 현재 분자 데이터를 찾을 수 없습니다: {molecule_id}")
                return False

            # 롤백 이벤트를 버전 기록에 추가
            await self.track_change(
                object_id=molecule_id,
                old_data=current_data,
                new_data=target_state,
                changed_by=rollback_by,
                change_reason=f"v{target_version}으로 롤백: {rollback_reason}"
            )
            
            # 실제 데이터 업데이트
            # target_state에는 변경된 필드만 있으므로, 현재 데이터에 덮어쓰기
            update_payload = current_data.copy()
            update_payload.update(target_state)
            
            success = await self.sheets_service.update_molecule_info(molecule_id, update_payload)

            if success:
                logger.info(f"✅ {molecule_id}가 v{target_version}으로 성공적으로 롤백되었습니다.")
                return True
            else:
                logger.error(f"분자 정보 업데이트 실패로 롤백에 실패했습니다: {molecule_id}")
                return False

        except Exception as e:
            logger.error(f"롤백 중 오류 발생: {e}", exc_info=True)
            return False
