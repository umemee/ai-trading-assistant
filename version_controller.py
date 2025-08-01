"""
version_controller.py - 분자 버전 관리 모듈

- 버전 번호 자동 증분 및 버전 기록 관리
- 실제 운영 환경에서는 sheets_service를 통해 Version_History 시트에서
  해당 Molecule_ID의 마지막 버전 번호를 조회 후 1 증가하는 방식으로 구현

2025-08-01 최신
"""

import logging
from typing import Optional
from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)

class VersionController:
    def __init__(self, sheets_service: SheetsService):
        self.sheets_service = sheets_service

    async def get_next_version_number(self, molecule_id: str) -> int:
        """
        해당 Molecule_ID의 다음 버전 번호를 반환
        - Version_History 시트에서 molecule_id에 해당하는 모든 기록 중 가장 높은 버전 번호를 찾아 +1
        - 신규 분자라면 1 반환
        """
        try:
            # Version_History 시트에서 모든 버전 기록을 가져옴
            history = await self.sheets_service.get_version_history()
            molecule_versions = [
                int(record.get("Version", "0"))
                for record in history
                if record.get("Molecule_ID", "") == molecule_id and record.get("Version", "").isdigit()
            ]
            if molecule_versions:
                next_version = max(molecule_versions) + 1
            else:
                next_version = 1
            logger.info(f"{molecule_id}의 다음 버전 번호: {next_version}")
            return next_version
        except Exception as e:
            logger.error(f"버전 번호 계산 오류: {e}")
            # 오류 시 기본값 1 반환
            return 1

    async def record_new_version(self, molecule_id: str, version: int, user: str, change_notes: str):
        """
        Version_History 시트에 버전 기록 추가
        """
        try:
            record = {
                "Molecule_ID": molecule_id,
                "Version": str(version),
                "Changed_By": user,
                "Change_Notes": change_notes,
                "Changed_Date": self.sheets_service.get_current_utc_iso()
            }
            await self.sheets_service.add_version_history_record(record)
            logger.info(f"분자 버전 기록 완료: {molecule_id} v{version} by {user}")
            return True
        except Exception as e:
            logger.error(f"분자 버전 기록 실패: {e}")
            return False

# 예시 사용법
if __name__ == "__main__":
    import os
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()
    sheets = SheetsService(
        spreadsheet_id=os.getenv("GOOGLE_SPREADSHEET_ID"),
        service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    )
    vc = VersionController(sheets)

    async def test_version():
        molecule_id = "LOGIC-EXP-026"
        next_version = await vc.get_next_version_number(molecule_id)
        print(f"다음 버전: {next_version}")
        ok = await vc.record_new_version(
            molecule_id,
            next_version,
            user="umemee",
            change_notes="신규 전략 성능 개선 및 필터 추가"
        )
        print(f"버전 기록 결과: {ok}")

    asyncio.run(test_version())
