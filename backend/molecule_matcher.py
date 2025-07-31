"""
molecule_matcher.py - 분자 매칭 및 전략 신호 생성 엔진
AI 트레이딩 어시스턴트 V5.1의 핵심 분자 매칭 및 예측/성과 기록 모듈

주요 기능:
- 최근 아톰 신호 조합을 분자(DB) 정의와 실시간으로 매칭
- 필수 아톰 충족 시 분자 신호 생성 (등급 산정 포함)
- 예측(분자) 발생 시 예측/오답노트, SIDB, 성과 대시보드 자동 기록
- 백테스팅 준비를 위한 신호 이력 제공
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple

from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)

class MoleculeMatchResult:
    def __init__(self,
                 matched: bool,
                 molecule_id: str = "",
                 molecule_name: str = "",
                 matched_atoms: List[str] = None,
                 unmatched_atoms: List[str] = None,
                 match_ratio: float = 0.0,
                 signal_grade: str = "",
                 timestamp_utc: str = "",
                 triggered: bool = False):
        self.matched = matched
        self.molecule_id = molecule_id
        self.molecule_name = molecule_name
        self.matched_atoms = matched_atoms or []
        self.unmatched_atoms = unmatched_atoms or []
        self.match_ratio = match_ratio
        self.signal_grade = signal_grade
        self.timestamp_utc = timestamp_utc or datetime.now(timezone.utc).isoformat()
        self.triggered = triggered

    def to_dict(self):
        return {
            "matched": self.matched,
            "molecule_id": self.molecule_id,
            "molecule_name": self.molecule_name,
            "matched_atoms": self.matched_atoms,
            "unmatched_atoms": self.unmatched_atoms,
            "match_ratio": self.match_ratio,
            "signal_grade": self.signal_grade,
            "timestamp_utc": self.timestamp_utc,
            "triggered": self.triggered,
        }

class MoleculeMatcher:
    """
    분자 매칭 로직
    - 아톰 신호 스트림을 받아 분자 정의와 실시간으로 매칭
    - 예상 신호 기록 및 실적 업데이트
    """

    def __init__(self, sheets_service: Optional[SheetsService] = None):
        self.sheets_service = sheets_service
        self.molecules_cache = {}
        self.last_matched_timestamp = {}
        self.recent_signals = []  # [{atom_id, timestamp_utc, ...}]
        logger.info("MoleculeMatcher 초기화 완료")

    async def initialize(self):
        if self.sheets_service:
            await self.load_molecules_from_sheets()
        else:
            self.load_demo_molecules()
        logger.info(f"분자 정의 {len(self.molecules_cache)}개 로드 완료")

    # molecule_matcher.py의 load_molecules_from_sheets 메서드 수정
async def load_molecules_from_sheets(self):
    """Google Sheets에서 분자 정의 로드 - active 상태만 로드"""
    try:
        molecule_data = await self.sheets_service.get_molecules()
        self.molecules_cache = {}
        
        for molecule in molecule_data:
            molecule_id = molecule.get('Molecule_ID')
            molecule_status = molecule.get('Status', '').lower()
            
            # ⭐ 승인 로직: active 상태인 분자만 로드
            if molecule_id and molecule_status == 'active':
                required_atoms = molecule.get('Required_Atom_IDs', [])
                if isinstance(required_atoms, str):
                    required_atoms = [aid.strip() for aid in required_atoms.split(',') if aid.strip()]

                self.molecules_cache[molecule_id] = {
                    'id': molecule_id,
                    'name': molecule.get('Molecule_Name', ''),
                    'category': molecule.get('Category', ''),
                    'required_atoms': required_atoms,
                    'match_threshold': float(molecule.get('Match_Threshold_%', 100)),
                    'translation_notes': molecule.get('Translation_Notes', ''),
                    'entry_sl_tp': molecule.get('Entry_SL_TP', ''),
                    'status': molecule_status
                }

        logger.info(f"활성 분자 {len(self.molecules_cache)}개 로드 완료")

    except Exception as e:
        logger.error(f"Google Sheets 분자 로드 실패: {e}")
        raise

    def load_demo_molecules(self):
        self.molecules_cache = {
            'LOGIC-EXP-004': {
                'id': 'LOGIC-EXP-004',
                'name': '장 초반 정배열 후 1분봉 20EMA 첫 눌림목',
                'category': '반등/진입',
                'required_atoms': ['CTX-009', 'TRG-008', 'STR-003'],
                'match_threshold': 100.0,
                'translation_notes': '...',
                'entry_sl_tp': ''
            }
        }

    def update_recent_atoms(self, atom_signal: Dict[str, Any], window_minutes: int = 30):
        """최근 N분 이내 아톰 신호 목록을 업데이트"""
        now = datetime.fromisoformat(atom_signal['timestamp_utc'].replace('Z', '+00:00'))
        self.recent_signals.append(atom_signal)
        # 시간창 필터 적용
        cutoff = now - timedelta(minutes=window_minutes)
        self.recent_signals = [
            a for a in self.recent_signals
            if datetime.fromisoformat(a['timestamp_utc'].replace('Z', '+00:00')) >= cutoff
        ]
        # 최대 200개로 슬라이딩 윈도우 유지(성능)
        if len(self.recent_signals) > 200:
            self.recent_signals = self.recent_signals[-200:]

    def find_molecule_matches(self) -> List[MoleculeMatchResult]:
        """
        최근 N분 내의 아톰 조합을 분자 정의와 매칭
        - 완전일치 또는 부분일치(매치율, 등급 산정)
        - 마지막 신호 이후 중복방지 설정(쿨다운)
        """
        now_utc = datetime.now(timezone.utc)
        occurred_results = []
        # 최근 신호 중 가장 최신의 timestamp_utc 기준으로 수행
        recent_atoms = [a['atom_id'] for a in self.recent_signals]
        recent_atoms_set = set(recent_atoms)
        # 각 분자 정의별 매칭
        for mid, molecule in self.molecules_cache.items():
            required_set = set(molecule['required_atoms'])
            matched_atoms = list(required_set & recent_atoms_set)
            unmatched_atoms = list(required_set - recent_atoms_set)
            match_ratio = 100.0 * len(matched_atoms) / len(required_set) if required_set else 0.0
            # 마지막 신호 이후 쿨다운(중복 방지)
            last_time = self.last_matched_timestamp.get(mid)
            triggered = False
            if match_ratio >= molecule.get('match_threshold', 100.0):
                # 매치: 완전일치 또는 부분일치(문턱값 이상)
                if not last_time or (now_utc - last_time).total_seconds() > 60:
                    triggered = True
                    self.last_matched_timestamp[mid] = now_utc
            grade = self.get_signal_grade(match_ratio)
            occurred_results.append(MoleculeMatchResult(
                matched=grade in ['A++', 'A+', 'A'],
                molecule_id=mid,
                molecule_name=molecule['name'],
                matched_atoms=matched_atoms,
                unmatched_atoms=unmatched_atoms,
                match_ratio=match_ratio,
                signal_grade=grade,
                triggered=triggered
            ))
        return occurred_results

    async def on_atom_signal(self, atom_signal: Dict[str, Any]):
        """
        새 아톰 신호가 발생했을 때 호출됨
        - 최근 아톰 스트림 업데이트
        - 분자 매칭
        - 신호 발생시 기록 및 콜백
        """
        self.update_recent_atoms(atom_signal)
        matches = self.find_molecule_matches()
        for match in matches:
            if match.triggered and match.matched:
                logger.info(f"분자 매칭 완료: {match.molecule_id} (등급: {match.signal_grade})")
                # Google Sheets 예측 기록
                await self.record_prediction(
                    atom_signal['ticker'],
                    match.molecule_id,
                    match.molecule_name,
                    match.matched_atoms,
                    match.signal_grade
                )

    async def record_prediction(self, ticker, molecule_id, molecule_name, key_atoms, grade):
        """
        예측/오답노트, SIDB, 성과 대시보드에 신호 기록
        """
        if not self.sheets_service:
            logger.info(f"예측 기록(Sheets 생략): {ticker} - {molecule_id}")
            return
        # 1. 예측/오답노트 기록
        prediction_data = {
            'Prediction_ID': "",
            'Timestamp_UTC': datetime.now(timezone.utc).isoformat(),
            'Ticker': ticker,
            'Triggered_Molecule_ID': molecule_id,
            'Prediction_Summary': molecule_name,
            'Key_Atoms_Found': key_atoms,
            'Actual_Outcome': "",
            'Human_Feedback': "",
            'AI_Review_Summary': "",
            'Position_Size': "",
            'Overnight_Permission': "",
        }
        await self.sheets_service.add_prediction_record(prediction_data)
        # 2. 분자 신호 이벤트 기록 등은 필요에 따라 확장

    @staticmethod
    def get_signal_grade(match_ratio: float) -> str:
        """매치율 등급화 (가중치 활용 가능)"""
        if match_ratio >= 100.0:
            return 'A++'
        elif match_ratio >= 85.0:
            return 'A+'
        elif match_ratio >= 70.0:
            return 'A'
        elif match_ratio >= 55.0:
            return 'B+'
        elif match_ratio >= 40.0:
            return 'B'
        else:
            return 'C'

    # 유틸/진단 용도
    def get_recent_signal_history(self) -> List[Dict]:
        return self.recent_signals.copy()

# ========== 사용 예시 및 자가진단 ==========

if __name__ == "__main__":
    import asyncio
    from datetime import timedelta

    async def test_molecule_matcher():
        matcher = MoleculeMatcher()
        await matcher.initialize()

        print("분자 매칭기 자가진단 시작")
        now = datetime.now(timezone.utc)
        # 아톰 시퀀스 시뮬레이션
        for i, aid in enumerate(["CTX-009", "TRG-008", "STR-003"]):
            matcher.update_recent_atoms({
                "atom_id": aid,
                "ticker": "AAPL",
                "timestamp_utc": (now + timedelta(seconds=i*10)).isoformat(),
            })

        results = matcher.find_molecule_matches()
        for res in results:
            print(f"분자: {res.molecule_id}, 매치률: {res.match_ratio:.1f}%, 등급: {res.signal_grade}, 트리거: {res.triggered}")

    asyncio.run(test_molecule_matcher())
