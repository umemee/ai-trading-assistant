"""
run_phase3_job.py - Phase 3 야간배치 (붙여넣기 후 바로 실행)

1) 검역 큐 → WFOValidator 실행
2) WFO_Results 시트 기록
3) Molecule_DB WFO_Score 업데이트
"""

import asyncio, logging, os
from dotenv import load_dotenv
from services.sheets_service import SheetsService
from quarantine_manager import QuarantineManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")

async def main():
    load_dotenv()
    sheets = SheetsService(
        spreadsheet_id=os.getenv("GOOGLE_SPREADSHEET_ID"),
        service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    )
    qm = QuarantineManager(sheets)
    results = await qm.process_queue()
    if results:
        passed = [r for r in results if r.validation_status == "PASSED"]
        logging.info(f"🎉 Phase 3 완료: {len(passed)}/{len(results)} PASSED")
    else:
        logging.info("대기 중인 검역 전략이 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())
