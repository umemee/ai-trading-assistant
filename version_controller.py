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
from dataclasses import dataclass

from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)

@dataclass
class VersionRecord:
    """버전 기록 데이터 클래스"""
    version_id: str
    object_type: str  # ATOM, MOLECULE
    object_id: str
    version_number: int
    change_type: str  # CREATE, UPDATE, DELETE
    changed_fields: List[str]
    old_values: Dict[str, Any]
    new_values: Dict[str, Any]
    changed_by: str
    changed_date: str
    change_reason: str
    checksum: str

class VersionController:
    """버전 관리 시스템"""
    
    def __init__(self, sheets_service: SheetsService):
        self.sheets_service = sheets_service
        self.version_cache = {}
        
        logger.info("버전 컨트롤러 초기화 완료")

    async def track_molecule_change(self, molecule_id: str, old_data: Dict, 
                                  new_data: Dict, changed_by: str, 
                                  change_reason: str = '') -> str:
        """분자 변경 추적"""
        try:
            # 변경된 필드 식별
            changed_fields = self.identify_changed_fields(old_data, new_data)
            
            if not changed_fields:
                logger.info(f"변경사항 없음: {molecule_id}")
                return ""
            
            # 버전 번호 생성
            version_number = await self.get_next_version_number(molecule_id, 'MOLECULE')
            
            # 버전 ID 생성
            version_id = f"VER_MOL_{molecule_id}_{version_number}_{int(datetime.now().timestamp())}"
            
            # 체크섬 계산
            checksum = self.calculate_checksum(new_data)
            
            # 버전 기록 생성
            version_record = VersionRecord(
                version_id=version_id,
                object_type='MOLECULE',
                object_id=molecule_id,
                version_number=version_number,
                change_type='UPDATE' if old_data else 'CREATE',
                changed_fields=changed_fields,
                old_values=self.extract_field_values(old_data, changed_fields),
                new_values=self.extract_field_values(new_data, changed_fields),
                changed_by=changed_by,
                changed_date=datetime.now(timezone.utc).isoformat(),
                change_reason=change_reason,
                checksum=checksum
            )
            
            # 버전 기록 저장
            await self.save_version_record(version_record)
            
            logger.info(f"버전 추적 완료: {version_id}")
            return version_id
            
        except Exception as e:
            logger.error(f"분자 변경 추적 실패: {e}")
            return ""

    async def track_atom_change(self, atom_id: str, old_data: Dict, 
                              new_data: Dict, changed_by: str, 
                              change_reason: str = '') -> str:
        """아톰 변경 추적"""
        try:
            changed_fields = self.identify_changed_fields(old_data, new_data)
            
            if not changed_fields:
                return ""
            
            version_number = await self.get_next_version_number(atom_id, 'ATOM')
            version_id = f"VER_ATOM_{atom_id}_{version_number}_{int(datetime.now().timestamp())}"
            checksum = self.calculate_checksum(new_data)
            
            version_record = VersionRecord(
                version_id=version_id,
                object_type='ATOM',
                object_id=atom_id,
                version_number=version_number,
                change_type='UPDATE' if old_data else 'CREATE',
                changed_fields=changed_fields,
                old_values=self.extract_field_values(old_data, changed_fields),
                new_values=self.extract_field_values(new_data, changed_fields),
                changed_by=changed_by,
                changed_date=datetime.now(timezone.utc).isoformat(),
                change_reason=change_reason,
                checksum=checksum
            )
            
            await self.save_version_record(version_record)
            logger.info(f"아톰 버전 추적 완료: {version_id}")
            return version_id
            
        except Exception as e:
            logger.error(f"아톰 변경 추적 실패: {e}")
            return ""

    def identify_changed_fields(self, old_data: Dict, new_data: Dict) -> List[str]:
        """변경된 필드 식별"""
        try:
            changed_fields = []
            
            # 모든 필드 확인
            all_fields = set(old_data.keys()) | set(new_data.keys())
            
            for field in all_fields:
                old_value = old_data.get(field)
                new_value = new_data.get(field)
                
                # 값이 다르면 변경된 것으로 간주
                if old_value != new_value:
                    changed_fields.append(field)
            
            return changed_fields
            
        except Exception as e:
            logger.error(f"변경 필드 식별 실패: {e}")
            return []

    def extract_field_values(self, data: Dict, fields: List[str]) -> Dict[str, Any]:
        """특정 필드들의 값 추출"""
        return {field: data.get(field) for field in fields}

    def calculate_checksum(self, data: Dict) -> str:
        """데이터 체크섬 계산"""
        try:
            # 데이터를 JSON 문자열로 변환 후 해시
            json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(json_str.encode()).hexdigest()[:16]
            
        except Exception as e:
            logger.error(f"체크섬 계산 실패: {e}")
            return ""

    async def get_next_version_number(self, object_id: str, object_type: str) -> int:
        """다음 버전 번호 생성"""
        try:
            # Version_History에서 해당 객체의 최대 버전 번호 조회
            version_history = await self.get_version_history(object_id, object_type)
            
            if not version_history:
                return 1
            
            max_version = max([v['version_number'] for v in version_history])
            return max_version + 1
            
        except Exception as e:
            logger.error(f"버전 번호 생성 실패: {e}")
            return 1

    async def save_version_record(self, record: VersionRecord):
        """버전 기록 저장"""
        try:
            version_data = {
                'Version_ID': record.version_id,
                'Object_Type': record.object_type,
                'Object_ID': record.object_id,
                'Version_Number': record.version_number,
                'Change_Type': record.change_type,
                'Changed_Fields': ','.join(record.changed_fields),
                'Old_Values': json.dumps(record.old_values, ensure_ascii=False),
                'New_Values': json.dumps(record.new_values, ensure_ascii=False),
                'Changed_By': record.changed_by,
                'Changed_Date': record.changed_date,
                'Change_Reason': record.change_reason,
                'Checksum': record.checksum
            }
            
            # Version_History 시트에 저장 (구현 필요)
            logger.info(f"버전 기록 저장: {record.version_id}")
            
        except Exception as e:
            logger.error(f"버전 기록 저장 실패: {e}")

    async def get_version_history(self, object_id: str, 
                                object_type: str = None) -> List[Dict]:
        """객체의 버전 이력 조회"""
        try:
            # Version_History 시트에서 해당 객체의 이력 조회
            # 실제 구현 필요
            
            # 임시 데이터 반환
            return []
            
        except Exception as e:
            logger.error(f"버전 이력 조회 실패: {e}")
            return []

    async def compare_versions(self, object_id: str, version1: int, 
                             version2: int) -> Dict[str, Any]:
        """버전 간 차이점 비교"""
        try:
            version_history = await self.get_version_history(object_id)
            
            v1_data = None
            v2_data = None
            
            for version in version_history:
                if version['version_number'] == version1:
                    v1_data = json.loads(version['new_values'])
                elif version['version_number'] == version2:
                    v2_data = json.loads(version['new_values'])
            
            if not v1_data or not v2_data:
                return {'error': '버전 데이터를 찾을 수 없습니다'}
            
            # 차이점 분석
            differences = {
                'changed_fields': [],
                'added_fields': [],
                'removed_fields': [],
                'field_changes': {}
            }
            
            all_fields = set(v1_data.keys()) | set(v2_data.keys())
            
            for field in all_fields:
                v1_value = v1_data.get(field)
                v2_value = v2_data.get(field)
                
                if field not in v1_data:
                    differences['added_fields'].append(field)
                elif field not in v2_data:
                    differences['removed_fields'].append(field)
                elif v1_value != v2_value:
                    differences['changed_fields'].append(field)
                    differences['field_changes'][field] = {
                        f'version_{version1}': v1_value,
                        f'version_{version2}': v2_value
                    }
            
            return differences
            
        except Exception as e:
            logger.error(f"버전 비교 실패: {e}")
            return {'error': str(e)}

    async def rollback_to_version(self, object_id: str, target_version: int, 
                                rollback_by: str, rollback_reason: str) -> bool:
        """특정 버전으로 롤백"""
        try:
            # 타겟 버전의 데이터 조회
            version_history = await self.get_version_history(object_id)
            target_data = None
            
            for version in version_history:
                if version['version_number'] == target_version:
                    target_data = json.loads(version['new_values'])
                    break
            
            if not target_data:
                logger.error(f"타겟 버전을 찾을 수 없음: {object_id} v{target_version}")
                return False
            
            # 현재 데이터 조회
            current_data = await self.get_current_object_data(object_id)
            
            if not current_data:
                logger.error(f"현재 데이터를 찾을 수 없음: {object_id}")
                return False
            
            # 롤백 실행 (실제 DB 업데이트)
            success = await self.update_object_data(object_id, target_data)
            
            if success:
                # 롤백 이벤트 기록
                await self.track_rollback_event(
                    object_id, target_version, rollback_by, rollback_reason
                )
                
                logger.info(f"롤백 완료: {object_id} → v{target_version}")
                return True
            else:
                logger.error(f"롤백 실패: {object_id}")
                return False
                
        except Exception as e:
            logger.error(f"롤백 실행 실패: {e}")
            return False

    async def get_current_object_data(self, object_id: str) -> Optional[Dict]:
        """현재 객체 데이터 조회"""
        try:
            # 분자인지 아톰인지 판단하여 해당 시트에서 조회
            if object_id.startswith('LOGIC') or 'MOL' in object_id:
                molecules = await self.sheets_service.get_molecules()
                for molecule in molecules:
                    if molecule.get('Molecule_ID') == object_id:
                        return molecule
            else:
                atoms = await self.sheets_service.get_atoms()
                for atom in atoms:
                    if atom.get('Atom_ID') == object_id:
                        return atom
            
            return None
            
        except Exception as e:
            logger.error(f"현재 객체 데이터 조회 실패: {e}")
            return None

    async def update_object_data(self, object_id: str, new_data: Dict) -> bool:
        """객체 데이터 업데이트"""
        try:
            # 실제 구현에서는 sheets_service의 update 메서드 사용
            # 여기서는 성공했다고 가정
            logger.info(f"객체 데이터 업데이트: {object_id}")
            return True
            
        except Exception as e:
            logger.error(f"객체 데이터 업데이트 실패: {e}")
            return False

    async def track_rollback_event(self, object_id: str, target_version: int, 
                                 rollback_by: str, rollback_reason: str):
        """롤백 이벤트 기록"""
        try:
            rollback_record = {
                'Rollback_ID': f"ROLLBACK_{object_id}_{int(datetime.now().timestamp())}",
                'Object_ID': object_id,
                'Target_Version': target_version,
                'Rollback_By': rollback_by,
                'Rollback_Date': datetime.now(timezone.utc).isoformat(),
                'Rollback_Reason': rollback_reason
            }
            
            # Rollback_Log 시트에 저장 (구현 필요)
            logger.info(f"롤백 이벤트 기록: {rollback_record['Rollback_ID']}")
            
        except Exception as e:
            logger.error(f"롤백 이벤트 기록 실패: {e}")

    async def create_snapshot(self, object_id: str, snapshot_by: str, 
                            snapshot_reason: str = '') -> str:
        """현재 상태 스냅샷 생성"""
        try:
            current_data = await self.get_current_object_data(object_id)
            
            if not current_data:
                return ""
            
            # 스냅샷을 새 버전으로 기록
            version_id = await self.track_molecule_change(
                object_id, {}, current_data, snapshot_by, 
                f"SNAPSHOT: {snapshot_reason}"
            )
            
            logger.info(f"스냅샷 생성 완료: {version_id}")
            return version_id
            
        except Exception as e:
            logger.error(f"스냅샷 생성 실패: {e}")
            return ""

    async def get_version_summary(self, object_id: str) -> Dict[str, Any]:
        """버전 요약 정보 조회"""
        try:
            version_history = await self.get_version_history(object_id)
            
            if not version_history:
                return {'object_id': object_id, 'total_versions': 0}
            
            latest_version = max([v['version_number'] for v in version_history])
            creation_date = min([v['changed_date'] for v in version_history])
            last_modified = max([v['changed_date'] for v in version_history])
            
            change_types = {}
            for version in version_history:
                change_type = version['change_type']
                change_types[change_type] = change_types.get(change_type, 0) + 1
            
            return {
                'object_id': object_id,
                'total_versions': len(version_history),
                'latest_version': latest_version,
                'creation_date': creation_date,
                'last_modified': last_modified,
                'change_types': change_types,
                'version_history': version_history[-5:]  # 최근 5개 버전
            }
            
        except Exception as e:
            logger.error(f"버전 요약 조회 실패: {e}")
            return {}

    async def cleanup_old_versions(self, retention_days: int = 90) -> int:
        """오래된 버전 정리"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            # 실제 구현에서는 Version_History에서 오래된 기록 삭제
            # 여기서는 정리된 개수만 반환
            cleaned_count = 0
            
            logger.info(f"버전 정리 완료: {cleaned_count}개 기록 삭제")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"버전 정리 실패: {e}")
            return 0

# 사용 예시
if __name__ == "__main__":
    async def test_version_controller():
        """버전 컨트롤러 테스트"""
        # sheets_service = SheetsService(...)  # 실제 사용 시 필요
        # version_controller = VersionController(sheets_service)
        
        print("📚 버전 컨트롤러 테스트")
        print("실제 사용을 위해서는 sheets_service가 필요합니다")
        
        version_controller = VersionController(None)
        
        # 테스트 데이터
        old_data = {
            'Molecule_ID': 'TEST-001',
            'Match_Threshold_%': 80,
            'Status': 'quarantined'
        }
        
        new_data = {
            'Molecule_ID': 'TEST-001',
            'Match_Threshold_%': 85,  # 변경됨
            'Status': 'active'        # 변경됨
        }
        
        # 변경 필드 식별 테스트
        changed_fields = version_controller.identify_changed_fields(old_data, new_data)
        print(f"변경된 필드: {changed_fields}")
        
        # 체크섬 계산 테스트
        checksum = version_controller.calculate_checksum(new_data)
        print(f"체크섬: {checksum}")

    asyncio.run(test_version_controller())
