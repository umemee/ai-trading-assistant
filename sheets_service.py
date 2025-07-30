"""
sheets_service.py - Google Sheets API 연동 서비스
AI 트레이딩 어시스턴트 V5.1의 핵심 데이터베이스 인터페이스

5개 핵심 시트와의 완전한 CRUD 작업 지원:
- Atom_DB: 아톰 정의 관리
- Molecule_DB: 분자 전략 관리  
- SIDB: 실시간 신호 기록
- Performance_Dashboard: 성과 대시보드
- Prediction_Notes: 예측/오답노트
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
import uuid

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd

# 로깅 설정
logger = logging.getLogger(__name__)

class SheetsService:
    """Google Sheets API 서비스 클래스"""
    
    def __init__(self, spreadsheet_id: str, service_account_json: Union[str, Dict] = None):
        """
        Google Sheets API 서비스 초기화
        
        Args:
            spreadsheet_id: Google Sheets 스프레드시트 ID
            service_account_json: 서비스 계정 JSON (문자열 또는 딕셔너리)
        """
        self.spreadsheet_id = spreadsheet_id
        self.service = None
        self._credentials = None
        
        # 스코프 정의
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        # 시트 이름 상수
        self.ATOM_DB = "Atom_DB"
        self.MOLECULE_DB = "Molecule_DB"
        self.SIDB = "SIDB"
        self.PERFORMANCE_DASHBOARD = "Performance_Dashboard"
        self.PREDICTION_NOTES = "Prediction_Notes"
        
        # 인증 및 서비스 초기화
        self._initialize_service(service_account_json)
    
    def _initialize_service(self, service_account_json: Union[str, Dict] = None):
        """Google Sheets API 서비스 초기화"""
        try:
            # 서비스 계정 인증 정보 로드
            if service_account_json:
                if isinstance(service_account_json, str):
                    # JSON 문자열인 경우
                    if service_account_json.startswith('{'):
                        credentials_info = json.loads(service_account_json)
                    else:
                        # 파일 경로인 경우
                        with open(service_account_json, 'r') as f:
                            credentials_info = json.load(f)
                else:
                    # 딕셔너리인 경우
                    credentials_info = service_account_json
                    
                self._credentials = Credentials.from_service_account_info(
                    credentials_info, scopes=self.scopes
                )
            else:
                # 환경 변수에서 로드
                credentials_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
                if credentials_json:
                    credentials_info = json.loads(credentials_json)
                    self._credentials = Credentials.from_service_account_info(
                        credentials_info, scopes=self.scopes
                    )
                else:
                    # 기본 인증 파일 사용
                    default_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                    if default_path and os.path.exists(default_path):
                        self._credentials = Credentials.from_service_account_file(
                            default_path, scopes=self.scopes
                        )
                    else:
                        raise ValueError("Google 서비스 계정 인증 정보를 찾을 수 없습니다.")
            
            # Google Sheets API 서비스 빌드
            self.service = build('sheets', 'v4', credentials=self._credentials)
            logger.info("Google Sheets API 서비스 초기화 완료")
            
        except Exception as e:
            logger.error(f"Google Sheets API 초기화 실패: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            # 스프레드시트 메타데이터 조회로 연결 테스트
            result = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            title = result.get('properties', {}).get('title', 'Unknown')
            logger.info(f"Google Sheets 연결 성공: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets 연결 테스트 실패: {e}")
            return False
    
    # ================== 아톰 DB 관리 ==================
    
    async def get_atoms(self) -> List[Dict]:
        """아톰 DB에서 모든 아톰 데이터 조회"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.ATOM_DB}!A:G"  # A~G 컬럼 (Timeframe 포함)
            ).execute()
            
            values = result.get('values', [])
            if not values:
                logger.warning("아톰 DB가 비어있습니다")
                return []
            
            # 헤더 행과 데이터 분리
            headers = values[0]
            atoms = []
            
            for row in values[1:]:
                # 행이 헤더보다 짧을 경우 빈 문자열로 채움
                while len(row) < len(headers):
                    row.append('')
                
                atom = dict(zip(headers, row))
                atoms.append(atom)
            
            logger.info(f"{len(atoms)}개 아톰 로드 완료")
            return atoms
            
        except Exception as e:
            logger.error(f"아톰 조회 실패: {e}")
            return []
    
    async def add_atom(self, atom_data: Dict) -> bool:
        """새 아톰을 아톰 DB에 추가"""
        try:
            # 현재 데이터 확인하여 다음 행 결정
            current_atoms = await self.get_atoms()
            next_row = len(current_atoms) + 2  # 헤더 행 + 1
            
            # 아톰 데이터를 리스트로 변환
            values = [
                atom_data.get('Atom_ID', ''),
                atom_data.get('Atom_Name', ''),
                atom_data.get('Description', ''),
                atom_data.get('Output_Column_Name', ''),
                atom_data.get('Category', ''),
                atom_data.get('Source_Reference', ''),
                atom_data.get('Timeframe', '')
            ]
            
            # 시트에 추가
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.ATOM_DB}!A{next_row}",
                valueInputOption='RAW',
                body={'values': [values]}
            ).execute()
            
            logger.info(f"새 아톰 추가: {atom_data.get('Atom_ID')}")
            return True
            
        except Exception as e:
            logger.error(f"아톰 추가 실패: {e}")
            return False
    
    # ================== 분자 DB 관리 ==================
    
    async def get_molecules(self) -> List[Dict]:
        """분자 DB에서 모든 분자 데이터 조회"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.MOLECULE_DB}!A:G"  # A~G 컬럼
            ).execute()
            
            values = result.get('values', [])
            if not values:
                logger.warning("분자 DB가 비어있습니다")
                return []
            
            headers = values[0]
            molecules = []
            
            for row in values[1:]:
                while len(row) < len(headers):
                    row.append('')
                
                molecule = dict(zip(headers, row))
                
                # Required_Atom_IDs를 리스트로 변환
                if molecule.get('Required_Atom_IDs'):
                    molecule['Required_Atom_IDs'] = [
                        atom_id.strip() 
                        for atom_id in molecule['Required_Atom_IDs'].split(',')
                        if atom_id.strip()
                    ]
                else:
                    molecule['Required_Atom_IDs'] = []
                
                # Match_Threshold_%를 숫자로 변환
                try:
                    molecule['Match_Threshold_%'] = float(molecule.get('Match_Threshold_%', 0))
                except ValueError:
                    molecule['Match_Threshold_%'] = 0.0
                
                molecules.append(molecule)
            
            logger.info(f"{len(molecules)}개 분자 로드 완료")
            return molecules
            
        except Exception as e:
            logger.error(f"분자 조회 실패: {e}")
            return []
    
    async def add_molecule(self, molecule_data: Dict) -> bool:
        """새 분자를 분자 DB에 추가"""
        try:
            current_molecules = await self.get_molecules()
            next_row = len(current_molecules) + 2
            
            # Required_Atom_IDs를 문자열로 변환
            required_atoms = molecule_data.get('Required_Atom_IDs', [])
            if isinstance(required_atoms, list):
                required_atoms_str = ', '.join(required_atoms)
            else:
                required_atoms_str = str(required_atoms)
            
            values = [
                molecule_data.get('Molecule_ID', ''),
                molecule_data.get('Molecule_Name', ''),
                molecule_data.get('Category', ''),
                required_atoms_str,
                molecule_data.get('Match_Threshold_%', 100),
                molecule_data.get('Translation_Notes', ''),
                molecule_data.get('Entry_SL_TP', '')
            ]
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.MOLECULE_DB}!A{next_row}",
                valueInputOption='RAW',
                body={'values': [values]}
            ).execute()
            
            logger.info(f"새 분자 추가: {molecule_data.get('Molecule_ID')}")
            return True
            
        except Exception as e:
            logger.error(f"분자 추가 실패: {e}")
            return False
    
    # ================== SIDB 관리 ==================
    
    async def append_sidb_record(self, signal_data: Dict) -> bool:
        """SIDB에 새 신호 기록 추가"""
        try:
            # Instance_ID 생성 (없는 경우)
            if 'Instance_ID' not in signal_data:
                signal_data['Instance_ID'] = str(uuid.uuid4())
            
            # UTC 타임스탬프 생성 (없는 경우)
            if 'Timestamp_UTC' not in signal_data:
                signal_data['Timestamp_UTC'] = datetime.now(timezone.utc).isoformat()
            
            values = [
                signal_data.get('Instance_ID'),
                signal_data.get('Timestamp_UTC'),
                signal_data.get('Ticker', ''),
                signal_data.get('Atom_ID', ''),
                signal_data.get('Timeframe', '1m'),
                signal_data.get('Price_At_Signal', 0),
                signal_data.get('Volume_At_Signal', 0),
                signal_data.get('Context_Atoms_Active', ''),
                signal_data.get('Is_Duplicate', False)
            ]
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SIDB}!A:I",
                valueInputOption='RAW',
                body={'values': [values]}
            ).execute()
            
            logger.info(f"SIDB 기록 추가: {signal_data.get('Ticker')} - {signal_data.get('Atom_ID')}")
            return True
            
        except Exception as e:
            logger.error(f"SIDB 기록 추가 실패: {e}")
            return False
    
    async def get_recent_sidb_records(self, hours: int = 24, ticker: str = None) -> List[Dict]:
        """최근 N시간 내 SIDB 기록 조회"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.SIDB}!A:I"
            ).execute()
            
            values = result.get('values', [])
            if len(values) < 2:
                return []
            
            headers = values[0]
            records = []
            cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
            
            for row in values[1:]:
                while len(row) < len(headers):
                    row.append('')
                
                record = dict(zip(headers, row))
                
                # 시간 필터링
                try:
                    record_time = datetime.fromisoformat(
                        record.get('Timestamp_UTC', '').replace('Z', '+00:00')
                    ).timestamp()
                    if record_time < cutoff_time:
                        continue
                except:
                    continue
                
                # 티커 필터링
                if ticker and record.get('Ticker') != ticker:
                    continue
                
                records.append(record)
            
            logger.info(f"최근 {hours}시간 SIDB 기록 {len(records)}개 조회")
            return records
            
        except Exception as e:
            logger.error(f"SIDB 기록 조회 실패: {e}")
            return []
    
    # ================== 성과 대시보드 관리 ==================
    
    async def get_performance_data(self) -> List[Dict]:
        """성과 대시보드 데이터 조회"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.PERFORMANCE_DASHBOARD}!A:H"
            ).execute()
            
            values = result.get('values', [])
            if len(values) < 2:
                return []
            
            headers = values[0]
            performance_data = []
            
            for row in values[1:]:
                while len(row) < len(headers):
                    row.append('')
                
                record = dict(zip(headers, row))
                
                # 숫자 필드 변환
                numeric_fields = ['Total_Trades', 'Win_Rate_%', 'Avg_RRR', 
                                'Avg_Hold_Time_Mins', 'Profit_Factor', 'Confidence_Score']
                
                for field in numeric_fields:
                    try:
                        record[field] = float(record.get(field, 0))
                    except ValueError:
                        record[field] = 0.0
                
                performance_data.append(record)
            
            logger.info(f"성과 데이터 {len(performance_data)}개 조회")
            return performance_data
            
        except Exception as e:
            logger.error(f"성과 데이터 조회 실패: {e}")
            return []
    
    async def update_performance_record(self, molecule_id: str, performance_data: Dict) -> bool:
        """특정 분자의 성과 기록 업데이트"""
        try:
            # 현재 성과 데이터 조회
            current_data = await self.get_performance_data()
            
            # 해당 분자 ID 찾기
            target_row = None
            for i, record in enumerate(current_data):
                if record.get('Molecule_ID') == molecule_id:
                    target_row = i + 2  # 헤더 행 고려
                    break
            
            # 새 레코드인 경우 추가
            if target_row is None:
                values = [
                    molecule_id,
                    performance_data.get('Total_Trades', 0),
                    performance_data.get('Win_Rate_%', 0),
                    performance_data.get('Avg_RRR', 0),
                    performance_data.get('Avg_Hold_Time_Mins', 0),
                    performance_data.get('Profit_Factor', 0),
                    performance_data.get('Confidence_Score', 0),
                    datetime.now(timezone.utc).isoformat()
                ]
                
                result = self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.PERFORMANCE_DASHBOARD}!A:H",
                    valueInputOption='RAW',
                    body={'values': [values]}
                ).execute()
            else:
                # 기존 레코드 업데이트
                values = [
                    molecule_id,
                    performance_data.get('Total_Trades', 0),
                    performance_data.get('Win_Rate_%', 0),
                    performance_data.get('Avg_RRR', 0),
                    performance_data.get('Avg_Hold_Time_Mins', 0),
                    performance_data.get('Profit_Factor', 0),
                    performance_data.get('Confidence_Score', 0),
                    datetime.now(timezone.utc).isoformat()
                ]
                
                result = self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.PERFORMANCE_DASHBOARD}!A{target_row}:H{target_row}",
                    valueInputOption='RAW',
                    body={'values': [values]}
                ).execute()
            
            logger.info(f"성과 기록 업데이트: {molecule_id}")
            return True
            
        except Exception as e:
            logger.error(f"성과 기록 업데이트 실패: {e}")
            return False
    
    # ================== 예측/오답노트 관리 ==================
    
    async def add_prediction_record(self, prediction_data: Dict) -> bool:
        """예측/오답노트에 새 예측 기록 추가"""
        try:
            # Prediction_ID 생성 (없는 경우)
            if 'Prediction_ID' not in prediction_data:
                prediction_data['Prediction_ID'] = str(uuid.uuid4())
            
            # UTC 타임스탬프 생성 (없는 경우)
            if 'Timestamp_UTC' not in prediction_data:
                prediction_data['Timestamp_UTC'] = datetime.now(timezone.utc).isoformat()
            
            # Key_Atoms_Found 리스트를 문자열로 변환
            key_atoms = prediction_data.get('Key_Atoms_Found', [])
            if isinstance(key_atoms, list):
                key_atoms_str = ', '.join(key_atoms)
            else:
                key_atoms_str = str(key_atoms)
            
            values = [
                prediction_data.get('Prediction_ID'),
                prediction_data.get('Timestamp_UTC'),
                prediction_data.get('Ticker', ''),
                prediction_data.get('Triggered_Molecule_ID', ''),
                prediction_data.get('Prediction_Summary', ''),
                key_atoms_str,
                prediction_data.get('Actual_Outcome', ''),
                prediction_data.get('Human_Feedback', ''),
                prediction_data.get('AI_Review_Summary', ''),
                prediction_data.get('Position_Size', ''),
                prediction_data.get('Overnight_Permission', '')
            ]
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.PREDICTION_NOTES}!A:K",
                valueInputOption='RAW',
                body={'values': [values]}
            ).execute()
            
            logger.info(f"예측 기록 추가: {prediction_data.get('Ticker')} - {prediction_data.get('Triggered_Molecule_ID')}")
            return True
            
        except Exception as e:
            logger.error(f"예측 기록 추가 실패: {e}")
            return False
    
    async def get_pending_predictions(self) -> List[Dict]:
        """아직 결과가 입력되지 않은 예측들 조회"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.PREDICTION_NOTES}!A:K"
            ).execute()
            
            values = result.get('values', [])
            if len(values) < 2:
                return []
            
            headers = values[0]
            pending_predictions = []
            
            for row in values[1:]:
                while len(row) < len(headers):
                    row.append('')
                
                record = dict(zip(headers, row))
                
                # Actual_Outcome이 비어있는 경우만 반환
                if not record.get('Actual_Outcome', '').strip():
                    pending_predictions.append(record)
            
            logger.info(f"미완료 예측 {len(pending_predictions)}개 조회")
            return pending_predictions
            
        except Exception as e:
            logger.error(f"미완료 예측 조회 실패: {e}")
            return []
    
    async def update_prediction_outcome(self, prediction_id: str, 
                                      actual_outcome: str, 
                                      human_feedback: str = '',
                                      ai_review_summary: str = '') -> bool:
        """예측 결과 업데이트"""
        try:
            # 현재 예측 노트 데이터 조회
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.PREDICTION_NOTES}!A:K"
            ).execute()
            
            values = result.get('values', [])
            if len(values) < 2:
                return False
            
            headers = values[0]
            
            # 해당 예측 ID 찾기
            target_row = None
            for i, row in enumerate(values[1:]):
                while len(row) < len(headers):
                    row.append('')
                
                if row[0] == prediction_id:  # Prediction_ID는 첫 번째 컬럼
                    target_row = i + 2  # 헤더 행 고려
                    break
            
            if target_row is None:
                logger.error(f"예측 ID {prediction_id}를 찾을 수 없습니다")
                return False
            
            # 특정 컬럼만 업데이트
            updates = [
                {
                    'range': f"{self.PREDICTION_NOTES}!G{target_row}",  # Actual_Outcome
                    'values': [[actual_outcome]]
                },
                {
                    'range': f"{self.PREDICTION_NOTES}!H{target_row}",  # Human_Feedback
                    'values': [[human_feedback]]
                },
                {
                    'range': f"{self.PREDICTION_NOTES}!I{target_row}",  # AI_Review_Summary
                    'values': [[ai_review_summary]]
                }
            ]
            
            # 배치 업데이트 실행
            body = {
                'valueInputOption': 'RAW',
                'data': updates
            }
            
            result = self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.info(f"예측 결과 업데이트: {prediction_id}")
            return True
            
        except Exception as e:
            logger.error(f"예측 결과 업데이트 실패: {e}")
            return False
    
    # ================== 유틸리티 메서드 ==================
    
    async def get_sheet_info(self) -> Dict:
        """스프레드시트 정보 조회"""
        try:
            result = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheets_info = []
            for sheet in result.get('sheets', []):
                props = sheet.get('properties', {})
                sheets_info.append({
                    'title': props.get('title'),
                    'sheetId': props.get('sheetId'),
                    'gridProperties': props.get('gridProperties', {})
                })
            
            return {
                'title': result.get('properties', {}).get('title'),
                'sheets': sheets_info
            }
            
        except Exception as e:
            logger.error(f"시트 정보 조회 실패: {e}")
            return {}
    
    async def backup_data(self) -> Dict:
        """모든 데이터 백업"""
        try:
            backup_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'atoms': await self.get_atoms(),
                'molecules': await self.get_molecules(),
                'sidb_recent': await self.get_recent_sidb_records(hours=168),  # 7일
                'performance': await self.get_performance_data(),
                'pending_predictions': await self.get_pending_predictions()
            }
            
            logger.info("데이터 백업 완료")
            return backup_data
            
        except Exception as e:
            logger.error(f"데이터 백업 실패: {e}")
            return {}

# 사용 예시
if __name__ == "__main__":
    async def test_sheets_service():
        # 환경 변수에서 설정 로드
        spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if not spreadsheet_id:
            print("GOOGLE_SPREADSHEET_ID 환경 변수가 설정되지 않았습니다.")
            return
        
        # 서비스 초기화
        sheets_service = SheetsService(
            spreadsheet_id=spreadsheet_id,
            service_account_json=service_account_json
        )
        
        # 연결 테스트
        if await sheets_service.test_connection():
            print("✅ Google Sheets 연결 성공")
            
            # 아톰 데이터 조회
            atoms = await sheets_service.get_atoms()
            print(f"📊 아톰 {len(atoms)}개 로드")
            
            # 분자 데이터 조회
            molecules = await sheets_service.get_molecules()
            print(f"🧬 분자 {len(molecules)}개 로드")
            
        else:
            print("❌ Google Sheets 연결 실패")
    
    # 테스트 실행
    asyncio.run(test_sheets_service())
