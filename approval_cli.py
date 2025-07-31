"""
approval_cli.py - 검역 분자 승인/거부 CLI

사용 예:
$ python approval_cli.py list            # 큐 확인
$ python approval_cli.py approve LOGIC-EXP-004  "alice" "LGTM"
$ python approval_cli.py reject  LOGIC-EXP-009  "bob"   "리스크 초과"
"""

import asyncio, sys, os, json
from dotenv import load_dotenv
from services.sheets_service import SheetsService
from approval_manager import ApprovalManager

load_dotenv()
sheets = SheetsService(
    spreadsheet_id=os.getenv("GOOGLE_SPREADSHEET_ID"),
    service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
)
appr = ApprovalManager(sheets)

async def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "list":
        queue = await appr.get_quarantine_queue()
        for q in queue:
            print(f"{q['molecule_id']:<15} {q['wfo_status']:<10} {q['priority']:.2f}")
    elif cmd == "approve":
        _, mol, reviewer, note = sys.argv
        ok = await appr.approve_molecule(mol, reviewer, note)
        print("✅ 승인" if ok else "❌ 실패")
    elif cmd == "reject":
        _, mol, reviewer, note = sys.argv
        ok = await appr.reject_molecule(mol, reviewer, note)
        print("🚫 거부" if ok else "❌ 실패")
    else:
        print(__doc__)
        
if __name__ == "__main__":
    asyncio.run(main())
