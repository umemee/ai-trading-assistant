"""
sheets_service.py - 완전한 Google Sheets API 연동 서비스

AI 트레이딩 어시스턴트 V5.5의 핵심 데이터베이스 관리 모듈

주요 기능:
- 9개 핵심 시트 완전 관리 (Molecule_DB, Quarantine_Queue 등)
- 검역-승인 워크플로우 지원
- WFO 백테스팅 결과 관리
- 버전 관리 및 위험 알림 시스템
- 완전한 CRUD 작업 지원
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
import traceback

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

logger = logging.getLogger(__name__)

class SheetsService:
    """완전한 Google Sheets 서비스 클래스"""
    
    # ================== 시트 이름 상수 정의 ==================
    
    # 기존 시트들
    SHEET_ATOM_DB = "Atom_DB"
    SHEET_MOLECULE_DB = "Molecule_DB"  
    SHEET_SIDB = "SIDB"
    SHEET_PREDICTIONS = "예측/오답노트"
    SHEET_PERFORMANCE = "Performance_Dashboard"
    
    # 신규 시트들 (V5.5)
    SHEET_QUARANTINE_QUEUE = "Quarantine_Queue"
    SHEET_APPROVAL_LOG = "Approval_Log"
    SHEET_VERSION_HISTORY = "Version_History"
    SHEET_RISK_ALERTS = "Risk_Alerts"
    SHEET_WFO_RESULTS = "WFO_Results"
    
    # ================== 컬럼 정의 상수 ==================
    
    # Molecule_DB 컬럼 (확장됨)
    MOLECULE_COLS = [
        "Molecule_ID", "Molecule_Name", "Category", "Required_Atom_IDs",
        "Match_Threshold_%", "Translation_Notes", "Entry_SL_TP",
        # V5.5 신규 컬럼들
        "Status", "Created_Date", "Approved_Date", "Approved_By",  
        "WFO_Score", "WFO_Efficiency", "Max_Drawdown", 
        "Version", "Parent_Version", "Environment"
    ]
    
    # Quarantine_Queue 컬럼
    QUARANTINE_COLS = [
        "Queue_ID", "Molecule_ID", "Created_Date", "AI_Confidence",
        "WFO_Status", "Review_Notes", "Priority_Level", "Estimated_Review_Date"
    ]
    
    # Approval_Log 컬럼  
    APPROVAL_COLS = [
        "Log_ID", "Molecule_ID", "Action", "Reviewer", "Review_Date",
        "Review_Notes", "Previous_Status", "New_Status"
    ]
    
    # Version_History 컬럼
    VERSION_COLS = [
        "History_ID", "Molecule_ID", "Version", "Changed_Fields", 
        "Old_Values", "New_Values", "Changed_By", "Changed_Date", "Change_Reason"
    ]
    
    # Risk_Alerts 컬럼
    RISK_COLS = [
        "Alert_ID", "Molecule_ID", "Alert_Type", "Alert_Level",
        "Triggered_Date", "Auto_Action", "Current_Drawdown", "Alert_Details"
    ]
    
    # WFO_Results 컬럼
    WFO_COLS = [
        "Result_ID", "Molecule_ID", "Test_Date", "Walk_Forward_Periods",
        "Simple_Return", "WFO_Return", "WFO_Efficiency", "Max_Drawdown",
        "Sharpe_Ratio", "Parameter_Stability_Score", "Validation_Status"
    ]
    
    # Performance_Dashboard 컬럼 (확장됨)
    PERFORMANCE_COLS = [
        "Molecule_ID", "Total_Trades", "Win_Rate_%", "Avg_RRR", 
        "Avg_Hold_Time_Mins", "Profit_Factor", "Confidence_Score", "Last_Updated",
        # V5.5 신규 컬럼들
        "Max_Drawdown_%", "WFO_Efficiency", "Sharpe_Ratio",
        "Current_Drawdown_%", "Risk_Alert_Level", "Auto_Disabled_Date", "Environment"
    ]

    def __init__(self, spreadsheet_id: str, service_account_json: str = None, 
                 credentials_path: str = "credentials.json"):
        """
        Google Sheets 서비스 초기화
        
        Args:
            spreadsheet_id: Google 스프레드시트 ID
            service_account_json: 서비스 계정 JSON (문자열)
            credentials_path: 자격증명 파일 경로
        """
        self.spreadsheet_id = spreadsheet_id
        self.service_account_json = service_account_json
        self.credentials_path = credentials_path
        self.client = None
        self.spreadsheet = None
        
        # 연결 상태
        self.is_connected = False
        self.last_error = None
        
        # 캐시
        self.sheets_cache = {}
        self.cache_expiry = {}
        self.cache_timeout = 300  # 5분
        
        logger.info("SheetsService 초기화 완료")

    async def initialize(self):
        """서비스 초기화 및 연결"""
        try:
            await self._authenticate()
            await self._verify_or_create_sheets()
            self.is_connected = True
            logger.info("✅ Google Sheets 서비스 초기화 완료")
            return True
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"❌ Google Sheets 초기화 실패: {e}")
            return False

    async def _authenticate(self):
        """Google Sheets API 인증"""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            if self.service_account_json:
                # JSON 문자열에서 인증
                creds_info = json.loads(self.service_account_json)
                credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
            else:
                # 파일에서 인증
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"자격증명 파일을 찾을 수 없습니다: {self.credentials_path}")
                credentials = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            logger.info("Google Sheets API 인증 성공")
            
        except Exception as e:
            logger.error(f"Google Sheets 인증 실패: {e}")
            raise

    async def _verify_or_create_sheets(self):
        """필요한 시트들이 존재하는지 확인하고 없으면 생성"""
        try:
            existing_sheets = {sheet.title for sheet in self.spreadsheet.worksheets()}
            
            # 필요한 모든 시트 정의
            required_sheets = {
                self.SHEET_ATOM_DB: ["Atom_ID", "Atom_Name", "Description", "Output_Column_Name", "Category", "Timeframe", "Source_Reference"],
                self.SHEET_MOLECULE_DB: self.MOLECULE_COLS,
                self.SHEET_SIDB: ["Instance_ID", "Timestamp_UTC", "Ticker", "Atom_ID", "Timeframe", "Price_At_Signal", "Volume_At_Signal", "Context_Atoms_Active", "Is_Duplicate"],
                self.SHEET_PREDICTIONS: ["Prediction_ID", "Timestamp_UTC", "Ticker", "Triggered_Molecule_ID", "Prediction_Summary", "Key_Atoms_Found", "Actual_Outcome", "Human_Feedback", "AI_Review_Summary", "Position_Size", "Overnight_Permission"],
                self.SHEET_PERFORMANCE: self.PERFORMANCE_COLS,
                self.SHEET_QUARANTINE_QUEUE: self.QUARANTINE_COLS,
                self.SHEET_APPROVAL_LOG: self.APPROVAL_COLS,
                self.SHEET_VERSION_HISTORY: self.VERSION_COLS,
                self.SHEET_RISK_ALERTS: self.RISK_COLS,
                self.SHEET_WFO_RESULTS: self.WFO_COLS
            }
            
            # 누락된 시트 생성
            for sheet_name, columns in required_sheets.items():
                if sheet_name not in existing_sheets:
                    logger.info(f"📝 신규 시트 생성 중: {sheet_name}")
                    await self._create_sheet_with_headers(sheet_name, columns)
                else:
                    logger.debug(f"✅ 시트 존재 확인: {sheet_name}")
            
            logger.info("🎯 모든 필요한 시트 검증 완료")
            
        except Exception as e:
            logger.error(f"시트 검증/생성 실패: {e}")
            raise

    async def _create_sheet_with_headers(self, sheet_name: str, headers: List[str]):
        """헤더와 함께 새 시트 생성"""
        try:
            # 시트 생성
            worksheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))
            
            # 헤더 행 추가
            worksheet.append_row(headers)
            
            logger.info(f"✅ 시트 생성 완료: {sheet_name} ({len(headers)}개 컬럼)")
            
        except Exception as e:
            logger.error(f"시트 생성 실패 ({sheet_name}): {e}")
            raise

    async def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            if not self.client or not self.spreadsheet:
                await self._authenticate()
            
            # 간단한 읽기 테스트
            test_sheet = self.spreadsheet.worksheets()[0]
            test_sheet.get('A1')
            
            self.is_connected = True
            logger.info("Google Sheets 연결 테스트 성공")
            return True
            
        except Exception as e:
            self.last_error = str(e) 
            self.is_connected = False
            logger.error(f"Google Sheets 연결 테스트 실패: {e}")
            return False

    # ================== Molecule_DB 관련 메서드 ==================
    
    async def get_molecules(self, status_filter: str = None) -> List[Dict[str, Any]]:
        """분자 목록 조회 (상태 필터 지원)"""
        try:
            worksheet = self.spreadsheet.worksheet(self.SHEET_MOLECULE_DB)
            records = worksheet.get_all_records()
            
            # 상태 필터 적용
            if status_filter:
                records = [r for r in records if r.get('Status', '').lower() == status_filter.lower()]
            
            logger.debug(f"분자 데이터 조회: {len(records)}개 (필터: {status_filter})")
            return records
            
        except Exception as e:
            logger.error(f"분자 데이터 조회 실패: {e}")
            return []

    async def add_molecule(self, molecule_data: Dict[str, Any]) -> bool:
        """새 분자 추가 (검역 상태로)"""
        try:
            # 기본값 설정
            molecule_data.setdefault('Status', 'quarantined')
            molecule_data.setdefault('Created_Date', datetime.now(timezone.utc).isoformat())
            molecule_data.setdefault('WFO_Score', 0.0)
            molecule_data.setdefault('Version', '1.0')
            molecule_data.setdefault('Environment', 'staging')
            
            worksheet = self.spreadsheet.worksheet(self.SHEET_MOLECULE_DB)
            
            # 컬럼 순서에 맞게 데이터 정렬
            row_data = []
            for col in self.MOLECULE_COLS:
                row_data.append(str(molecule_data.get(col, '')))
            
            worksheet.append_row(row_data)
            
            logger.info(f"✅ 새 분자 추가 (검역): {molecule_data.get('Molecule_ID')}")
            return True
            
        except Exception as e:
            logger.error(f"분자 추가 실패: {e}")
            return False

    async def update_molecule_status(self, molecule_id: str, new_status: str, 
                                   approved_by: str = None) -> bool:
        """분자 상태 업데이트"""
        try:
            worksheet = self.spreadsheet.worksheet(self.SHEET_MOLECULE_DB)
            records = worksheet.get_all_records()
            
            # 해당 분자 찾기
            for i, record in enumerate(records):
                if record.get('Molecule_ID') == molecule_id:
                    row_num = i + 2  # 헤더 고려
                    
                    # 상태 업데이트
                    status_col = self.MOLECULE_COLS.index('Status') + 1
                    worksheet.update_cell(row_num, status_col, new_status)
                    
                    # 승인일시 업데이트 (active로 변경 시)
                    if new_status == 'active':
                        approved_date_col = self.MOLECULE_COLS.index('Approved_Date') + 1
                        worksheet.update_cell(row_num, approved_date_col, 
                                            datetime.now(timezone.utc).isoformat())
                        
                        if approved_by:
                            approved_by_col = self.MOLECULE_COLS.index('Approved_By') + 1
                            worksheet.update_cell(row_num, approved_by_col, approved_by)
                    
                    logger.info(f"✅ 분자 상태 업데이트: {molecule_id} → {new_status}")
                    return True
            
            logger.warning(f"분자를 찾을 수 없음: {molecule_id}")
            return False
            
        except Exception as e:
            logger.error(f"분자 상태 업데이트 실패: {e}")
            return False

    # ================== Quarantine_Queue 관련 메서드 ==================
    
    async def add_to_quarantine(self, molecule_data: Dict[str, Any]) -> bool:
        """검역소에 분자 추가"""
        try:
            quarantine_data = {
                'Queue_ID': str(uuid.uuid4()),
                'Molecule_ID': molecule_data.get('Molecule_ID'),
                'Created_Date': datetime.now(timezone.utc).isoformat(),
                'AI_Confidence': molecule_data.get('AI_Confidence', 0.8),
                'WFO_Status': 'pending',
                'Review_Notes': '',
                'Priority_Level': 'normal',
                'Estimated_Review_Date': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            }
            
            worksheet = self.spreadsheet.worksheet(self.SHEET_QUARANTINE_QUEUE)
            
            row_data = []
            for col in self.QUARANTINE_COLS:
                row_data.append(str(quarantine_data.get(col, '')))
            
            worksheet.append_row(row_data)
            
            logger.info(f"✅ 검역소에 추가: {molecule_data.get('Molecule_ID')}")
            return True
            
        except Exception as e:
            logger.error(f"검역소 추가 실패: {e}")
            return False

    async def get_quarantine_queue(self) -> List[Dict[str, Any]]:
        """검역 대기 목록 조회"""
        try:
            worksheet = self.spreadsheet.worksheet(self.SHEET_QUARANTINE_QUEUE)
            records = worksheet.get_all_records()
            
            logger.debug(f"검역 대기 목록: {len(records)}개")
            return records
            
        except Exception as e:
            logger.error(f"검역 목록 조회 실패: {e}")
            return []

    async def remove_from_quarantine(self, molecule_id: str) -> bool:
        """검역소에서 제거"""
        try:
            worksheet = self.spreadsheet.worksheet(self.SHEET_QUARANTINE_QUEUE)
            records = worksheet.get_all_records()
            
            for i, record in enumerate(records):
                if record.get('Molecule_ID') == molecule_id:
                    row_num = i + 2  # 헤더 고려
                    worksheet.delete_rows(row_num)
                    
                    logger.info(f"✅ 검역소에서 제거: {molecule_id}")
                    return True
            
            logger.warning(f"검역소에서 분자를 찾을 수 없음: {molecule_id}")
            return False
            
        except Exception as e:
            logger.error(f"검역소 제거 실패: {e}")
            return False

    # ================== Approval_Log 관련 메서드 ==================
    
    async def log_approval_action(self, molecule_id: str, action: str, 
                                 reviewer: str, notes: str = "") -> bool:
        """승인/거부 로그 기록"""
        try:
            log_data = {
                'Log_ID': str(uuid.uuid4()),
                'Molecule_ID': molecule_id,
                'Action': action,  # 'approved', 'rejected', 'pending'
                'Reviewer': reviewer,
                'Review_Date': datetime.now(timezone.utc).isoformat(),
                'Review_Notes': notes,
                'Previous_Status': 'quarantined',
                'New_Status': 'active' if action == 'approved' else 'rejected'
            }
            
            worksheet = self.spreadsheet.worksheet(self.SHEET_APPROVAL_LOG)
            
            row_data = []
            for col in self.APPROVAL_COLS:
                row_data.append(str(log_data.get(col, '')))
            
            worksheet.append_row(row_data)
            
            logger.info(f"✅ 승인 로그 기록: {molecule_id} - {action}")
            return True
            
        except Exception as e:
            logger.error(f"승인 로그 기록 실패: {e}")
            return False

    # ================== WFO_Results 관련 메서드 ==================
    
    async def save_wfo_result(self, wfo_data: Dict[str, Any]) -> bool:
        """WFO 백테스팅 결과 저장"""
        try:
            wfo_data.setdefault('Result_ID', str(uuid.uuid4()))
            wfo_data.setdefault('Test_Date', datetime.now(timezone.utc).isoformat())
            
            worksheet = self.spreadsheet.worksheet(self.SHEET_WFO_RESULTS)
            
            row_data = []
            for col in self.WFO_COLS:
                row_data.append(str(wfo_data.get(col, '')))
                
            worksheet.append_row(row_data)
            
            logger.info(f"✅ WFO 결과 저장: {wfo_data.get('Molecule_ID')} - 효율성: {wfo_data.get('WFO_Efficiency', 0)}")
            return True
            
        except Exception as e:
            logger.error(f"WFO 결과 저장 실패: {e}")
            return False

    async def get_wfo_results(self, molecule_id: str = None) -> List[Dict[str, Any]]:
        """WFO 결과 조회"""
        try:
            worksheet = self.spreadsheet.worksheet(self.SHEET_WFO_RESULTS)
            records = worksheet.get_all_records()
            
            if molecule_id:
                records = [r for r in records if r.get('Molecule_ID') == molecule_id]
            
            logger.debug(f"WFO 결과 조회: {len(records)}개")
            return records
            
        except Exception as e:
            logger.error(f"WFO 결과 조회 실패: {e}")
            return []

    # ================== Risk_Alerts 관련 메서드 ==================
    
    async def add_risk_alert(self, alert_data: Dict[str, Any]) -> bool:
        """위험 알림 추가"""
        try:
            alert_data.setdefault('Alert_ID', str(uuid.uuid4()))
            alert_data.setdefault('Triggered_Date', datetime.now(timezone.utc).isoformat())
            
            worksheet = self.spreadsheet.worksheet(self.SHEET_RISK_ALERTS)
            
            row_data = []
            for col in self.RISK_COLS:
                row_data.append(str(alert_data.get(col, '')))
            
            worksheet.append_row(row_data)
            
            logger.info(f"🚨 위험 알림 추가: {alert_data.get('Molecule_ID')} - {alert_data.get('Alert_Type')}")
            return True
            
        except Exception as e:
            logger.error(f"위험 알림 추가 실패: {e}")
            return False

    # ================== 기존 메서드들 (호환성 유지) ==================
    
    async def get_atoms(self) -> List[Dict[str, Any]]:
        """아톰 목록 조회"""
        try:
            worksheet = self.spreadsheet.worksheet(self.SHEET_ATOM_DB)
            records = worksheet.get_all_records()
            
            logger.debug(f"아톰 데이터 조회: {len(records)}개")
            return records
            
        except Exception as e:
            logger.error(f"아톰 데이터 조회 실패: {e}")
            return []

    async def append_sidb_record(self, sidb_data: Dict[str, Any]) -> bool:
        """SIDB 기록 추가"""
        try:
            sidb_data.setdefault('Instance_ID', str(uuid.uuid4()))
            sidb_data.setdefault('Timestamp_UTC', datetime.now(timezone.utc).isoformat())
            
            worksheet = self.spreadsheet.worksheet(self.SHEET_SIDB)
            
            # SIDB 컬럼 순서
            sidb_cols = ["Instance_ID", "Timestamp_UTC", "Ticker", "Atom_ID", "Timeframe", 
                        "Price_At_Signal", "Volume_At_Signal", "Context_Atoms_Active", "Is_Duplicate"]
            
            row_data = []
            for col in sidb_cols:
                row_data.append(str(sidb_data.get(col, '')))
            
            worksheet.append_row(row_data)
            
            logger.debug(f"✅ SIDB 기록 추가: {sidb_data.get('Atom_ID')}")
            return True
            
        except Exception as e:
            logger.error(f"SIDB 기록 실패: {e}")
            return False

    async def add_prediction_record(self, prediction_data: Dict[str, Any]) -> bool:
        """예측 기록 추가"""
        try:
            prediction_data.setdefault('Prediction_ID', str(uuid.uuid4()))
            prediction_data.setdefault('Timestamp_UTC', datetime.now(timezone.utc).isoformat())
            
            worksheet = self.spreadsheet.worksheet(self.SHEET_PREDICTIONS)
            
            # 예측 컬럼 순서
            pred_cols = ["Prediction_ID", "Timestamp_UTC", "Ticker", "Triggered_Molecule_ID", 
                        "Prediction_Summary", "Key_Atoms_Found", "Actual_Outcome", 
                        "Human_Feedback", "AI_Review_Summary", "Position_Size", "Overnight_Permission"]
            
            row_data = []
            for col in pred_cols:
                value = prediction_data.get(col, '')
                # 리스트인 경우 문자열로 변환
                if isinstance(value, list):
                    value = ','.join(map(str, value))
                row_data.append(str(value))
            
            worksheet.append_row(row_data)
            
            logger.info(f"✅ 예측 기록 추가: {prediction_data.get('Ticker')} - {prediction_data.get('Triggered_Molecule_ID')}")
            return True
            
        except Exception as e:
            logger.error(f"예측 기록 실패: {e}")
            return False

    # ================== 유틸리티 메서드 ==================
    
    def get_service_status(self) -> Dict[str, Any]:
        """서비스 상태 반환"""
        return {
            'is_connected': self.is_connected,
            'spreadsheet_id': self.spreadsheet_id,
            'last_error': self.last_error,
            'sheets_available': len(self.sheets_cache),
            'cache_timeout': self.cache_timeout
        }

    async def clear_cache(self):
        """캐시 초기화"""
        self.sheets_cache.clear()
        self.cache_expiry.clear()
        logger.info("시트 캐시 초기화 완료")

# 사용 예시
if __name__ == "__main__":
    async def test_sheets_service():
        """SheetsService 테스트"""
        # 환경변수에서 설정 로드
        spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if not spreadsheet_id:
            print("❌ GOOGLE_SPREADSHEET_ID 환경변수가 설정되지 않았습니다")
            return
        
        print("🔍 SheetsService 테스트 시작")
        print("=" * 60)
        
        try:
            # 서비스 초기화
            sheets = SheetsService(
                spreadsheet_id=spreadsheet_id,
                service_account_json=service_account_json
            )
            
            # 초기화 및 연결 테스트
            success = await sheets.initialize()
            if not success:
                print(f"❌ 초기화 실패: {sheets.last_error}")
                return
            
            print("✅ 서비스 초기화 성공")
            
            # 연결 테스트
            connected = await sheets.test_connection()
            print(f"📡 연결 테스트: {'성공' if connected else '실패'}")
            
            # 기본 데이터 조회 테스트
            molecules = await sheets.get_molecules()
            print(f"📊 분자 데이터: {len(molecules)}개")
            
            atoms = await sheets.get_atoms()
            print(f"⚛️ 아톰 데이터: {len(atoms)}개")
            
            quarantine = await sheets.get_quarantine_queue()
            print(f"🚨 검역 대기: {len(quarantine)}개")
            
            # 서비스 상태
            status = sheets.get_service_status()
            print(f"📈 서비스 상태: {status}")
            
            print("\n✅ 모든 테스트 완료!")
            
        except Exception as e:
            print(f"❌ 테스트 실패: {e}")
            print(traceback.format_exc())

    # 테스트 실행
    asyncio.run(test_sheets_service())
