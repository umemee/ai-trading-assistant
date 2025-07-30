"""
SignalScanner Module - 실시간 아톰 탐지 및 분자 신호 생성
Alpaca WebSocket을 통한 24시간 시장 데이터 모니터링
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Callable, Optional
import random

from services.alpaca_service import AlpacaService
from services.sheets_service import SheetsService
from utils.database import DatabaseManager

logger = logging.getLogger(__name__)

class SignalScanner:
    """실시간 시장 스캐너 - 아톰 탐지 및 분자 신호 생성"""
    
    def __init__(self, alpaca_service: AlpacaService, 
                 sheets_service: Optional[SheetsService] = None,
                 database_manager: Optional[DatabaseManager] = None):
        self.alpaca_service = alpaca_service
        self.sheets_service = sheets_service
        self.database_manager = database_manager
        
        self.is_running = False
        self.watchlist: List[str] = []
        self.atoms: List[Dict] = []
        self.molecules: List[Dict] = []
        
        # 콜백 함수들
        self.signal_callback: Optional[Callable] = None
        self.molecule_callback: Optional[Callable] = None
        
        # 통계
        self.atoms_detected = 0
        self.signals_generated = 0
        
    async def start(self, tickers: List[str]):
        """스캐너 시작"""
        if self.is_running:
            await self.stop()
            
        self.watchlist = tickers
        self.is_running = True
        
        logger.info(f"SignalScanner started with tickers: {tickers}")
        
        # 아톰과 분자 데이터 로드
        await self.load_knowledge_base()
        
        # Alpaca WebSocket 시작
        await self.alpaca_service.start_websocket(
            symbols=tickers,
            on_quote=self.on_quote_received,
            on_trade=self.on_trade_received,
            on_bar=self.on_bar_received
        )
        
        # 정기적인 분자 매칭 작업 시작
        asyncio.create_task(self.molecule_matcher_loop())
        
    async def stop(self):
        """스캐너 정지"""
        if not self.is_running:
            return
            
        self.is_running = False
        await self.alpaca_service.stop_websocket()
        
        logger.info("SignalScanner stopped")
        
    async def load_knowledge_base(self):
        """지식 베이스 로드 (아톰과 분자 정의)"""
        try:
            if self.sheets_service:
                # Google Sheets에서 로드
                self.atoms = await self.sheets_service.get_atoms()
                self.molecules = await self.sheets_service.get_molecules()
            else:
                # 로컬 더미 데이터 사용
                self.atoms = self.get_demo_atoms()
                self.molecules = self.get_demo_molecules()
                
            logger.info(f"Loaded {len(self.atoms)} atoms and {len(self.molecules)} molecules")
            
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")
            # 폴백: 더미 데이터 사용
            self.atoms = self.get_demo_atoms()
            self.molecules = self.get_demo_molecules()
    
    def get_demo_atoms(self) -> List[Dict]:
        """더미 아톰 데이터"""
        return [
            {
                "atom_id": "STR-003",
                "name": "1분 20EMA 지지",
                "category": "Structural",
                "description": "1분 차트에서 20EMA 지지선 확인"
            },
            {
                "atom_id": "TRG-003", 
                "name": "거래량 폭발",
                "category": "Trigger",
                "description": "평균 거래량 대비 5배 이상 폭발"
            },
            {
                "atom_id": "CTX-001",
                "name": "A급 시황 환경",
                "category": "Context", 
                "description": "시장 전반적인 A급 상승 환경"
            }
        ]
    
    def get_demo_molecules(self) -> List[Dict]:
        """더미 분자 데이터""" 
        return [
            {
                "molecule_id": "LOGIC-EXP-004",
                "name": "첫 번째 눌림목",
                "required_atoms": ["CTX-001", "STR-003", "TRG-003"],
                "threshold": 80
            }
        ]
    
    async def on_quote_received(self, quote_data: Dict):
        """실시간 호가 데이터 수신"""
        # 호가 데이터 기반 아톰 탐지 로직 (간소화)
        pass
        
    async def on_trade_received(self, trade_data: Dict):
        """실시간 거래 데이터 수신"""
        symbol = trade_data.get("symbol", "")
        price = trade_data.get("price", 0)
        volume = trade_data.get("size", 0)
        
        # 거래량 기반 아톰 탐지
        await self.detect_volume_atoms(symbol, price, volume)
        
    async def on_bar_received(self, bar_data: Dict):
        """실시간 바 데이터 수신 (1분봉)"""
        symbol = bar_data.get("symbol", "")
        
        # 기술적 분석 기반 아톰 탐지
        await self.detect_technical_atoms(symbol, bar_data)
        
    async def detect_volume_atoms(self, symbol: str, price: float, volume: int):
        """거래량 기반 아톰 탐지"""
        # 간단한 거래량 폭발 탐지 로직
        if volume > 100000:  # 임계값
            await self.trigger_atom_signal(
                symbol=symbol,
                atom_id="TRG-003",
                atom_name="거래량 폭발",
                price=price,
                volume=volume,
                grade=self.calculate_signal_grade(volume, 100000)
            )
    
    async def detect_technical_atoms(self, symbol: str, bar_data: Dict):
        """기술적 분석 기반 아톰 탐지"""
        # 여기서는 랜덤 시뮬레이션으로 대체
        # 실제로는 EMA, 지지/저항선 등을 계산
        
        if random.random() < 0.3:  # 30% 확률로 아톰 탐지
            atom = random.choice(self.atoms)
            price = bar_data.get("close", random.uniform(50, 200))
            volume = bar_data.get("volume", random.randint(10000, 1000000))
            
            await self.trigger_atom_signal(
                symbol=symbol,
                atom_id=atom["atom_id"],
                atom_name=atom["name"],
                price=price,
                volume=volume,
                grade=random.choice(["A++", "A+", "A", "B+", "B", "C"])
            )
    
    async def trigger_atom_signal(self, symbol: str, atom_id: str, atom_name: str, 
                                  price: float, volume: int, grade: str):
        """아톰 신호 발생"""
        self.atoms_detected += 1
        
        signal_data = {
            "ticker": symbol,
            "atom_id": atom_id,
            "atom_name": atom_name,
            "price": price,
            "volume": volume,
            "grade": grade,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Google Sheets에 기록
        if self.sheets_service:
            try:
                await self.sheets_service.append_sidb_record(signal_data)
            except Exception as e:
                logger.error(f"Error saving to SIDB: {e}")
        
        # 콜백 호출
        if self.signal_callback:
            self.signal_callback(signal_data)
            
        logger.info(f"Atom signal triggered: {symbol} - {atom_id} - {grade}")
    
    def calculate_signal_grade(self, value: float, threshold: float) -> str:
        """신호 등급 계산"""
        ratio = value / threshold
        if ratio >= 5.0:
            return "A++"
        elif ratio >= 3.0:
            return "A+"
        elif ratio >= 2.0:
            return "A"
        elif ratio >= 1.5:
            return "B+"
        elif ratio >= 1.0:
            return "B"
        else:
            return "C"
    
    async def molecule_matcher_loop(self):
        """분자 매칭 루프 (백그라운드 실행)"""
        while self.is_running:
            try:
                await self.check_molecule_triggers()
                await asyncio.sleep(10)  # 10초마다 확인
            except Exception as e:
                logger.error(f"Error in molecule matcher loop: {e}")
                await asyncio.sleep(5)
    
    async def check_molecule_triggers(self):
        """분자 트리거 확인"""
        # 최근 아톰 신호들을 기반으로 분자 매칭
        # 실제로는 SIDB에서 최근 30분간의 아톰 신호를 조회
        
        if random.random() < 0.15:  # 15% 확률로 분자 신호
            molecule = random.choice(self.molecules)
            symbol = random.choice(self.watchlist) if self.watchlist else "AAPL"
            
            await self.trigger_molecule_signal(
                symbol=symbol,
                molecule_id=molecule["molecule_id"],
                molecule_name=molecule["name"],
                grade="A+",
                matched_atoms=molecule["required_atoms"]
            )
    
    async def trigger_molecule_signal(self, symbol: str, molecule_id: str, 
                                      molecule_name: str, grade: str, 
                                      matched_atoms: List[str]):
        """분자 신호 발생"""
        self.signals_generated += 1
        
        signal_data = {
            "ticker": symbol,
            "molecule_id": molecule_id,
            "molecule_name": molecule_name,
            "grade": grade,
            "matched_atoms": matched_atoms,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 콜백 호출
        if self.molecule_callback:
            self.molecule_callback(signal_data)
            
        logger.info(f"Molecule signal triggered: {symbol} - {molecule_id}")
    
    def set_signal_callback(self, callback: Callable):
        """아톰 신호 콜백 설정"""
        self.signal_callback = callback
    
    def set_molecule_callback(self, callback: Callable):
        """분자 신호 콜백 설정"""
        self.molecule_callback = callback
    
    def get_statistics(self) -> Dict:
        """스캐너 통계 반환"""
        return {
            "is_running": self.is_running,
            "watchlist_size": len(self.watchlist),
            "atoms_detected": self.atoms_detected,
            "signals_generated": self.signals_generated,
            "knowledge_base": {
                "atoms": len(self.atoms),
                "molecules": len(self.molecules)
            }
        }
