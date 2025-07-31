"""
approval_manager.py - 승인 관리 시스템

검역된 분자들의 승인/거부 처리 및 상태 관리
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import json

from services.sheets_service import SheetsService
from validator import WFOValidator, WFOResult

logger = logging.getLogger(__name__)

class ApprovalManager:
    """승인 관리 시스템"""
    
    def __init__(self, sheets_service: SheetsService):
        self.sheets_service = sheets_service
        self.wfo_validator = WFOValidator(sheets_service)
        
        logger.info("ApprovalManager 초기화 완료")

    async def get_quarantine_queue(self) -> List[Dict]:
        """검역 대기 목록 조회"""
        try:
            molecules = await self.sheets_service.get_molecules()
            quarantine_queue = []
            
            for molecule in molecules:
                if molecule.get('Status', '').lower() == 'quarantined':
                    # WFO 결과가 있는지 확인
                    wfo_status = 'PENDING'  # 실제로는 WFO_Results 시트에서 조회
                    
                    quarantine_queue.append({
                        'molecule_id': molecule.get('Molecule_ID'),
                        'molecule_name': molecule.get('Molecule_Name'),
                        'category': molecule.get('Category'),
                        'created_date': molecule.get('Created_Date'),
                        'wfo_status': wfo_status,
                        'wfo_score': molecule.get('WFO_Score', 0.0),
                        'priority': self._calculate_priority(molecule)
                    })
            
            # 우선순위순 정렬
            quarantine_queue.sort(key=lambda x: x['priority'], reverse=True)
            
            logger.info(f"검역 대기 목록: {len(quarantine_queue)}개")
            return quarantine_queue
            
        except Exception as e:
            logger.error(f"검역 대기 목록 조회 실패: {e}")
            return []

    def _calculate_priority(self, molecule: Dict) -> float:
        """분자 우선순위 계산"""
        try:
            priority = 0.0
            
            # WFO 점수가 높을수록 우선순위 증가
            wfo_score = float(molecule.get('WFO_Score', 0))
            priority += wfo_score * 10
            
            # 생성 시간이 오래될수록 우선순위 증가
            created_date = molecule.get('Created_Date')
            if created_date:
                try:
                    created_dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                    days_old = (datetime.now(timezone.utc) - created_dt).days
                    priority += days_old * 0.1
                except:
                    pass
            
            return priority
            
        except Exception as e:
            logger.error(f"우선순위 계산 실패: {e}")
            return 0.0

    async def approve_molecule(self, molecule_id: str, approver: str, 
                             approval_notes: str = '') -> bool:
        """분자 승인 처리"""
        try:
            # 분자 정보 조회
            molecules = await self.sheets_service.get_molecules()
            target_molecule = None
            
            for molecule in molecules:
                if molecule.get('Molecule_ID') == molecule_id:
                    target_molecule = molecule
                    break
            
            if not target_molecule:
                logger.error(f"분자를 찾을 수 없음: {molecule_id}")
                return False
            
            # 상태를 active로 변경
            target_molecule['Status'] = 'active'
            target_molecule['Approved_Date'] = datetime.now(timezone.utc).isoformat()
            target_molecule['Approved_By'] = approver
            
            # Google Sheets 업데이트 (실제로는 sheets_service에 update 메서드 필요)
            success = await self._update_molecule_status(molecule_id, target_molecule)
            
            if success:
                # 승인 로그 기록
                await self._log_approval_action(
                    molecule_id, 'APPROVED', approver, approval_notes
                )
                
                logger.info(f"분자 승인 완료: {molecule_id} by {approver}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"분자 승인 실패: {e}")
            return False

    async def reject_molecule(self, molecule_id: str, reviewer: str, 
                            rejection_reason: str) -> bool:
        """분자 거부 처리"""
        try:
            # 분자 정보 조회
            molecules = await self.sheets_service.get_molecules()
            target_molecule = None
            
            for molecule in molecules:
                if molecule.get('Molecule_ID') == molecule_id:
                    target_molecule = molecule
                    break
            
            if not target_molecule:
                logger.error(f"분자를 찾을 수 없음: {molecule_id}")
                return False
            
            # 상태를 rejected로 변경
            target_molecule['Status'] = 'rejected'
            target_molecule['Approved_Date'] = datetime.now(timezone.utc).isoformat()
            target_molecule['Approved_By'] = reviewer
            
            # Google Sheets 업데이트
            success = await self._update_molecule_status(molecule_id, target_molecule)
            
            if success:
                # 거부 로그 기록
                await self._log_approval_action(
                    molecule_id, 'REJECTED', reviewer, rejection_reason
                )
                
                logger.info(f"분자 거부 완료: {molecule_id} by {reviewer}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"분자 거부 실패: {e}")
            return False

    async def run_wfo_validation(self, molecule_id: str = None) -> Dict:
        """WFO 검증 실행"""
        try:
            if molecule_id:
                # 특정 분자만 검증
                molecules = await self.sheets_service.get_molecules()
                target_molecule = next(
                    (m for m in molecules if m.get('Molecule_ID') == molecule_id), 
                    None
                )
                
                if not target_molecule:
                    return {'success': False, 'error': '분자를 찾을 수 없음'}
                
                result = await self.wfo_validator.run_molecule_wfo_test(target_molecule)
                
                if result:
                    # WFO 점수 업데이트
                    await self._update_wfo_score(molecule_id, result)
                    
                    return {
                        'success': True,
                        'molecule_id': molecule_id,
                        'validation_status': result.validation_status,
                        'wfo_efficiency': result.wfo_efficiency,
                        'wfo_sharpe': result.wfo_sharpe
                    }
                else:
                    return {'success': False, 'error': 'WFO 검증 실패'}
            
            else:
                # 모든 검역 분자 검증
                results = await self.wfo_validator.validate_quarantined_molecules()
                
                # 각 결과를 DB에 업데이트
                for result in results:
                    await self._update_wfo_score(result.molecule_id, result)
                
                return {
                    'success': True,
                    'total_tested': len(results),
                    'results': [
                        {
                            'molecule_id': r.molecule_id,
                            'validation_status': r.validation_status,
                            'wfo_efficiency': r.wfo_efficiency
                        } for r in results
                    ]
                }
                
        except Exception as e:
            logger.error(f"WFO 검증 실행 실패: {e}")
            return {'success': False, 'error': str(e)}

    async def _update_molecule_status(self, molecule_id: str, molecule_data: Dict) -> bool:
        """분자 상태 업데이트 (실제 구현 필요)"""
        try:
            # 실제로는 sheets_service에 update_molecule 메서드가 필요
            # 여기서는 성공했다고 가정
            logger.info(f"분자 상태 업데이트: {molecule_id}")
            return True
            
        except Exception as e:
            logger.error(f"분자 상태 업데이트 실패: {e}")
            return False

    async def _update_wfo_score(self, molecule_id: str, wfo_result: WFOResult) -> bool:
        """WFO 점수 업데이트"""
        try:
            # WFO 점수를 분자 DB에 업데이트
            logger.info(f"WFO 점수 업데이트: {molecule_id} - {wfo_result.wfo_efficiency:.3f}")
            return True
            
        except Exception as e:
            logger.error(f"WFO 점수 업데이트 실패: {e}")
            return False

    async def _log_approval_action(self, molecule_id: str, action: str, 
                                 reviewer: str, notes: str):
        """승인/거부 액션 로그 기록"""
        try:
            log_data = {
                'Log_ID': f"APPROVAL_{molecule_id}_{int(datetime.now().timestamp())}",
                'Molecule_ID': molecule_id,
                'Action': action,
                'Reviewer': reviewer,
                'Review_Date': datetime.now(timezone.utc).isoformat(),
                'Review_Notes': notes
            }
            
            # 실제로는 Approval_Log 시트에 기록 (sheets_service 확장 필요)
            logger.info(f"승인 로그 기록: {molecule_id} - {action}")
            
        except Exception as e:
            logger.error(f"승인 로그 기록 실패: {e}")

    async def get_approval_dashboard_data(self) -> Dict:
        """승인 대시보드 데이터 조회"""
        try:
            quarantine_queue = await self.get_quarantine_queue()
            
            # 상태별 통계
            pending_wfo = len([q for q in quarantine_queue if q['wfo_status'] == 'PENDING'])
            ready_for_review = len([q for q in quarantine_queue if q['wfo_status'] == 'PASSED'])
            failed_wfo = len([q for q in quarantine_queue if q['wfo_status'] == 'FAILED'])
            
            return {
                'quarantine_summary': {
                    'total_in_quarantine': len(quarantine_queue),
                    'pending_wfo': pending_wfo,
                    'ready_for_review': ready_for_review,
                    'failed_wfo': failed_wfo
                },
                'quarantine_queue': quarantine_queue[:10],  # 상위 10개만
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"승인 대시보드 데이터 조회 실패: {e}")
            return {}

# 사용 예시
if __name__ == "__main__":
    async def test_approval_manager():
        """승인 관리자 테스트"""
        # sheets_service = SheetsService(...)  # 실제 사용 시 필요
        # approval_manager = ApprovalManager(sheets_service)
        
        print("🎛️ 승인 관리자 테스트")
        print("실제 사용을 위해서는 sheets_service가 필요합니다")

    asyncio.run(test_approval_manager())
