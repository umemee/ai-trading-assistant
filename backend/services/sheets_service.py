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

logger = logging.getLogger(__name__)

class SheetsService:
    """Google Sheets API 서비스 클래스"""

    def __init__(self, spreadsheet_id: str = None, service_account_json: Union[str, Dict] = None):
        self.spreadsheet_id = spreadsheet_id or os.getenv('GOOGLE_SPREADSHEET_ID')
        self.service = None
        self._credentials = None
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        # 시트 이름
        self.ATOM_DB = "Atom_DB"
        self.MOLECULE_DB = "Molecule_DB"
        self.SIDB = "SIDB"
        self.PERFORMANCE_DASHBOARD = "Performance_Dashboard"
        self.PREDICTION_NOTES = "Prediction_Notes"
        self.QUARANTINE_QUEUE = "Quarantine_Queue"
        self.APPROVAL_LOG = "Approval_Log"
        self.VERSION_HISTORY = "Version_History"
        self.RISK_ALERTS = "Risk_Alerts"
        self.WFO_RESULTS = "WFO_Results"
        self._initialize_service(service_account_json)

    def _initialize_service(self, service_account_json: Union[str, Dict] = None):
        try:
            json_str = service_account_json or os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
            if json_str:
                if isinstance(json_str, dict):
                    credentials_info = json_str
                elif json_str.strip().startswith('{'):
                    credentials_info = json.loads(json_str)
                else:
                    with open(json_str, "r") as f:
                        credentials_info = json.load(f)
                self._credentials = Credentials.from_service_account_info(credentials_info, scopes=self.scopes)
            else:
                raise ValueError("Google 서비스 계정 JSON이 필요합니다.")
            self.service = build('sheets', 'v4', credentials=self._credentials)
            logger.info("Google Sheets API 서비스 초기화 완료")
        except Exception as e:
            logger.error(f"Google Sheets 인증에 실패했습니다: {e}")
            raise

    async def test_connection(self) -> bool:
        try:
            result = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            title = result.get('properties', {}).get('title', 'Unknown')
            logger.info(f"Google Sheets 연결 성공: {title}")
            print(f"✅ Google Sheets 연결 성공: {title}")
            return True
        except Exception as e:
            logger.error(f"Google Sheets 연결 테스트 실패: {e}")
            print(f"❌ Google Sheets 연결 실패: {e}")
            return False

    # ================== 아톰 DB 관리 ==================
    async def get_atoms(self) -> List[Dict]:
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.ATOM_DB}!A:Q"
            ).execute()
            values = result.get('values', [])
            if not values:
                logger.warning("아톰 DB가 비어있습니다")
                return []
            headers = values[0]
            atoms = []
            for row in values[1:]:
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
        try:
            current_atoms = await self.get_atoms()
            next_row = len(current_atoms) + 2
            values = [
                atom_data.get('Atom_ID', ''),
                atom_data.get('Atom_Name', ''),
                atom_data.get('Description', ''),
                atom_data.get('Output_Column_Name', ''),
                atom_data.get('Category', ''),
                atom_data.get('Source_Reference', ''),
                atom_data.get('Timeframe', '')
            ]
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
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.MOLECULE_DB}!A:Q"
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
                if molecule.get('Required_Atom_IDs'):
                    molecule['Required_Atom_IDs'] = [
                        atom_id.strip()
                        for atom_id in molecule['Required_Atom_IDs'].split(',')
                        if atom_id.strip()
                    ]
                else:
                    molecule['Required_Atom_IDs'] = []
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
        try:
            current_molecules = await self.get_molecules()
            next_row = len(current_molecules) + 2
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

    async def update_molecule_info(self, molecule_id: str, update_data: Dict) -> bool:
        """Molecule_DB에서 특정 Molecule_ID의 정보 업데이트"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.MOLECULE_DB}!A:Q"
            ).execute()
            values = result.get('values', [])
            headers = values[0]
            for i, row in enumerate(values[1:], start=2):
                while len(row) < len(headers):
                    row.append('')
                if row[0] == molecule_id:
                    # 업데이트할 값 적용
                    for key, val in update_data.items():
                        if key in headers:
                            idx = headers.index(key)
                            row[idx] = val
                    body = {"values": [row]}
                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f"{self.MOLECULE_DB}!A{i}",
                        valueInputOption="RAW",
                        body=body
                    ).execute()
                    logger.info(f"Molecule_DB 업데이트: {molecule_id}")
                    return True
            logger.warning(f"업데이트할 분자 ID를 찾지 못함: {molecule_id}")
            return False
        except Exception as e:
            logger.error(f"Molecule_DB 업데이트 실패: {e}")
            return False

    # ================== SIDB 관리 ==================
    async def append_sidb_record(self, signal_data: Dict) -> bool:
        try:
            if 'Instance_ID' not in signal_data:
                signal_data['Instance_ID'] = str(uuid.uuid4())
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
                try:
                    record_time = datetime.fromisoformat(
                        record.get('Timestamp_UTC', '').replace('Z', '+00:00')
                    ).timestamp()
                    if record_time < cutoff_time:
                        continue
                except:
                    continue
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
        try:
            current_data = await self.get_performance_data()
            target_row = None
            for i, record in enumerate(current_data):
                if record.get('Molecule_ID') == molecule_id:
                    target_row = i + 2
                    break
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
        try:
            if 'Prediction_ID' not in prediction_data:
                prediction_data['Prediction_ID'] = str(uuid.uuid4())
            if 'Timestamp_UTC' not in prediction_data:
                prediction_data['Timestamp_UTC'] = datetime.now(timezone.utc).isoformat()
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
                if not record.get('Actual_Outcome', '').strip():
                    pending_predictions.append(record)
            logger.info(f"미완료 예측 {len(pending_predictions)}개 조회")
            return pending_predictions
        except Exception as e:
            logger.error(f"미완료 예측 조회 실패: {e}")
            return []

    async def update_prediction_outcome(self, prediction_id: str, actual_outcome: str,
                                        human_feedback: str = '', ai_review_summary: str = '') -> bool:
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.PREDICTION_NOTES}!A:K"
            ).execute()
            values = result.get('values', [])
            if len(values) < 2:
                return False
            headers = values[0]
            target_row = None
            for i, row in enumerate(values[1:]):
                while len(row) < len(headers):
                    row.append('')
                if row[0] == prediction_id:
                    target_row = i + 2
                    break
            if target_row is None:
                logger.error(f"예측 ID {prediction_id}를 찾을 수 없습니다")
                return False
            updates = [
                {
                    'range': f"{self.PREDICTION_NOTES}!G{target_row}",
                    'values': [[actual_outcome]]
                },
                {
                    'range': f"{self.PREDICTION_NOTES}!H{target_row}",
                    'values': [[human_feedback]]
                },
                {
                    'range': f"{self.PREDICTION_NOTES}!I{target_row}",
                    'values': [[ai_review_summary]]
                }
            ]
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

    # ================== Quarantine_Queue 관리 ==================
    async def get_quarantine_queue(self) -> List[Dict]:
        """Quarantine_Queue에서 검증 대기중인 분자 목록 가져오기"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.QUARANTINE_QUEUE}!A:Z"
            ).execute()
            values = result.get('values', [])
            if not values or len(values) < 2:
                return []
            headers = values[0]
            queue_data = []
            for row in values[1:]:
                while len(row) < len(headers):
                    row.append('')
                item = dict(zip(headers, row))
                queue_data.append(item)
            logger.info(f"Quarantine_Queue에서 {len(queue_data)}개 전략 로드")
            return queue_data
        except Exception as e:
            logger.error(f"Quarantine_Queue 로드 실패: {e}")
            return []

    # ================== WFO_Results 관리 ==================
    async def save_wfo_result(self, result_data: Dict) -> bool:
        """WFO 결과를 WFO_Results 시트에 저장"""
        try:
            result_data = {k: v for k, v in result_data.items()}
            current_results = await self.get_wfo_results()
            next_row = len(current_results) + 2
            # 표 4.1: Result_ID, Molecule_ID, WFO_Efficiency 등
            values = [
                result_data.get('Result_ID', str(uuid.uuid4())),
                result_data.get('Molecule_ID', ''),
                result_data.get('Test_Date', datetime.now(timezone.utc).isoformat()),
                result_data.get('WFO_Efficiency', 0.0),
                result_data.get('Validation_Status', ''),
                result_data.get('Simple_Return', 0.0),
                result_data.get('WFO_Return', 0.0),
                result_data.get('Max_Drawdown', 0.0),
                result_data.get('Sharpe_Ratio', 0.0),
                result_data.get('Parameter_Stability_Score', 0.0)
            ]
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.WFO_RESULTS}!A:J",
                valueInputOption='RAW',
                body={'values': [values]}
            ).execute()
            logger.info(f"WFO 결과 저장: {result_data.get('Molecule_ID')}")
            return True
        except Exception as e:
            logger.error(f"WFO 결과 저장 실패: {e}")
            return False

    async def get_wfo_results(self) -> List[Dict]:
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.WFO_RESULTS}!A:J"
            ).execute()
            values = result.get('values', [])
            if len(values) < 2:
                return []
            headers = values[0]
            results = []
            for row in values[1:]:
                while len(row) < len(headers):
                    row.append('')
                item = dict(zip(headers, row))
                results.append(item)
            logger.info(f"WFO_Results {len(results)}개 로드")
            return results
        except Exception as e:
            logger.error(f"WFO_Results 조회 실패: {e}")
            return []

    # ================== Approval_Log 관리 ==================
    async def log_approval_action(self, log_data: Dict) -> bool:
        """분자 승인/거부 기록을 Approval_Log에 저장"""
        try:
            current_logs = await self.get_approval_logs()
            next_row = len(current_logs) + 2
            # 표 4.1: Log_ID, Molecule_ID, Action, Reviewer, Review_Notes, Previous_Status, New_Status
            values = [
                log_data.get('Log_ID', str(uuid.uuid4())),
                log_data.get('Molecule_ID', ''),
                log_data.get('Action', ''),
                log_data.get('Reviewer', ''),
                log_data.get('Review_Notes', ''),
                log_data.get('Previous_Status', ''),
                log_data.get('New_Status', ''),
                log_data.get('Timestamp', datetime.now(timezone.utc).isoformat())
            ]
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.APPROVAL_LOG}!A:H",
                valueInputOption='RAW',
                body={'values': [values]}
            ).execute()
            logger.info(f"Approval_Log 기록 추가: {log_data.get('Molecule_ID')}")
            return True
        except Exception as e:
            logger.error(f"Approval_Log 기록 추가 실패: {e}")
            return False

    async def get_approval_logs(self) -> List[Dict]:
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.APPROVAL_LOG}!A:H"
            ).execute()
            values = result.get('values', [])
            if len(values) < 2:
                return []
            headers = values[0]
            logs = []
            for row in values[1:]:
                while len(row) < len(headers):
                    row.append('')
                item = dict(zip(headers, row))
                logs.append(item)
            logger.info(f"Approval_Log {len(logs)}개 로드")
            return logs
        except Exception as e:
            logger.error(f"Approval_Log 조회 실패: {e}")
            return []

    # ================== Risk_Alerts 관리 ==================
    async def save_risk_alert(self, alert_data: Dict) -> bool:
        """RiskMonitor의 자동 개입 조치를 Risk_Alerts에 기록"""
        try:
            current_alerts = await self.get_risk_alerts()
            next_row = len(current_alerts) + 2
            # 표 4.1: Alert_ID, Molecule_ID, Alert_Type, Auto_Action 등
            values = [
                alert_data.get('Alert_ID', str(uuid.uuid4())),
                alert_data.get('Molecule_ID', ''),
                alert_data.get('Alert_Type', ''),
                alert_data.get('Alert_Level', ''),
                alert_data.get('Current_Drawdown', 0.0),
                alert_data.get('Alert_Details', ''),
                alert_data.get('Triggered_Date', datetime.now(timezone.utc).isoformat()),
                alert_data.get('Auto_Action', '')
            ]
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.RISK_ALERTS}!A:H",
                valueInputOption='RAW',
                body={'values': [values]}
            ).execute()
            logger.info(f"Risk_Alerts 기록 추가: {alert_data.get('Molecule_ID')}")
            return True
        except Exception as e:
            logger.error(f"Risk_Alerts 기록 추가 실패: {e}")
            return False

    async def get_risk_alerts(self) -> List[Dict]:
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.RISK_ALERTS}!A:H"
            ).execute()
            values = result.get('values', [])
            if len(values) < 2:
                return []
            headers = values[0]
            alerts = []
            for row in values[1:]:
                while len(row) < len(headers):
                    row.append('')
                item = dict(zip(headers, row))
                alerts.append(item)
            logger.info(f"Risk_Alerts {len(alerts)}개 로드")
            return alerts
        except Exception as e:
            logger.error(f"Risk_Alerts 조회 실패: {e}")
            return []

    # ================== Version_History 관리 ==================
    async def save_version_record(self, version_data: Dict) -> bool:
        """VersionController의 변경 이력을 Version_History에 기록"""
        try:
            current_versions = await self.get_version_history()
            next_row = len(current_versions) + 2
            # 표 4.1: History_ID, Molecule_ID, Changed_Fields, Old_Values, New_Values, Changed_By, Changed_Date, Change_Reason
            values = [
                version_data.get('History_ID', str(uuid.uuid4())),
                version_data.get('Molecule_ID', ''),
                version_data.get('Changed_Fields', ''),
                version_data.get('Old_Values', ''),
                version_data.get('New_Values', ''),
                version_data.get('Changed_By', ''),
                version_data.get('Changed_Date', datetime.now(timezone.utc).isoformat()),
                version_data.get('Change_Reason', '')
            ]
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.VERSION_HISTORY}!A:H",
                valueInputOption='RAW',
                body={'values': [values]}
            ).execute()
            logger.info(f"Version_History 기록 추가: {version_data.get('Molecule_ID')}")
            return True
        except Exception as e:
            logger.error(f"Version_History 기록 추가 실패: {e}")
            return False

    async def get_version_history(self) -> List[Dict]:
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.VERSION_HISTORY}!A:H"
            ).execute()
            values = result.get('values', [])
            if len(values) < 2:
                return []
            headers = values[0]
            versions = []
            for row in values[1:]:
                while len(row) < len(headers):
                    row.append('')
                item = dict(zip(headers, row))
                versions.append(item)
            logger.info(f"Version_History {len(versions)}개 로드")
            return versions
        except Exception as e:
            logger.error(f"Version_History 조회 실패: {e}")
            return []

    # ================== 유틸리티 메서드 ==================
    async def get_sheet_info(self) -> Dict:
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
        try:
            backup_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'atoms': await self.get_atoms(),
                'molecules': await self.get_molecules(),
                'sidb_recent': await self.get_recent_sidb_records(hours=168),
                'performance': await self.get_performance_data(),
                'pending_predictions': await self.get_pending_predictions()
            }
            logger.info("데이터 백업 완료")
            return backup_data
        except Exception as e:
            logger.error(f"데이터 백업 실패: {e}")
            return {}

# 테스트 코드 (직접 실행할 경우만)
if __name__ == "__main__":
    async def test_sheets_service():
        spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        if not spreadsheet_id:
            print("GOOGLE_SPREADSHEET_ID 환경 변수가 설정되지 않았습니다.")
            return
        sheets_service = SheetsService(
            spreadsheet_id=spreadsheet_id,
            service_account_json=service_account_json
        )
        if await sheets_service.test_connection():
            print("✅ Google Sheets 연결 성공")
            atoms = await sheets_service.get_atoms()
            print(f"📊 아톰 {len(atoms)}개 로드")
            molecules = await sheets_service.get_molecules()
            print(f"🧬 분자 {len(molecules)}개 로드")
        else:
            print("❌ Google Sheets 연결 실패")

    asyncio.run(test_sheets_service())
