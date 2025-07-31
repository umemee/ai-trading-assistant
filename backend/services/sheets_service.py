"""
sheets_service.py - Google Sheets API 연동 서비스
AI 트레이딩 어시스턴트 V5.5의 핵심 데이터베이스 인터페이스

- 10개 핵심 시트와의 완전한 CRUD 작업 지원
- 환경별 시트 ID 자동 적용
- 데이터 무결성을 위한 행 단위 업데이트
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

    def __init__(self, spreadsheet_id: str, credentials_path: str = "credentials.json"):
        """
        Google Sheets API 서비스 초기화
        """
        self.spreadsheet_id = spreadsheet_id
        self._credentials = self._load_credentials(credentials_path)
        self.service = build('sheets', 'v4', credentials=self._credentials)

        # 시트 이름 상수 정의 (기획서 기준)
        self.ATOM_DB = "Atom_DB"
        self.MOLECULE_DB = "Molecule_DB"
        self.SIDB = "SIDB"
        self.PERFORMANCE_DASHBOARD = "Performance_Dashboard"
        self.PREDICTION_NOTES = "Prediction_Notes"
        # 신규 시트
        self.QUARANTINE_QUEUE = "Quarantine_Queue"
        self.APPROVAL_LOG = "Approval_Log"
        self.VERSION_HISTORY = "Version_History"
        self.RISK_ALERTS = "Risk_Alerts"
        self.WFO_RESULTS = "WFO_Results"

        logger.info("Google Sheets API 서비스 초기화 완료")

    def _load_credentials(self, credentials_path: str) -> Credentials:
        """서비스 계정 인증 정보 로드"""
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        # 환경 변수에서 인증 정보 로드 시도
        creds_json_str = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        if creds_json_str:
            try:
                creds_info = json.loads(creds_json_str)
                return Credentials.from_service_account_info(creds_info, scopes=scopes)
            except json.JSONDecodeError:
                logger.error("환경 변수의 GOOGLE_SERVICE_ACCOUNT_JSON이 올바른 JSON 형식이 아닙니다.")
        
        # 파일에서 로드
        if os.path.exists(credentials_path):
            return Credentials.from_service_account_file(credentials_path, scopes=scopes)
        
        raise FileNotFoundError(
            f"인증 파일을 찾을 수 없습니다. "
            f"GOOGLE_SERVICE_ACCOUNT_JSON 환경 변수를 설정하거나 "
            f"'{credentials_path}' 파일을 프로젝트 루트에 위치시켜 주세요."
        )

    async def _get_sheet_values(self, range_name: str) -> List[List[Any]]:
        """시트의 모든 값을 가져오는 유틸리티 함수"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            return result.get('values', [])
        except HttpError as e:
            logger.error(f"시트 값 조회 실패 ({range_name}): {e}")
            if e.resp.status == 404:
                logger.error(f"시트 또는 범위를 찾을 수 없습니다. 시트 이름이 '{range_name}'이 맞는지 확인하세요.")
            return []

    async def _append_row(self, sheet_name: str, values: List[Any]) -> bool:
        """시트에 한 행을 추가하는 유틸리티 함수"""
        try:
            body = {'values': [values]}
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            return True
        except Exception as e:
            logger.error(f"시트 행 추가 실패 ({sheet_name}): {e}")
            return False

    async def get_molecules(self) -> List[Dict]:
        """분자 DB에서 모든 분자 데이터 조회"""
        values = await self._get_sheet_values(self.MOLECULE_DB)
        if not values or len(values) < 2:
            return []
        
        headers = values[0]
        molecules = [dict(zip(headers, row)) for row in values[1:]]
        return molecules
        
    async def get_atoms(self) -> List[Dict]:
        """아톰 DB에서 모든 아톰 데이터 조회"""
        values = await self._get_sheet_values(self.ATOM_DB)
        if not values or len(values) < 2:
            return []
        
        headers = values[0]
        atoms = [dict(zip(headers, row)) for row in values[1:]]
        return atoms
    
    # === 1단계 목표: 신규 DB 시트 연동 함수 구현 ===

    async def save_wfo_result(self, result_data: Dict) -> bool:
        """WFO_Results 시트에 WFO 검증 결과 기록"""
        logger.info(f"WFO 결과 저장 요청: {result_data.get('Molecule_ID')}")
        values = [
            result_data.get('Result_ID', str(uuid.uuid4())),
            result_data.get('Molecule_ID'),
            result_data.get('Test_Date', datetime.now(timezone.utc).isoformat()),
            result_data.get('Walk_Forward_Periods'),
            result_data.get('Simple_Return'),
            result_data.get('WFO_Return'),
            result_data.get('WFO_Efficiency'),
            result_data.get('Max_Drawdown'),
            result_data.get('Sharpe_Ratio'),
            result_data.get('Parameter_Stability_Score'),
            result_data.get('Validation_Status')
        ]
        return await self._append_row(self.WFO_RESULTS, values)

    async def save_risk_alert(self, alert_data: Dict) -> bool:
        """Risk_Alerts 시트에 위험 알림 기록"""
        logger.info(f"위험 알림 저장 요청: {alert_data.get('Molecule_ID')}")
        values = [
            alert_data.get('Alert_ID', str(uuid.uuid4())),
            alert_data.get('Molecule_ID'),
            alert_data.get('Alert_Type'),
            alert_data.get('Alert_Level'),
            alert_data.get('Triggered_Date', datetime.now(timezone.utc).isoformat()),
            alert_data.get('Auto_Action'),
            alert_data.get('Current_Drawdown'),
            alert_data.get('Alert_Details')
        ]
        return await self._append_row(self.RISK_ALERTS, values)

    async def save_version_record(self, version_data: Dict) -> bool:
        """Version_History 시트에 버전 변경 이력 기록"""
        logger.info(f"버전 기록 저장 요청: {version_data.get('Object_ID')}")
        values = [
            version_data.get('History_ID', str(uuid.uuid4())),
            version_data.get('Molecule_ID'),
            version_data.get('Version'),
            json.dumps(version_data.get('Changed_Fields', {})),
            json.dumps(version_data.get('Old_Values', {})),
            json.dumps(version_data.get('New_Values', {})),
            version_data.get('Changed_By'),
            version_data.get('Changed_Date', datetime.now(timezone.utc).isoformat()),
            version_data.get('Change_Reason')
        ]
        return await self._append_row(self.VERSION_HISTORY, values)

    async def log_approval_action(self, log_data: Dict) -> bool:
        """Approval_Log 시트에 승인/거부 활동 기록"""
        logger.info(f"승인 활동 기록 요청: {log_data.get('Molecule_ID')}")
        values = [
            log_data.get('Log_ID', str(uuid.uuid4())),
            log_data.get('Molecule_ID'),
            log_data.get('Action'), # 'approved' or 'rejected'
            log_data.get('Reviewer'),
            log_data.get('Review_Date', datetime.now(timezone.utc).isoformat()),
            log_data.get('Review_Notes'),
            log_data.get('Previous_Status'),
            log_data.get('New_Status')
        ]
        return await self._append_row(self.APPROVAL_LOG, values)

    async def update_molecule_info(self, molecule_id: str, updates: Dict[str, Any]) -> bool:
        """Molecule_DB의 특정 분자 정보 업데이트"""
        logger.info(f"분자 정보 업데이트 요청: {molecule_id}, 업데이트 항목: {list(updates.keys())}")
        try:
            values = await self._get_sheet_values(self.MOLECULE_DB)
            if not values or len(values) < 2:
                logger.error("분자 DB가 비어있거나 헤더가 없습니다.")
                return False

            headers = values[0]
            
            # 업데이트할 컬럼 인덱스 찾기
            update_indices = {}
            for key in updates.keys():
                if key not in headers:
                    logger.warning(f"'{key}' 컬럼이 분자 DB에 없어 업데이트를 건너뜁니다.")
                    continue
                update_indices[key] = headers.index(key)

            if not update_indices:
                logger.warning("업데이트할 유효한 컬럼이 없습니다.")
                return False

            # 해당 분자 ID를 찾아 행 업데이트
            mol_id_col_index = headers.index("Molecule_ID")
            target_row_index = -1
            for i, row in enumerate(values[1:]):
                if row[mol_id_col_index] == molecule_id:
                    target_row_index = i + 2  # 시트 인덱스는 1부터 시작, 헤더 제외
                    break
            
            if target_row_index == -1:
                logger.error(f"업데이트할 분자를 찾지 못했습니다: {molecule_id}")
                return False

            # Google Sheets API의 batchUpdate를 사용하여 특정 셀들만 업데이트
            data = []
            for key, value in updates.items():
                if key in update_indices:
                    col_letter = chr(ord('A') + update_indices[key])
                    data.append({
                        'range': f"{self.MOLECULE_DB}!{col_letter}{target_row_index}",
                        'values': [[value]]
                    })

            body = {
                'valueInputOption': 'USER_ENTERED',
                'data': data
            }
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body=body
            ).execute()

            logger.info(f"분자 정보 업데이트 완료: {molecule_id}")
            return True

        except Exception as e:
            logger.error(f"분자 정보 업데이트 실패 ({molecule_id}): {e}")
            return False

# 스크립트 실행 예시 (테스트용)
if __name__ == '__main__':
    # 이 부분은 직접 실행되지 않으며, 다른 파일에서 import하여 사용합니다.
    print("SheetsService 모듈이 로드되었습니다.")
    print("이 모듈은 AI 트레이딩 시스템의 다른 부분에서 사용됩니다.")
