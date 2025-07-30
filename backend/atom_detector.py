"""
atom_detector.py - 실제 아톰 탐지 로직 엔진
AI 트레이딩 어시스턴트 V5.1의 핵심 아톰 탐지 모듈

주요 기능:
- 실시간 시장 데이터에서 아톰 패턴 탐지
- 다중 시간대 분석 (1분, 5분, 1시간)
- 컨버전스(겹침) 탐지 및 파생 아톰 생성
- 아톰 신호 등급 산정 및 SIDB 기록
- 핵심 매매 시간대 필터링 (21:00-00:30 KST)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass
import yfinance as yf

from technical_indicators import TechnicalIndicators
from services.sheets_service import SheetsService

# 로깅 설정
logger = logging.getLogger(__name__)

@dataclass
class AtomSignal:
    """아톰 신호 데이터 클래스"""
    atom_id: str
    atom_name: str
    ticker: str
    timeframe: str
    price_at_signal: float
    volume_at_signal: int
    grade: str
    timestamp_utc: str
    context_atoms_active: List[str]
    confidence_score: float
    additional_data: Dict[str, Any] = None

class AtomDetector:
    """실제 아톰 탐지 로직 클래스"""
    
    def __init__(self, sheets_service: Optional[SheetsService] = None):
        """
        아톰 탐지기 초기화
        
        Args:
            sheets_service: Google Sheets 서비스 (선택사항)
        """
        self.sheets_service = sheets_service
        self.technical_indicators = TechnicalIndicators()
        
        # 아톰 정의 캐시
        self.atoms_cache = {}
        self.molecules_cache = {}
        
        # 탐지 설정
        self.min_volume_threshold = 50000  # 최소 거래량 기준
        self.convergence_threshold = 0.01  # 1% 이내 컨버전스 기준
        self.core_trading_hours = {
            'start_hour': 21,  # 21:00 KST
            'end_hour': 0,     # 00:30 KST (다음날)
            'end_minute': 30
        }
        
        # 활성 컨텍스트 아톰 추적
        self.active_context_atoms = {}
        
        # 통계
        self.atoms_detected_count = 0
        self.signals_generated_count = 0
        
        logger.info("AtomDetector 초기화 완료")
    
    async def initialize(self):
        """아톰 탐지기 초기화 - 아톰 및 분자 정의 로드"""
        try:
            if self.sheets_service:
                # Google Sheets에서 아톰 및 분자 정의 로드
                await self.load_atoms_from_sheets()
                await self.load_molecules_from_sheets()
            else:
                # 로컬 더미 데이터 로드
                self.load_demo_atoms()
                self.load_demo_molecules()
            
            logger.info(f"아톰 탐지기 초기화 완료: {len(self.atoms_cache)}개 아톰, {len(self.molecules_cache)}개 분자")
            
        except Exception as e:
            logger.error(f"아톰 탐지기 초기화 실패: {e}")
            # 폴백: 데모 데이터 사용
            self.load_demo_atoms()
            self.load_demo_molecules()
    
    async def load_atoms_from_sheets(self):
        """Google Sheets에서 아톰 정의 로드"""
        try:
            atoms_data = await self.sheets_service.get_atoms()
            self.atoms_cache = {}
            
            for atom in atoms_data:
                atom_id = atom.get('Atom_ID')
                if atom_id:
                    self.atoms_cache[atom_id] = {
                        'id': atom_id,
                        'name': atom.get('Atom_Name', ''),
                        'description': atom.get('Description', ''),
                        'category': atom.get('Category', ''),
                        'timeframe': atom.get('Timeframe', '1m'),
                        'output_column': atom.get('Output_Column_Name', ''),
                        'source_reference': atom.get('Source_Reference', '')
                    }
            
            logger.info(f"Google Sheets에서 {len(self.atoms_cache)}개 아톰 로드 완료")
            
        except Exception as e:
            logger.error(f"Google Sheets 아톰 로드 실패: {e}")
            raise
    
    async def load_molecules_from_sheets(self):
        """Google Sheets에서 분자 정의 로드"""
        try:
            molecules_data = await self.sheets_service.get_molecules()
            self.molecules_cache = {}
            
            for molecule in molecules_data:
                molecule_id = molecule.get('Molecule_ID')
                if molecule_id:
                    required_atoms = molecule.get('Required_Atom_IDs', '')
                    if isinstance(required_atoms, str):
                        required_atoms = [atom.strip() for atom in required_atoms.split(',') if atom.strip()]
                    
                    self.molecules_cache[molecule_id] = {
                        'id': molecule_id,
                        'name': molecule.get('Molecule_Name', ''),
                        'category': molecule.get('Category', ''),
                        'required_atoms': required_atoms,
                        'match_threshold': float(molecule.get('Match_Threshold_%', 100)),
                        'translation_notes': molecule.get('Translation_Notes', ''),
                        'entry_sl_tp': molecule.get('Entry_SL_TP', '')
                    }
            
            logger.info(f"Google Sheets에서 {len(self.molecules_cache)}개 분자 로드 완료")
            
        except Exception as e:
            logger.error(f"Google Sheets 분자 로드 실패: {e}")
            raise
    
    def load_demo_atoms(self):
        """데모 아톰 데이터 로드"""
        self.atoms_cache = {
            'CTX-001': {
                'id': 'CTX-001',
                'name': '촉매_A++등급',
                'description': '뉴스의 등급이 A++로 분류됨',
                'category': 'Context',
                'timeframe': '',
                'output_column': 'is_catalyst_Aplusplus',
                'source_reference': 'LOGIC-EXP-010'
            },
            'STR-003': {
                'id': 'STR-003',
                'name': '1분_20EMA_지지',
                'description': '1분봉 캔들 저가가 1분봉 20EMA에 1% 이내 근접하며 지지',
                'category': 'Structural',
                'timeframe': '1m',
                'output_column': 'is_supported_at_1m_ema20',
                'source_reference': 'LOGIC-EXP-004'
            },
            'TRG-003': {
                'id': 'TRG-003',
                'name': '거래량_폭발',
                'description': '일정 기간 평균 대비 상대 거래량이 500% 이상 급증',
                'category': 'Trigger',
                'timeframe': '1m',
                'output_column': 'triggered_volume_spike',
                'source_reference': 'LOGIC-EXP-001'
            },
            'DRV-001': {
                'id': 'DRV-001',
                'name': '컨버전스_1m20_5m100',
                'description': '1분 20EMA와 5분 100EMA가 1% 가격 범위 내에서 겹침',
                'category': 'Derived',
                'timeframe': '1m,5m',
                'output_column': 'is_conv_1m20_5m100',
                'source_reference': 'LOGIC-EXP-002'
            }
        }
        
        logger.info(f"데모 아톰 {len(self.atoms_cache)}개 로드 완료")
    
    def load_demo_molecules(self):
        """데모 분자 데이터 로드"""
        self.molecules_cache = {
            'LOGIC-EXP-004': {
                'id': 'LOGIC-EXP-004',
                'name': '장 초반 정배열 후 1분봉 20EMA 첫 눌림목',
                'category': '반등/진입',
                'required_atoms': ['CTX-009', 'TRG-008', 'STR-003'],
                'match_threshold': 100.0,
                'translation_notes': '장기 추세가 나쁘더라도, 장 초반 강력한 거래량과 함께 형성된 정배열의 첫 번째 20EMA 눌림목은 신뢰도가 높음',
                'entry_sl_tp': ''
            }
        }
        
        logger.info(f"데모 분자 {len(self.molecules_cache)}개 로드 완료")
    
    def is_core_trading_hours(self, timestamp: datetime) -> bool:
        """핵심 매매 시간대 확인 (21:00-00:30 KST)"""
        try:
            # UTC를 KST로 변환 (UTC+9)
            kst_time = timestamp + timedelta(hours=9)
            hour = kst_time.hour
            minute = kst_time.minute
            
            # 21:00-23:59 or 00:00-00:30
            return (hour >= 21) or (hour == 0 and minute <= 30)
            
        except Exception as e:
            logger.error(f"시간대 확인 오류: {e}")
            return True  # 오류 시 기본적으로 허용
    
    async def detect_atoms_in_data(self, ticker: str, ohlcv_data_dict: Dict[str, pd.DataFrame], 
                                 current_time: Optional[datetime] = None) -> List[AtomSignal]:
        """
        주어진 OHLCV 데이터에서 아톰 탐지
        
        Args:
            ticker: 종목 심볼
            ohlcv_data_dict: 시간대별 OHLCV 데이터 {'1m': df, '5m': df, '1h': df}
            current_time: 현재 시간 (None이면 최신 데이터 시간 사용)
            
        Returns:
            탐지된 아톰 신호 리스트
        """
        try:
            detected_atoms = []
            
            # 현재 시간 설정
            if current_time is None:
                current_time = datetime.now(timezone.utc)
            
            # 핵심 매매 시간대 확인
            if not self.is_core_trading_hours(current_time):
                logger.debug(f"핵심 매매 시간대가 아님: {current_time}")
                return detected_atoms
            
            # 시간대별 데이터에 기술적 지표 계산
            processed_data = {}
            for timeframe, df in ohlcv_data_dict.items():
                if not df.empty:
                    # 핵심 매매 시간대 데이터만 필터링
                    filtered_df = self.technical_indicators.filter_market_hours_data(df)
                    if not filtered_df.empty:
                        processed_data[timeframe] = self.technical_indicators.calculate_all_indicators(
                            filtered_df, timeframe
                        )
            
            if not processed_data:
                logger.warning(f"필터링된 데이터가 없음: {ticker}")
                return detected_atoms
            
            # 1. Context 아톰 탐지
            context_atoms = await self.detect_context_atoms(ticker, processed_data, current_time)
            detected_atoms.extend(context_atoms)
            
            # 2. Structural 아톰 탐지  
            structural_atoms = await self.detect_structural_atoms(ticker, processed_data, current_time)
            detected_atoms.extend(structural_atoms)
            
            # 3. Trigger 아톰 탐지
            trigger_atoms = await self.detect_trigger_atoms(ticker, processed_data, current_time)
            detected_atoms.extend(trigger_atoms)
            
            # 4. Derived 아톰 탐지 (컨버전스)
            derived_atoms = await self.detect_derived_atoms(ticker, processed_data, current_time)
            detected_atoms.extend(derived_atoms)
            
            # 5. 중복 제거 및 신호 등급 최종 산정
            final_atoms = self.deduplicate_and_grade_atoms(detected_atoms)
            
            # 6. SIDB에 기록
            for atom_signal in final_atoms:
                await self.record_atom_to_sidb(atom_signal)
            
            self.atoms_detected_count += len(final_atoms)
            
            if final_atoms:
                logger.info(f"{ticker}에서 {len(final_atoms)}개 아톰 탐지: {[atom.atom_id for atom in final_atoms]}")
            
            return final_atoms
            
        except Exception as e:
            logger.error(f"아톰 탐지 오류 ({ticker}): {e}")
            return []
    
    async def detect_context_atoms(self, ticker: str, processed_data: Dict[str, pd.DataFrame], 
                                 current_time: datetime) -> List[AtomSignal]:
        """Context 카테고리 아톰 탐지"""
        context_atoms = []
        
        try:
            # Context 아톰들 필터링
            context_atom_defs = {k: v for k, v in self.atoms_cache.items() if v['category'] == 'Context'}
            
            for atom_id, atom_def in context_atom_defs.items():
                detected = False
                confidence_score = 0.0
                additional_data = {}
                
                # CTX-001: 촉매_A++등급 (시뮬레이션)
                if atom_id == 'CTX-001':
                    # 실제로는 뉴스 API 등에서 확인해야 함
                    # 여기서는 특정 조건으로 시뮬레이션
                    detected = self.simulate_catalyst_grade(ticker, 'A++')
                    confidence_score = 0.9 if detected else 0.0
                
                # CTX-010: 시장_주도주 (거래량 및 변동성 기반)
                elif atom_id == 'CTX-010':
                    if '1m' in processed_data:
                        df = processed_data['1m']
                        if len(df) >= 10:
                            # 최근 거래량이 평균의 10배 이상이고 상승률 5% 이상
                            recent_volume = df['Volume'].iloc[-1]
                            avg_volume = df['Volume'].iloc[-10:-1].mean()
                            price_change = (df['Close'].iloc[-1] / df['Close'].iloc[-10] - 1) * 100
                            
                            if recent_volume > avg_volume * 10 and price_change > 5:
                                detected = True
                                confidence_score = min(0.95, recent_volume / (avg_volume * 15))
                                additional_data = {
                                    'volume_ratio': recent_volume / avg_volume,
                                    'price_change_pct': price_change
                                }
                
                # CTX-015: 나스닥_상승추세 (QQQ 기반, 시뮬레이션)
                elif atom_id == 'CTX-015':
                    # 실제로는 QQQ 데이터를 가져와야 함
                    detected = self.simulate_nasdaq_trend()
                    confidence_score = 0.7 if detected else 0.0
                
                if detected:
                    atom_signal = AtomSignal(
                        atom_id=atom_id,
                        atom_name=atom_def['name'],
                        ticker=ticker,
                        timeframe=atom_def.get('timeframe', ''),
                        price_at_signal=processed_data['1m']['Close'].iloc[-1] if '1m' in processed_data else 0.0,
                        volume_at_signal=int(processed_data['1m']['Volume'].iloc[-1]) if '1m' in processed_data else 0,
                        grade=self.calculate_atom_grade(confidence_score),
                        timestamp_utc=current_time.isoformat(),
                        context_atoms_active=[],
                        confidence_score=confidence_score,
                        additional_data=additional_data
                    )
                    
                    context_atoms.append(atom_signal)
                    
                    # 활성 컨텍스트 아톰으로 등록 (1시간 유효)
                    expiry_time = current_time + timedelta(hours=1)
                    self.active_context_atoms[atom_id] = {
                        'ticker': ticker,
                        'expiry_time': expiry_time,
                        'confidence_score': confidence_score
                    }
            
        except Exception as e:
            logger.error(f"Context 아톰 탐지 오류: {e}")
        
        return context_atoms
    
    async def detect_structural_atoms(self, ticker: str, processed_data: Dict[str, pd.DataFrame], 
                                    current_time: datetime) -> List[AtomSignal]:
        """Structural 카테고리 아톰 탐지"""
        structural_atoms = []
        
        try:
            # Structural 아톰들 필터링
            structural_atom_defs = {k: v for k, v in self.atoms_cache.items() if v['category'] == 'Structural'}
            
            for atom_id, atom_def in structural_atom_defs.items():
                detected = False
                confidence_score = 0.0
                timeframe = atom_def.get('timeframe', '1m')
                
                # 해당 시간대 데이터가 있는지 확인
                if timeframe not in processed_data:
                    continue
                
                df = processed_data[timeframe]
                if df.empty or len(df) < 2:
                    continue
                
                # STR-003: 1분_20EMA_지지
                if atom_id == 'STR-003':
                    detected = self.technical_indicators.detect_ema_support(df, 20)
                    if detected:
                        current_low = df['Low'].iloc[-1]
                        current_ema = df['EMA_20'].iloc[-1]
                        proximity = abs(current_low - current_ema) / current_ema
                        confidence_score = max(0.5, 1.0 - (proximity / self.convergence_threshold))
                
                # STR-004: 1분_50EMA_지지
                elif atom_id == 'STR-004':
                    detected = self.technical_indicators.detect_ema_support(df, 50)
                    if detected:
                        current_low = df['Low'].iloc[-1]
                        current_ema = df['EMA_50'].iloc[-1]
                        proximity = abs(current_low - current_ema) / current_ema
                        confidence_score = max(0.5, 1.0 - (proximity / self.convergence_threshold))
                
                # STR-007: 1분_VWAP_지지
                elif atom_id == 'STR-007':
                    detected = self.technical_indicators.detect_vwap_support(df)
                    if detected:
                        confidence_score = 0.8
                
                # STR-008: 1분_슈퍼트렌드_지지
                elif atom_id == 'STR-008':
                    detected = self.technical_indicators.detect_supertrend_support(df)
                    if detected:
                        confidence_score = 0.85
                
                # STR-001: 1분_EMA_응축
                elif atom_id == 'STR-001':
                    detected = self.technical_indicators.detect_ema_compression(df, [5, 20], True)
                    if detected:
                        confidence_score = 0.9
                
                if detected:
                    atom_signal = AtomSignal(
                        atom_id=atom_id,
                        atom_name=atom_def['name'],
                        ticker=ticker,
                        timeframe=timeframe,
                        price_at_signal=float(df['Close'].iloc[-1]),
                        volume_at_signal=int(df['Volume'].iloc[-1]),
                        grade=self.calculate_atom_grade(confidence_score),
                        timestamp_utc=current_time.isoformat(),
                        context_atoms_active=self.get_active_context_atoms(ticker),
                        confidence_score=confidence_score
                    )
                    
                    structural_atoms.append(atom_signal)
            
        except Exception as e:
            logger.error(f"Structural 아톰 탐지 오류: {e}")
        
        return structural_atoms
    
    async def detect_trigger_atoms(self, ticker: str, processed_data: Dict[str, pd.DataFrame], 
                                 current_time: datetime) -> List[AtomSignal]:
        """Trigger 카테고리 아톰 탐지"""
        trigger_atoms = []
        
        try:
            # Trigger 아톰들 필터링
            trigger_atom_defs = {k: v for k, v in self.atoms_cache.items() if v['category'] == 'Trigger'}
            
            for atom_id, atom_def in trigger_atom_defs.items():
                detected = False
                confidence_score = 0.0
                timeframe = atom_def.get('timeframe', '1m')
                additional_data = {}
                
                # 해당 시간대 데이터가 있는지 확인
                if timeframe not in processed_data:
                    continue
                
                df = processed_data[timeframe]
                if df.empty or len(df) < 2:
                    continue
                
                # TRG-003: 거래량_폭발
                if atom_id == 'TRG-003':
                    volume_data = self.technical_indicators.detect_volume_explosion(df)
                    detected = volume_data['triggered']
                    if detected:
                        confidence_score = min(0.95, volume_data['volume_ratio'] / 10.0)
                        additional_data = {
                            'volume_ratio': volume_data['volume_ratio'],
                            'volume_grade': volume_data['grade']
                        }
                
                # TRG-001: 1분_VWAP_골든크로스
                elif atom_id == 'TRG-001':
                    detected = self.technical_indicators.detect_vwap_golden_cross(df, 20, 5)
                    if detected:
                        confidence_score = 0.85
                
                # TRG-004: 1분_슈퍼트렌드_돌파
                elif atom_id == 'TRG-004':
                    detected = self.technical_indicators.detect_supertrend_breakout(df)
                    if detected:
                        confidence_score = 0.9
                
                # TRG-006: VWAP_재탈환
                elif atom_id == 'TRG-006':
                    detected = self.technical_indicators.detect_vwap_reclaim(df, 10)
                    if detected:
                        confidence_score = 0.8
                
                # TRG-008: 1분_정배열_형성
                elif atom_id == 'TRG-008':
                    detected = self.technical_indicators.detect_uptrend_array(df, timeframe)
                    if detected:
                        confidence_score = 0.75
                
                if detected and confidence_score > 0.5:  # 최소 신뢰도 기준
                    atom_signal = AtomSignal(
                        atom_id=atom_id,
                        atom_name=atom_def['name'],
                        ticker=ticker,
                        timeframe=timeframe,
                        price_at_signal=float(df['Close'].iloc[-1]),
                        volume_at_signal=int(df['Volume'].iloc[-1]),
                        grade=self.calculate_atom_grade(confidence_score),
                        timestamp_utc=current_time.isoformat(),
                        context_atoms_active=self.get_active_context_atoms(ticker),
                        confidence_score=confidence_score,
                        additional_data=additional_data
                    )
                    
                    trigger_atoms.append(atom_signal)
            
        except Exception as e:
            logger.error(f"Trigger 아톰 탐지 오류: {e}")
        
        return trigger_atoms
    
    async def detect_derived_atoms(self, ticker: str, processed_data: Dict[str, pd.DataFrame], 
                                 current_time: datetime) -> List[AtomSignal]:
        """Derived 카테고리 아톰 탐지 (컨버전스)"""
        derived_atoms = []
        
        try:
            # Derived 아톰들 필터링
            derived_atom_defs = {k: v for k, v in self.atoms_cache.items() if v['category'] == 'Derived'}
            
            for atom_id, atom_def in derived_atom_defs.items():
                detected = False
                confidence_score = 0.0
                
                # DRV-001: 컨버전스_1m20_5m100
                if atom_id == 'DRV-001':
                    if '1m' in processed_data and '5m' in processed_data:
                        detected = self.technical_indicators.detect_convergence_1m20_5m100(
                            processed_data['1m'], processed_data['5m']
                        )
                        if detected:
                            confidence_score = 0.9
                
                # DRV-002: 컨버전스_1m20_슈퍼트렌드
                elif atom_id == 'DRV-002':
                    if '1m' in processed_data:
                        detected = self.technical_indicators.detect_convergence_1m20_supertrend(
                            processed_data['1m']
                        )
                        if detected:
                            confidence_score = 0.85
                
                # DRV-005: 컨버전스_1m50_VWAP_슈퍼트렌드
                elif atom_id == 'DRV-005':
                    if '1m' in processed_data:
                        detected = self.technical_indicators.detect_convergence_1m50_vwap_supertrend(
                            processed_data['1m']
                        )
                        if detected:
                            confidence_score = 0.95  # 3중 컨버전스는 높은 신뢰도
                
                if detected:
                    df_1m = processed_data.get('1m')
                    atom_signal = AtomSignal(
                        atom_id=atom_id,
                        atom_name=atom_def['name'],
                        ticker=ticker,
                        timeframe='1m,5m',  # 다중 시간대
                        price_at_signal=float(df_1m['Close'].iloc[-1]) if df_1m is not None else 0.0,
                        volume_at_signal=int(df_1m['Volume'].iloc[-1]) if df_1m is not None else 0,
                        grade=self.calculate_atom_grade(confidence_score),
                        timestamp_utc=current_time.isoformat(),
                        context_atoms_active=self.get_active_context_atoms(ticker),
                        confidence_score=confidence_score
                    )
                    
                    derived_atoms.append(atom_signal)
            
        except Exception as e:
            logger.error(f"Derived 아톰 탐지 오류: {e}")
        
        return derived_atoms
    
    def get_active_context_atoms(self, ticker: str) -> List[str]:
        """현재 활성화된 컨텍스트 아톰 목록 반환"""
        active_atoms = []
        current_time = datetime.now(timezone.utc)
        
        # 만료된 컨텍스트 아톰 제거
        expired_atoms = []
        for atom_id, atom_data in self.active_context_atoms.items():
            if atom_data['expiry_time'] < current_time:
                expired_atoms.append(atom_id)
            elif atom_data['ticker'] == ticker:
                active_atoms.append(atom_id)
        
        # 만료된 아톰 제거
        for atom_id in expired_atoms:
            del self.active_context_atoms[atom_id]
        
        return active_atoms
    
    def deduplicate_and_grade_atoms(self, atoms: List[AtomSignal]) -> List[AtomSignal]:
        """중복 제거 및 최종 등급 산정"""
        try:
            # 아톰 ID별로 그룹화
            atom_groups = {}
            for atom in atoms:
                if atom.atom_id not in atom_groups:
                    atom_groups[atom.atom_id] = []
                atom_groups[atom.atom_id].append(atom)
            
            # 각 그룹에서 가장 높은 신뢰도의 아톰만 선택
            final_atoms = []
            for atom_id, atom_list in atom_groups.items():
                if atom_list:
                    # 신뢰도가 가장 높은 아톰 선택
                    best_atom = max(atom_list, key=lambda x: x.confidence_score)
                    final_atoms.append(best_atom)
            
            return final_atoms
            
        except Exception as e:
            logger.error(f"아톰 중복 제거 오류: {e}")
            return atoms
    
    def calculate_atom_grade(self, confidence_score: float) -> str:
        """신뢰도 점수를 기반으로 아톰 등급 산정"""
        if confidence_score >= 0.95:
            return 'A++'
        elif confidence_score >= 0.85:
            return 'A+'
        elif confidence_score >= 0.75:
            return 'A'
        elif confidence_score >= 0.65:
            return 'B+'
        elif confidence_score >= 0.55:
            return 'B'
        else:
            return 'C'
    
    async def record_atom_to_sidb(self, atom_signal: AtomSignal):
        """아톰 신호를 SIDB에 기록"""
        try:
            if not self.sheets_service:
                logger.debug(f"SIDB 기록 스킵 (Sheets 서비스 없음): {atom_signal.atom_id}")
                return
            
            # SIDB 기록용 데이터 준비
            sidb_data = {
                'Instance_ID': str(uuid.uuid4()),
                'Timestamp_UTC': atom_signal.timestamp_utc,
                'Ticker': atom_signal.ticker,
                'Atom_ID': atom_signal.atom_id,
                'Timeframe': atom_signal.timeframe,
                'Price_At_Signal': atom_signal.price_at_signal,
                'Volume_At_Signal': atom_signal.volume_at_signal,
                'Context_Atoms_Active': ','.join(atom_signal.context_atoms_active),
                'Is_Duplicate': False
            }
            
            # Google Sheets에 기록
            success = await self.sheets_service.append_sidb_record(sidb_data)
            
            if success:
                logger.debug(f"SIDB 기록 성공: {atom_signal.atom_id} ({atom_signal.ticker})")
            else:
                logger.warning(f"SIDB 기록 실패: {atom_signal.atom_id} ({atom_signal.ticker})")
            
        except Exception as e:
            logger.error(f"SIDB 기록 오류: {e}")
    
    # 시뮬레이션 헬퍼 함수들
    def simulate_catalyst_grade(self, ticker: str, grade: str) -> bool:
        """촉매 등급 시뮬레이션 (실제로는 뉴스 API 연동 필요)"""
        # 특정 종목에서 10% 확률로 A++ 촉매 발생
        import random
        return random.random() < 0.1
    
    def simulate_nasdaq_trend(self) -> bool:
        """나스닥 추세 시뮬레이션 (실제로는 QQQ 데이터 필요)"""
        # 70% 확률로 상승 추세
        import random
        return random.random() < 0.7
    
    async def get_real_time_data(self, ticker: str, timeframes: List[str] = ['1m', '5m', '1h']) -> Dict[str, pd.DataFrame]:
        """
        실시간 데이터 수집 (yfinance 기반)
        실제 운영에서는 Alpaca API 등으로 대체 필요
        """
        try:
            data_dict = {}
            
            for timeframe in timeframes:
                try:
                    # yfinance로 최근 데이터 수집
                    stock = yf.Ticker(ticker)
                    
                    if timeframe == '1m':
                        df = stock.history(period='1d', interval='1m')
                    elif timeframe == '5m':
                        df = stock.history(period='5d', interval='5m')
                    elif timeframe == '1h':
                        df = stock.history(period='1mo', interval='1h')
                    else:
                        continue
                    
                    if not df.empty:
                        # 컬럼명 표준화
                        df = df.rename(columns={
                            'Open': 'Open',
                            'High': 'High', 
                            'Low': 'Low',
                            'Close': 'Close',
                            'Volume': 'Volume'
                        })
                        
                        data_dict[timeframe] = df
                    
                except Exception as e:
                    logger.warning(f"{ticker} {timeframe} 데이터 수집 실패: {e}")
                    continue
            
            return data_dict
            
        except Exception as e:
            logger.error(f"실시간 데이터 수집 오류 ({ticker}): {e}")
            return {}
    
    async def detect_atoms_for_ticker(self, ticker: str) -> List[AtomSignal]:
        """특정 종목에 대한 아톰 탐지 (외부 호출용)"""
        try:
            # 실시간 데이터 수집
            ohlcv_data = await self.get_real_time_data(ticker)
            
            if not ohlcv_data:
                logger.warning(f"데이터 없음: {ticker}")
                return []
            
            # 아톰 탐지 실행
            detected_atoms = await self.detect_atoms_in_data(ticker, ohlcv_data)
            
            return detected_atoms
            
        except Exception as e:
            logger.error(f"종목별 아톰 탐지 오류 ({ticker}): {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """아톰 탐지기 통계 반환"""
        return {
            'atoms_detected_count': self.atoms_detected_count,
            'signals_generated_count': self.signals_generated_count,
            'atoms_cache_size': len(self.atoms_cache),
            'molecules_cache_size': len(self.molecules_cache),
            'active_context_atoms_count': len(self.active_context_atoms)
        }

# 사용 예시
if __name__ == "__main__":
    async def test_atom_detector():
        """아톰 탐지기 테스트"""
        
        # 아톰 탐지기 초기화
        detector = AtomDetector()
        await detector.initialize()
        
        print("🔍 아톰 탐지기 테스트 시작")
        print("=" * 50)
        
        # 테스트 종목
        test_tickers = ['AAPL', 'TSLA', 'MSFT']
        
        for ticker in test_tickers:
            print(f"\n📊 {ticker} 아톰 탐지 중...")
            
            try:
                # 아톰 탐지 실행
                detected_atoms = await detector.detect_atoms_for_ticker(ticker)
                
                if detected_atoms:
                    print(f"✅ {len(detected_atoms)}개 아톰 탐지:")
                    for atom in detected_atoms:
                        print(f"   - {atom.atom_id}: {atom.atom_name} (등급: {atom.grade})")
                else:
                    print("   탐지된 아톰 없음")
                    
            except Exception as e:
                print(f"   ❌ 오류: {e}")
        
        # 통계 출력
        stats = detector.get_statistics()
        print(f"\n📈 탐지 통계:")
        print(f"   - 총 탐지된 아톰: {stats['atoms_detected_count']}개")
        print(f"   - 로드된 아톰 정의: {stats['atoms_cache_size']}개")
        print(f"   - 활성 컨텍스트 아톰: {stats['active_context_atoms_count']}개")
        
        print("\n✅ 아톰 탐지기 테스트 완료!")
    
    # 테스트 실행
    asyncio.run(test_atom_detector())
