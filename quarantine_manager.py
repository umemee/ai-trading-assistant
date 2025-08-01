"""
quarantine_manager.py - 검역 큐 관리 및 WFO 자동 실행 (Quarantine_Queue 별도 시트 기반)

기획서 명세 준수:
- 신규 분자는 Molecule_DB에 status: 'quarantined'로 추가됨과 동시에 Quarantine_Queue 시트에도 Queue_ID, Molecule_ID, WFO_Status 등으로 기록됨.
- 검역 큐(Quarantine_Queue)만을 대상으로 WFO 실행 및 결과 기록.
- 확장성과 감사 추적성을 고려한 설계.

Phase 3 전용 모듈 (붙여넣기 후 바로 사용)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional

from services.sheets_service import SheetsService
from validator import WFOValidator, WFOResult

logger = logging.getLogger(__name__)

class QuarantineManager:
    """Quarantine_Queue 시트 기반 검역 큐 관리 + WFO 실행 + 결과 기록"""

    def __init__(self, sheets: SheetsService):
        self.sheets = sheets
        self.validator = WFOValidator(sheets)

    async def add_to_quarantine_queue(self, molecule_id: str):
        """
        신규 분자를 Quarantine_Queue에 추가
        - Molecule_DB에 status: 'quarantined'로 등록된 후 호출되어야 함
        """
        queue_item = {
            "Queue_ID": str(uuid.uuid4()),
            "Molecule_ID": molecule_id,
            "Created_Date": datetime.now(timezone.utc).isoformat(),
            "WFO_Status": "PENDING",
            "Last_Updated": datetime.now(timezone.utc).isoformat()
        }
        # Quarantine_Queue 시트에 추가
        await self.sheets.add_quarantine_queue_item(queue_item)
        logger.info(f"Quarantine_Queue에 분자 등록: {molecule_id}")

    async def get_queue(self) -> List[Dict]:
        """
        Quarantine_Queue 시트에서 WFO_Status가 'PENDING' 또는 'RUNNING'인 분자 목록 반환
        """
        queue_items = await self.sheets.get_quarantine_queue()
        # 검역 큐의 상태가 PENDING/RUNNING인 분자만 큐에 포함
        queue = [item for item in queue_items if item.get("WFO_Status", "").upper() in ("PENDING", "RUNNING")]
        logger.info(f"Quarantine_Queue에서 검역 분자 {len(queue)}건 로드")
        return queue

    async def process_queue(self) -> List[WFOResult]:
        """
        큐를 순회하며 WFO 테스트 후 결과 기록 & 상태 업데이트 + Molecule_DB/Quarantine_Queue 동기화
        """
        queue = await self.get_queue()
        results: List[WFOResult] = []
        logger.info(f"🔍 검역 큐 {len(queue)}건 발견")
        for item in queue:
            molecule_id = item["Molecule_ID"]
            try:
                # WFO 시작: 상태 업데이트
                await self.update_quarantine_status(item["Queue_ID"], "RUNNING")
                molecule = await self.sheets.get_molecule_by_id(molecule_id)
                if not molecule:
                    logger.warning(f"Molecule_DB에서 {molecule_id} 조회 실패")
                    continue
                res = await self.validator.run_molecule_wfo_test(molecule)
                if not res:
                    await self.update_quarantine_status(item["Queue_ID"], "ERROR")
                    continue
                # WFO_Results 시트 기록
                await self.validator.save_wfo_result(res)
                # Molecule_DB에 WFO_Score, Status 업데이트
                await self._update_molecule_score_and_status(molecule_id, res)
                # Quarantine_Queue 상태 동기화
                wfo_status = "READY_FOR_REVIEW" if res.validation_status in ("PASSED", "CONDITIONAL") else "FAILED_WFO"
                await self.update_quarantine_status(item["Queue_ID"], wfo_status, wfo_efficiency=res.wfo_efficiency)
                results.append(res)
            except Exception as e:
                logger.error(f"WFO 실패: {molecule_id} - {e}")
                await self.update_quarantine_status(item["Queue_ID"], "ERROR")
        return results

    async def update_quarantine_status(self, queue_id: str, status: str, wfo_efficiency: Optional[float]=None):
        """
        Quarantine_Queue 시트의 WFO_Status 업데이트 (+ WFO_Efficiency)
        """
        update_payload = {
            "WFO_Status": status,
            "Last_Updated": datetime.now(timezone.utc).isoformat()
        }
        if wfo_efficiency is not None:
            update_payload["WFO_Efficiency"] = f"{wfo_efficiency:.3f}"
        await self.sheets.update_quarantine_queue_item(queue_id, update_payload)
        logger.info(f"Quarantine_Queue 상태 변경: {queue_id} → {status}")

    async def _update_molecule_score_and_status(self, mol_id: str, res: WFOResult):
        """
        Molecule_DB의 WFO_Score 및 Status 컬럼 PATCH
        - 검역 큐에서 WFO 테스트 결과에 따라 상태 변경
        """
        status = "ready_for_review" if res.validation_status in ("PASSED", "CONDITIONAL") else "failed_wfo"
        update_payload = {
            "WFO_Score": f"{res.wfo_efficiency:.3f}",
            "Status": status
        }
        await self.sheets.update_molecule_info(mol_id, update_payload)
        logger.info(f"Molecule_DB: {mol_id} → WFO_Score: {res.wfo_efficiency:.3f}, Status: {status}")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    sheets = SheetsService(
        spreadsheet_id=os.getenv("GOOGLE_SPREADSHEET_ID"),
        service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    )
    qm = QuarantineManager(sheets)
    asyncio.run(qm.process_queue())
