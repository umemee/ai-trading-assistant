"""
signal_scanner.py - 완전한 실시간 아톰 탐지 및 분자 신호 생성 엔진
AI 트레이딩 어시스턴트 V5.1의 핵심 스캐닝 모듈

주요 기능:
- Alpaca API 실시간 데이터 수신
- 완전한 기술적 지표 계산 연동
- 실제 아톰 탐지 로직 구현
- 분자 매칭 및 신호 생성
- Google Sheets 자동 기록
- 핵심 매매 시간대 필터링 (21:00-00:30 KST)
- 다중 시간대 분석 (1분, 5분, 1시간)
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Callable, Optional, Any
import pandas as pd
import numpy as np
from collections import defaultdict, deque

# 새로운 서비스들 import
from services.alpaca_service import AlpacaService
from services.sheets_service import SheetsService
from technical_indicators import TechnicalIndicators
from atom_detector import AtomDetector, AtomSignal
from molecule_matcher import MoleculeMatcher, MoleculeMatchResult

logger = logging.getLogger(__name__)

class DataBuffer:
    """시간대별 데이터 버퍼 관리"""
    
    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self.buffers = {
            '1m': defaultdict(lambda: deque(maxlen=max_size)),
            '5m': defaultdict(lambda: deque(maxlen=max_size // 5)),
            '1h': defaultdict(lambda: deque(maxlen=max_size // 60))
        }
        self.last_bar_timestamps = defaultdict(dict)
    
    def add_trade_data(self, symbol: str, trade_data: Dict):
        """거래 데이터를 시간대별 버퍼에 추가"""
        timestamp = datetime.fromtimestamp(trade_data.get('timestamp', 0), tz=timezone.utc)
        
        # 1분봉 데이터 생성/업데이트
        self._update_bar_data(symbol, '1m', timestamp, trade_data)
        
        # 5분봉 데이터 생성/업데이트  
        self._update_bar_data(symbol, '5m', timestamp, trade_data)
        
        # 1시간봉 데이터 생성/업데이트
        self._update_bar_data(symbol, '1h', timestamp, trade_data)
    
    def _update_bar_data(self, symbol: str, timeframe: str, timestamp: datetime, trade_data: Dict):
        """특정 시간대의 바 데이터 업데이트"""
        # 시간대별 바 시작 시간 계산
        if timeframe == '1m':
            bar_start = timestamp.replace(second=0, microsecond=0)
        elif timeframe == '5m':
            minute = (timestamp.minute // 5) * 5
            bar_start = timestamp.replace(minute=minute, second=0, microsecond=0)
        else:  # 1h
            bar_start = timestamp.replace(minute=0, second=0, microsecond=0)
        
        buffer = self.buffers[timeframe][symbol]
        price = float(trade_data.get('price', 0))
        volume = int(trade_data.get('size', 0))
        
        # 새로운 바인지 확인
        if (symbol not in self.last_bar_timestamps[timeframe] or 
            self.last_bar_timestamps[timeframe][symbol] != bar_start):
            
            # 새로운 바 생성
            new_bar = {
                'timestamp': bar_start,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume
            }
            buffer.append(new_bar)
            self.last_bar_timestamps[timeframe][symbol] = bar_start
        else:
            # 기존 바 업데이트
            if buffer:
                current_bar = buffer[-1]
                current_bar['high'] = max(current_bar['high'], price)
                current_bar['low'] = min(current_bar['low'], price)
                current_bar['close'] = price
                current_bar['volume'] += volume
    
    def get_dataframe(self, symbol: str, timeframe: str, periods: int = 100) -> pd.DataFrame:
        """특정 심볼과 시간대의 데이터프레임 반환"""
        buffer = self.buffers[timeframe][symbol]
        
        if not buffer:
            return pd.DataFrame()
        
        # 최근 N개 데이터만 선택
        recent_data = list(buffer)[-periods:] if len(buffer) > periods else list(buffer)
        
        if not recent_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(recent_data)
        df.set_index('timestamp', inplace=True)
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        return df

class SignalScanner:
    """완전한 실시간 시장 스캐너 - 실제 아톰 탐지 및 분자 신호 생성"""
    
    def __init__(self, 
                 alpaca_service: AlpacaService,
                 sheets_service: Optional[SheetsService] = None,
                 technical_indicators: Optional[TechnicalIndicators] = None,
                 atom_detector: Optional[AtomDetector] = None,
                 molecule_matcher: Optional[MoleculeMatcher] = None):
        
        self.alpaca_service = alpaca_service
        self.sheets_service = sheets_service
        
        # 서비스 초기화
        self.technical_indicators = technical_indicators or TechnicalIndicators()
        self.atom_detector = atom_detector or AtomDetector(sheets_service)
        self.molecule_matcher = molecule_matcher or MoleculeMatcher(sheets_service)
        
        # 상태 관리
        self.is_running = False
        self.watchlist: List[str] = []
        
        # 데이터 버퍼
        self.data_buffer = DataBuffer()
        
        # 콜백 함수들
        self.signal_callback: Optional[Callable] = None
        self.molecule_callback: Optional[Callable] = None
        
        # 통계
        self.atoms_detected = 0
        self.molecules_triggered = 0
        self.trades_processed = 0
        self.start_time = None
        
        # 핵심 매매 시간대 설정 (KST)
        self.core_trading_hours = {
            'start_hour': 21,  # 21:00 KST
            'end_hour': 0,     # 00:30 KST (다음날)
            'end_minute': 30
        }
        
        # 스캔 간격 설정
        self.scan_intervals = {
            'atom_detection': 10,  # 10초마다 아톰 탐지
            'molecule_matching': 15,  # 15초마다 분자 매칭
            'data_cleanup': 300   # 5분마다 데이터 정리
        }
        
        logger.info("완전한 SignalScanner 초기화 완료")
    
    async def initialize(self):
        """스캐너 초기화 - 모든 서비스 준비"""
        try:
            # 아톰 탐지기 초기화
            await self.atom_detector.initialize()
            
            # 분자 매칭기 초기화
            await self.molecule_matcher.initialize()
            
            logger.info("SignalScanner 모든 서비스 초기화 완료")
            
        except Exception as e:
            logger.error(f"SignalScanner 초기화 실패: {e}")
            raise
    
    async def start(self, tickers: List[str]):
        """스캐너 시작"""
        if self.is_running:
            await self.stop()
        
        if not tickers:
            raise ValueError("감시할 종목이 없습니다")
        
        self.watchlist = tickers
        self.is_running = True
        self.start_time = datetime.now(timezone.utc)
        
        logger.info(f"SignalScanner 시작: {tickers}")
        
        # 서비스 초기화
        await self.initialize()
        
        try:
            # Alpaca WebSocket 시작
            await self.alpaca_service.start_websocket(
                symbols=tickers,
                on_quote=self.on_quote_received,
                on_trade=self.on_trade_received,
                on_bar=self.on_bar_received
            )
            
            # 백그라운드 작업들 시작
            asyncio.create_task(self.atom_detection_loop())
            asyncio.create_task(self.molecule_matching_loop())
            asyncio.create_task(self.data_maintenance_loop())
            
            logger.info("SignalScanner 모든 루프 시작됨")
            
        except Exception as e:
            logger.error(f"SignalScanner 시작 실패: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """스캐너 정지"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        try:
            await self.alpaca_service.stop_websocket()
            logger.info("SignalScanner 정지됨")
        except Exception as e:
            logger.error(f"SignalScanner 정지 중 오류: {e}")
    
    def is_core_trading_hours(self, timestamp: datetime = None) -> bool:
        """핵심 매매 시간대 확인 (21:00-00:30 KST)"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # UTC를 KST로 변환 (UTC+9)  
        kst_time = timestamp + timedelta(hours=9)
        hour = kst_time.hour
        minute = kst_time.minute
        
        # 21:00-23:59 또는 00:00-00:30
        return (hour >= 21) or (hour == 0 and minute <= 30)
    
    # ================== 실시간 데이터 수신 핸들러 ==================
    
    async def on_quote_received(self, quote_data: Dict):
        """실시간 호가 데이터 수신 처리"""
        try:
            symbol = quote_data.get("symbol", "")
            
            # 핵심 매매 시간대가 아니면 무시
            if not self.is_core_trading_hours():
                return
            
            # 호가 데이터 기반 추가 분석 (필요시 구현)
            logger.debug(f"Quote received for {symbol}")
            
        except Exception as e:
            logger.error(f"호가 데이터 처리 오류: {e}")
    
    async def on_trade_received(self, trade_data: Dict):
        """실시간 거래 데이터 수신 처리"""
        try:
            symbol = trade_data.get("symbol", "")
            
            # 핵심 매매 시간대가 아니면 무시
            if not self.is_core_trading_hours():
                return
            
            # 데이터 버퍼에 추가
            self.data_buffer.add_trade_data(symbol, trade_data)
            self.trades_processed += 1
            
            # 즉시 거래량 기반 아톰 체크 (TRG-003: 거래량 폭발)
            await self.check_volume_atoms(symbol, trade_data)
            
            logger.debug(f"Trade processed for {symbol}: {trade_data.get('price')} x {trade_data.get('size')}")
            
        except Exception as e:
            logger.error(f"거래 데이터 처리 오류: {e}")
    
    async def on_bar_received(self, bar_data: Dict):
        """실시간 바 데이터 수신 처리 (Alpaca에서 직접 제공하는 경우)"""
        try:
            symbol = bar_data.get("symbol", "")
            
            # 핵심 매매 시간대가 아니면 무시
            if not self.is_core_trading_hours():
                return
            
            logger.debug(f"Bar received for {symbol}")
            
        except Exception as e:
            logger.error(f"바 데이터 처리 오류: {e}")
    
    # ================== 즉시 처리 아톰 탐지 ==================
    
    async def check_volume_atoms(self, symbol: str, trade_data: Dict):
        """거래량 기반 아톰 즉시 탐지 (TRG-003)"""
        try:
            # 1분봉 데이터 확인
            df_1m = self.data_buffer.get_dataframe(symbol, '1m', 20)
            
            if df_1m.empty or len(df_1m) < 2:
                return
            
            # 거래량 폭발 탐지
            volume_result = self.technical_indicators.detect_volume_explosion(df_1m)
            
            if volume_result['triggered']:
                # 아톰 신호 생성
                atom_signal = AtomSignal(
                    atom_id='TRG-003',
                    atom_name='거래량_폭발',
                    ticker=symbol,
                    timeframe='1m',
                    price_at_signal=float(trade_data.get('price', 0)),
                    volume_at_signal=int(trade_data.get('size', 0)),
                    grade=volume_result['grade'],
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    context_atoms_active=[],
                    confidence_score=min(0.95, volume_result['volume_ratio'] / 10.0)
                )
                
                await self.process_atom_signal(atom_signal)
                
        except Exception as e:
            logger.error(f"거래량 아톰 탐지 오류: {e}")
    
    # ================== 백그라운드 탐지 루프들 ==================
    
    async def atom_detection_loop(self):
        """아톰 탐지 백그라운드 루프"""
        logger.info("아톰 탐지 루프 시작")
        
        while self.is_running:
            try:
                # 핵심 매매 시간대에만 실행
                if self.is_core_trading_hours():
                    for symbol in self.watchlist:
                        await self.detect_atoms_for_symbol(symbol)
                        
                        # CPU 과부하 방지
                        await asyncio.sleep(0.5)
                
                # 스캔 간격 대기
                await asyncio.sleep(self.scan_intervals['atom_detection'])
                
            except Exception as e:
                logger.error(f"아톰 탐지 루프 오류: {e}")
                await asyncio.sleep(5)
    
    async def detect_atoms_for_symbol(self, symbol: str):
        """특정 심볼에 대한 포괄적 아톰 탐지"""
        try:
            # 다중 시간대 데이터 수집
            data_dict = {}
            for timeframe in ['1m', '5m', '1h']:
                df = self.data_buffer.get_dataframe(symbol, timeframe)
                if not df.empty and len(df) >= 20:  # 최소 데이터 확보
                    # 기술적 지표 계산
                    df_with_indicators = self.technical_indicators.calculate_all_indicators(df, timeframe)
                    data_dict[timeframe] = df_with_indicators
            
            if not data_dict:
                return
            
            # 아톰 탐지기로 전달
            detected_atoms = await self.atom_detector.detect_atoms_in_data(
                ticker=symbol,
                ohlcv_data_dict=data_dict,
                current_time=datetime.now(timezone.utc)
            )
            
            # 탐지된 아톰들 처리
            for atom_signal in detected_atoms:
                await self.process_atom_signal(atom_signal)
                
        except Exception as e:
            logger.error(f"{symbol} 아톰 탐지 오류: {e}")
    
    async def molecule_matching_loop(self):
        """분자 매칭 백그라운드 루프"""
        logger.info("분자 매칭 루프 시작")
        
        while self.is_running:
            try:
                # 핵심 매매 시간대에만 실행
                if self.is_core_trading_hours():
                    await self.check_molecule_patterns()
                
                # 스캔 간격 대기
                await asyncio.sleep(self.scan_intervals['molecule_matching'])
                
            except Exception as e:
                logger.error(f"분자 매칭 루프 오류: {e}")
                await asyncio.sleep(5)
    
    async def check_molecule_patterns(self):
        """분자 패턴 매칭 확인"""
        try:
            # 분자 매칭기에서 최근 아톰 조합 확인
            matches = self.molecule_matcher.find_molecule_matches()
            
            for match in matches:
                if match.triggered and match.matched:
                    await self.process_molecule_signal(match)
                    
        except Exception as e:
            logger.error(f"분자 패턴 확인 오류: {e}")
    
    async def data_maintenance_loop(self):
        """데이터 유지보수 백그라운드 루프"""
        logger.info("데이터 유지보수 루프 시작")
        
        while self.is_running:
            try:
                # 메모리 사용량 체크 및 정리
                await self.cleanup_old_data()
                
                # 통계 업데이트
                await self.update_statistics()
                
                # 유지보수 간격 대기
                await asyncio.sleep(self.scan_intervals['data_cleanup'])
                
            except Exception as e:
                logger.error(f"데이터 유지보수 오류: {e}")
                await asyncio.sleep(30)
    
    # ================== 신호 처리 ==================
    
    async def process_atom_signal(self, atom_signal: AtomSignal):
        """아톰 신호 처리"""
        try:
            self.atoms_detected += 1
            
            # 아톰 데이터를 분자 매칭기에 전달
            atom_data = {
                'timestamp_utc': atom_signal.timestamp_utc,
                'ticker': atom_signal.ticker,
                'atom_id': atom_signal.atom_id,
                'grade': atom_signal.grade,
                'confidence_score': atom_signal.confidence_score
            }
            
            await self.molecule_matcher.on_atom_signal(atom_data)
            
            # Google Sheets에 SIDB 기록
            if self.sheets_service:
                await self.record_atom_to_sidb(atom_signal)
            
            # 콜백 호출 (UI 업데이트용)
            if self.signal_callback:
                await self.signal_callback({
                    "type": "atom_signal",
                    "ticker": atom_signal.ticker,
                    "atom_id": atom_signal.atom_id,
                    "atom_name": atom_signal.atom_name,
                    "price": atom_signal.price_at_signal,
                    "volume": atom_signal.volume_at_signal,
                    "grade": atom_signal.grade,
                    "timestamp": atom_signal.timestamp_utc
                })
            
            logger.info(f"아톰 신호 처리 완료: {atom_signal.ticker} - {atom_signal.atom_id} ({atom_signal.grade})")
            
        except Exception as e:
            logger.error(f"아톰 신호 처리 오류: {e}")
    
    async def process_molecule_signal(self, molecule_match: MoleculeMatchResult):
        """분자 신호 처리"""
        try:
            self.molecules_triggered += 1
            
            # 콜백 호출 (UI 업데이트용)
            if self.molecule_callback:
                await self.molecule_callback({
                    "type": "molecule_signal",
                    "molecule_id": molecule_match.molecule_id,
                    "molecule_name": molecule_match.molecule_name,
                    "matched_atoms": molecule_match.matched_atoms,
                    "match_ratio": molecule_match.match_ratio,
                    "grade": molecule_match.signal_grade,
                    "timestamp": molecule_match.timestamp_utc
                })
            
            logger.info(f"분자 신호 처리 완료: {molecule_match.molecule_id} (등급: {molecule_match.signal_grade})")
            
        except Exception as e:
            logger.error(f"분자 신호 처리 오류: {e}")
    
    async def record_atom_to_sidb(self, atom_signal: AtomSignal):
        """아톰 신호를 SIDB에 기록"""
        try:
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
            
            success = await self.sheets_service.append_sidb_record(sidb_data)
            
            if success:
                logger.debug(f"SIDB 기록 성공: {atom_signal.atom_id}")
            else:
                logger.warning(f"SIDB 기록 실패: {atom_signal.atom_id}")
                
        except Exception as e:
            logger.error(f"SIDB 기록 오류: {e}")
    
    # ================== 유지보수 및 통계 ==================
    
    async def cleanup_old_data(self):
        """오래된 데이터 정리"""
        try:
            # 각 심볼별로 오래된 데이터 정리
            for symbol in self.watchlist:
                for timeframe in ['1m', '5m', '1h']:
                    buffer = self.data_buffer.buffers[timeframe][symbol]
                    # deque의 maxlen이 자동으로 처리하므로 별도 정리 불필요
                    pass
            
            logger.debug("데이터 정리 완료")
            
        except Exception as e:
            logger.error(f"데이터 정리 오류: {e}")
    
    async def update_statistics(self):
        """통계 업데이트"""
        try:
            if self.start_time:
                uptime = datetime.now(timezone.utc) - self.start_time
                logger.debug(f"스캐너 가동시간: {uptime.total_seconds():.0f}초, "
                           f"아톰: {self.atoms_detected}개, 분자: {self.molecules_triggered}개, "
                           f"거래: {self.trades_processed}개")
            
        except Exception as e:
            logger.error(f"통계 업데이트 오류: {e}")
    
    # ================== 콜백 및 설정 ==================
    
    def set_signal_callback(self, callback: Callable):
        """아톰 신호 콜백 설정"""
        self.signal_callback = callback
    
    def set_molecule_callback(self, callback: Callable):
        """분자 신호 콜백 설정"""
        self.molecule_callback = callback
    
    def get_statistics(self) -> Dict[str, Any]:
        """스캐너 통계 반환"""
        uptime = 0
        if self.start_time:
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        return {
            "is_running": self.is_running,
            "watchlist": self.watchlist,
            "watchlist_size": len(self.watchlist),
            "atoms_detected": self.atoms_detected,
            "molecules_triggered": self.molecules_triggered,
            "trades_processed": self.trades_processed,
            "uptime_seconds": uptime,
            "is_core_trading_hours": self.is_core_trading_hours(),
            "data_buffer_status": {
                timeframe: {
                    symbol: len(self.data_buffer.buffers[timeframe][symbol])
                    for symbol in self.watchlist
                }
                for timeframe in ['1m', '5m', '1h']
            }
        }
    
    def get_recent_data(self, symbol: str, timeframe: str = '1m', periods: int = 50) -> Dict:
        """최근 데이터 반환 (디버깅용)"""
        try:
            df = self.data_buffer.get_dataframe(symbol, timeframe, periods)
            
            if df.empty:
                return {"error": "데이터 없음"}
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "periods": len(df),
                "latest_price": float(df['Close'].iloc[-1]),
                "latest_volume": int(df['Volume'].iloc[-1]),
                "price_change": float(df['Close'].iloc[-1] - df['Close'].iloc[0]),
                "volume_avg": float(df['Volume'].mean())
            }
            
        except Exception as e:
            return {"error": str(e)}

# 사용 예시 및 테스트
if __name__ == "__main__":
    async def test_signal_scanner():
        """완전한 SignalScanner 테스트"""
        
        # 더미 서비스들로 테스트
        from services.alpaca_service import AlpacaService
        
        alpaca_service = AlpacaService("test_key", "test_secret")
        
        scanner = SignalScanner(
            alpaca_service=alpaca_service,
            sheets_service=None  # 테스트용으로 None
        )
        
        # 콜백 설정
        async def atom_callback(signal):
            print(f"🔴 아톰 신호: {signal['ticker']} - {signal['atom_id']} ({signal['grade']})")
        
        async def molecule_callback(signal):
            print(f"🔥 분자 신호: {signal['molecule_id']} - {signal['molecule_name']} ({signal['grade']})")
        
        scanner.set_signal_callback(atom_callback)
        scanner.set_molecule_callback(molecule_callback)
        
        print("🔍 완전한 SignalScanner 테스트 시작")
        print("=" * 60)
        
        try:
            # 스캐너 시작
            await scanner.start(['AAPL', 'TSLA', 'MSFT'])
            
            print("✅ 스캐너 시작됨")
            print(f"📊 초기 통계: {scanner.get_statistics()}")
            
            # 30초간 실행
            await asyncio.sleep(30)
            
            print(f"📈 최종 통계: {scanner.get_statistics()}")
            
        except Exception as e:
            print(f"❌ 테스트 오류: {e}")
        finally:
            await scanner.stop()
            print("🛑 스캐너 정지됨")
    
    # 테스트 실행
    asyncio.run(test_signal_scanner())
