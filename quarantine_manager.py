"""
quarantine_manager.py - 검역 큐 관리 및 WFO 자동 실행

Phase 3 전용 모듈 (붙여넣기 후 바로 사용)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict

from services.sheets_service import SheetsService
from validator import WFOValidator, WFOResult

logger = logging.getLogger(__name__)

class QuarantineManager:
    """검역 큐 감시 + WFO 실행 + 결과 기록"""

    def __init__(self, sheets: SheetsService):
        self.sheets = sheets
        self.validator = WFOValidator(sheets)

    async def get_queue(self) -> List[Dict]:
        """Status가 'quarantined'인 분자를 모두 가져온다."""
        molecules = await self.sheets.get_molecules()
        return [m for m in molecules if m.get("Status", "").lower() == "quarantined"]

    async def process_queue(self) -> List[WFOResult]:
        """큐를 순회하며 WFO 테스트 후 결과 기록 & 상태 업데이트"""
        queue = await self.get_queue()
        results: List[WFOResult] = []
        logger.info(f"🔍 검역 큐 {len(queue)}건 발견")
        for molecule in queue:
            try:
                res = await self.validator.run_molecule_wfo_test(molecule)
                if not res:
                    continue
                # WFO_Results 시트 기록
                await self.validator.save_wfo_result(res)
                # Molecule_DB에 WFO_Score 업데이트
                await self._update_molecule_score(molecule["Molecule_ID"], res)
                results.append(res)
            except Exception as e:
                logger.error(f"WFO 실패: {molecule['Molecule_ID']} - {e}")
        return results

    async def _update_molecule_score(self, mol_id: str, res: WFOResult) -> None:
        """Molecule_DB의 WFO_Score 컬럼만 PATCH"""
        range_ = f"Molecule_DB!A2:Z"   # 전체 검색
        sheet = self.sheets.service.spreadsheets()
        data = sheet.values().get(spreadsheetId=self.sheets.spreadsheet_id, range=range_).execute()
        values = data.get("values", [])
        headers = values[0]

        if "Molecule_ID" not in headers or "WFO_Score" not in headers:
            logger.warning("필수 컬럼이 없습니다. 시트 구조를 확인하세요.")
            return

        col_id = headers.index("Molecule_ID")
        col_score = headers.index("WFO_Score")

        for i, row in enumerate(values[1:], start=2):
            if len(row) > col_id and row[col_id] == mol_id:
                # 행 채우기
                while len(row) <= col_score:
                    row.append("")
                row[col_score] = f"{res.wfo_efficiency:.3f}"
                body = {"values": [row]}
                sheet.values().update(
                    spreadsheetId=self.sheets.spreadsheet_id,
                    range=f"Molecule_DB!A{i}",
                    valueInputOption="RAW",
                    body=body
                ).execute()
                # 검증 상태도 기록
                status_idx = headers.index("Status")
                row[status_idx] = "ready_for_review" if res.validation_status in ("PASSED", "CONDITIONAL") else "failed_wfo"
                sheet.values().update(
                    spreadsheetId=self.sheets.spreadsheet_id,
                    range=f"Molecule_DB!A{i}",
                    valueInputOption="RAW",
                    body={"values": [row]}
                ).execute()
                logger.info(f"{mol_id} → WFO_Score 업데이트 완료")
                break

if __name__ == "__main__":
    import os
    import json
    from dotenv import load_dotenv

    load_dotenv()
    sheets = SheetsService(
        spreadsheet_id=os.getenv("GOOGLE_SPREADSHEET_ID"),
        service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    )
    qm = QuarantineManager(sheets)
    asyncio.run(qm.process_queue())
