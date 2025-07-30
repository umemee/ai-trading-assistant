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
                numeric_fields = ['Total_Trades', 'Win_Rate_%
