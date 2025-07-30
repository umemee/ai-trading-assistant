"""
alpaca_service.py - 완전한 Alpaca Markets API 연동 서비스
AI 트레이딩 어시스턴트 V5.1의 핵심 데이터 수집 모듈

주요 기능:
- REST API & WebSocket 완전 연동
- 실시간 다중 시간대 데이터 수집 (1분, 5분, 1시간)
- 자동 재연결 및 에러 복구
- yfinance 폴백 지원
- 핵심 매매 시간대 필터링 (21:00-00:30 KST)
- 데이터 버퍼링 및 캐싱
- 포지션 관리 및 주문 기능
"""

import asyncio
import json
import logging
import ssl
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Callable, Optional, Any, Tuple
from collections import defaultdict, deque
import websockets
import aiohttp
import pandas as pd
import yfinance as yf
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MarketData:
    """시장 데이터 구조체"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    timeframe: str
    source: str = "alpaca"

@dataclass
class TradeData:
    """거래 데이터 구조체"""
    symbol: str
    timestamp: datetime
    price: float
    size: int
    conditions: List[str] = None

@dataclass
class QuoteData:
    """호가 데이터 구조체"""
    symbol: str
    timestamp: datetime
    bid_price: float
    bid_size: int
    ask_price: float
    ask_size: int

class DataBuffer:
    """다중 시간대 데이터 버퍼"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffers = {
            '1m': defaultdict(lambda: deque(maxlen=max_size)),
            '5m': defaultdict(lambda: deque(maxlen=max_size // 5)),
            '1h': defaultdict(lambda: deque(maxlen=max_size // 60))
        }
        self.last_timestamps = defaultdict(dict)
        self.trade_aggregator = defaultdict(list)
    
    def add_trade(self, trade_data: TradeData):
        """거래 데이터를 시간대별 버퍼에 집계"""
        symbol = trade_data.symbol
        timestamp = trade_data.timestamp
        
        # 거래 데이터를 임시 저장
        self.trade_aggregator[symbol].append(trade_data)
        
        # 1분봉 집계
        self._aggregate_to_timeframe(symbol, '1m', timestamp)
        
        # 5분봉 집계
        self._aggregate_to_timeframe(symbol, '5m', timestamp)
        
        # 1시간봉 집계
        self._aggregate_to_timeframe(symbol, '1h', timestamp)
    
    def _aggregate_to_timeframe(self, symbol: str, timeframe: str, timestamp: datetime):
        """특정 시간대로 데이터 집계"""
        # 시간대별 바 시작 시간 계산
        if timeframe == '1m':
            bar_start = timestamp.replace(second=0, microsecond=0)
        elif timeframe == '5m':
            minute = (timestamp.minute // 5) * 5
            bar_start = timestamp.replace(minute=minute, second=0, microsecond=0)
        else:  # 1h
            bar_start = timestamp.replace(minute=0, second=0, microsecond=0)
        
        # 새로운 바인지 확인
        last_timestamp = self.last_timestamps[symbol].get(timeframe)
        
        if last_timestamp != bar_start:
            # 이전 바 완성 및 저장
            if last_timestamp and symbol in self.trade_aggregator:
                completed_bar = self._create_bar_from_trades(
                    symbol, timeframe, last_timestamp
                )
                if completed_bar:
                    self.buffers[timeframe][symbol].append(completed_bar)
            
            self.last_timestamps[symbol][timeframe] = bar_start
    
    def _create_bar_from_trades(self, symbol: str, timeframe: str, bar_timestamp: datetime) -> Optional[MarketData]:
        """거래 데이터로부터 바 데이터 생성"""
        if symbol not in self.trade_aggregator:
            return None
        
        # 해당 시간대의 거래들 필터링
        trades = []
        for trade in self.trade_aggregator[symbol]:
            if self._is_trade_in_timeframe(trade.timestamp, bar_timestamp, timeframe):
                trades.append(trade)
        
        if not trades:
            return None
        
        # OHLCV 계산
        prices = [trade.price for trade in trades]
        volumes = [trade.size for trade in trades]
        
        return MarketData(
            symbol=symbol,
            timestamp=bar_timestamp,
            open=prices[0],
            high=max(prices),
            low=min(prices),
            close=prices[-1],
            volume=sum(volumes),
            timeframe=timeframe,
            source="alpaca"
        )
    
    def _is_trade_in_timeframe(self, trade_time: datetime, bar_time: datetime, timeframe: str) -> bool:
        """거래가 해당 시간대에 속하는지 확인"""
        if timeframe == '1m':
            return (trade_time >= bar_time and 
                   trade_time < bar_time + timedelta(minutes=1))
        elif timeframe == '5m':
            return (trade_time >= bar_time and 
                   trade_time < bar_time + timedelta(minutes=5))
        else:  # 1h
            return (trade_time >= bar_time and 
                   trade_time < bar_time + timedelta(hours=1))
    
    def get_latest_bars(self, symbol: str, timeframe: str, count: int = 100) -> List[MarketData]:
        """최신 바 데이터 반환"""
        buffer = self.buffers[timeframe][symbol]
        return list(buffer)[-count:] if len(buffer) > count else list(buffer)
    
    def get_dataframe(self, symbol: str, timeframe: str, count: int = 100) -> pd.DataFrame:
        """DataFrame 형태로 데이터 반환"""
        bars = self.get_latest_bars(symbol, timeframe, count)
        
        if not bars:
            return pd.DataFrame()
        
        data = []
        for bar in bars:
            data.append({
                'timestamp': bar.timestamp,
                'Open': bar.open,
                'High': bar.high,
                'Low': bar.low,
                'Close': bar.close,
                'Volume': bar.volume
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index('timestamp', inplace=True)
        
        return df

class AlpacaService:
    """완전한 Alpaca Markets API 서비스"""
    
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        
        # API URLs
        if paper:
            self.base_url = "https://paper-api.alpaca.markets"
            self.data_url = "https://data.alpaca.markets"
            self.ws_url = "wss://stream.data.alpaca.markets/v2/sip"
        else:
            self.base_url = "https://api.alpaca.markets"
            self.data_url = "https://data.alpaca.markets"
            self.ws_url = "wss://stream.data.alpaca.markets/v2/sip"
        
        # WebSocket 관련
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.is_authenticated = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
        # 콜백 함수들
        self.on_quote: Optional[Callable] = None
        self.on_trade: Optional[Callable] = None
        self.on_bar: Optional[Callable] = None
        self.on_connection_change: Optional[Callable] = None
        
        # 데이터 관리
        self.data_buffer = DataBuffer()
        self.subscribed_symbols: List[str] = []
        
        # 상태 관리
        self.last_heartbeat = datetime.now(timezone.utc)
        self.message_count = 0
        self.error_count = 0
        
        # 핵심 매매 시간대 설정 (KST)
        self.core_trading_hours = {
            'start_hour': 21,  # 21:00 KST
            'end_hour': 0,     # 00:30 KST (다음날)
            'end_minute': 30
        }
        
        # HTTP 세션
        self.session: Optional[aiohttp.ClientSession] = None
        
        logger.info("AlpacaService 초기화 완료")
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.stop_websocket()
        if self.session:
            await self.session.close()
    
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
    
    # ================== REST API 기능 ==================
    
    async def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            headers = {
                'APCA-API-KEY-ID': self.api_key,
                'APCA-API-SECRET-KEY': self.secret_key
            }
            
            # 계정 정보 조회로 인증 테스트
            async with self.session.get(
                f"{self.base_url}/v2/account",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                if response.status == 200:
                    account_data = await response.json()
                    logger.info(f"Alpaca 연결 성공: {account_data.get('status', 'Unknown')}")
                    return True
                else:
                    logger.error(f"Alpaca 인증 실패: {response.status}")
                    return False
        
        except Exception as e:
            logger.error(f"Alpaca 연결 테스트 실패: {e}")
            return False
    
    async def get_account_info(self) -> Dict[str, Any]:
        """계정 정보 조회"""
        try:
            headers = self._get_headers()
            
            async with self.session.get(
                f"{self.base_url}/v2/account",
                headers=headers
            ) as response:
                
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"계정 정보 조회 실패: {response.status}")
        
        except Exception as e:
            logger.error(f"계정 정보 조회 오류: {e}")
            return {}
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """포지션 목록 조회"""
        try:
            headers = self._get_headers()
            
            async with self.session.get(
                f"{self.base_url}/v2/positions",
                headers=headers
            ) as response:
                
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"포지션 조회 실패: {response.status}")
        
        except Exception as e:
            logger.error(f"포지션 조회 오류: {e}")
            return []
    
    async def get_historical_bars(self, symbols: List[str], timeframe: str = '1Min', 
                                 start: datetime = None, end: datetime = None, 
                                 limit: int = 1000) -> Dict[str, pd.DataFrame]:
        """과거 바 데이터 조회"""
        try:
            if not start:
                start = datetime.now(timezone.utc) - timedelta(days=1)
            if not end:
                end = datetime.now(timezone.utc)
            
            headers = self._get_headers()
            results = {}
            
            for symbol in symbols:
                params = {
                    'symbols': symbol,
                    'timeframe': timeframe,
                    'start': start.isoformat(),
                    'end': end.isoformat(),
                    'limit': limit,
                    'adjustment': 'raw'
                }
                
                async with self.session.get(
                    f"{self.data_url}/v2/stocks/bars",
                    headers=headers,
                    params=params
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        bars = data.get('bars', {}).get(symbol, [])
                        
                        if bars:
                            df_data = []
                            for bar in bars:
                                df_data.append({
                                    'timestamp': pd.to_datetime(bar['t']),
                                    'Open': bar['o'],
                                    'High': bar['h'],
                                    'Low': bar['l'],
                                    'Close': bar['c'],
                                    'Volume': bar['v']
                                })
                            
                            df = pd.DataFrame(df_data)
                            if not df.empty:
                                df.set_index('timestamp', inplace=True)
                            results[symbol] = df
                        else:
                            results[symbol] = pd.DataFrame()
                    else:
                        logger.warning(f"{symbol} 과거 데이터 조회 실패: {response.status}")
                        results[symbol] = pd.DataFrame()
                
                # API 속도 제한 고려
                await asyncio.sleep(0.1)
            
            return results
            
        except Exception as e:
            logger.error(f"과거 데이터 조회 오류: {e}")
            return {}
    
    async def place_order(self, symbol: str, qty: int, side: str, 
                         order_type: str = 'market', time_in_force: str = 'day',
                         limit_price: float = None, stop_price: float = None) -> Dict[str, Any]:
        """주문 발주"""
        try:
            headers = self._get_headers()
            
            order_data = {
                'symbol': symbol,
                'qty': abs(qty),
                'side': side.lower(),
                'type': order_type.lower(),
                'time_in_force': time_in_force.lower()
            }
            
            if limit_price:
                order_data['limit_price'] = str(limit_price)
            if stop_price:
                order_data['stop_price'] = str(stop_price)
            
            async with self.session.post(
                f"{self.base_url}/v2/orders",
                headers=headers,
                json=order_data
            ) as response:
                
                if response.status == 201:
                    order_result = await response.json()
                    logger.info(f"주문 성공: {order_result.get('id')} - {symbol} {side} {qty}")
                    return order_result
                else:
                    error_text = await response.text()
                    raise Exception(f"주문 실패: {response.status} - {error_text}")
        
        except Exception as e:
            logger.error(f"주문 발주 오류: {e}")
            return {}
    
    def _get_headers(self) -> Dict[str, str]:
        """HTTP 요청 헤더 생성"""
        return {
            'APCA-API-KEY-ID': self.api_key,
            'APCA-API-SECRET-KEY': self.secret_key,
            'Content-Type': 'application/json'
        }
    
    # ================== WebSocket 기능 ==================
    
    async def start_websocket(self, symbols: List[str],
                             on_quote: Optional[Callable] = None,
                             on_trade: Optional[Callable] = None,
                             on_bar: Optional[Callable] = None,
                             on_connection_change: Optional[Callable] = None):
        """WebSocket 연결 시작"""
        self.on_quote = on_quote
        self.on_trade = on_trade
        self.on_bar = on_bar
        self.on_connection_change = on_connection_change
        self.subscribed_symbols = symbols
        
        logger.info(f"Alpaca WebSocket 시작: {symbols}")
        
        try:
            await self._connect_websocket()
            
            if self.is_connected:
                # 백그라운드 작업들 시작
                asyncio.create_task(self._websocket_heartbeat())
                asyncio.create_task(self._fallback_data_collector())
                
                logger.info("Alpaca WebSocket 모든 작업 시작됨")
            
        except Exception as e:
            logger.error(f"WebSocket 시작 실패: {e}")
            # 폴백 모드로 전환
            await self._start_fallback_mode()
    
    async def _connect_websocket(self):
        """WebSocket 연결 및 인증"""
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.websocket = await websockets.connect(
                self.ws_url, 
                ssl=ssl_context,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            self.reconnect_attempts = 0
            
            # 인증
            auth_message = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.secret_key
            }
            
            await self.websocket.send(json.dumps(auth_message))
            
            # 인증 응답 대기
            auth_response = await asyncio.wait_for(
                self.websocket.recv(), timeout=10.0
            )
            
            response_data = json.loads(auth_response)
            
            if response_data.get("T") == "success":
                self.is_authenticated = True
                logger.info("Alpaca WebSocket 인증 성공")
                
                # 구독 설정
                await self._subscribe_to_feeds()
                
                # 메시지 처리 루프 시작
                asyncio.create_task(self._message_handler_loop())
                
                # 연결 상태 콜백 호출
                if self.on_connection_change:
                    await self.on_connection_change(True, "연결됨")
                
            else:
                raise Exception(f"인증 실패: {response_data}")
                
        except Exception as e:
            logger.error(f"WebSocket 연결 실패: {e}")
            self.is_connected = False
            self.is_authenticated = False
            
            if self.on_connection_change:
                await self.on_connection_change(False, f"연결 실패: {str(e)}")
            
            # 재연결 시도
            await self._attempt_reconnect()
    
    async def _subscribe_to_feeds(self):
        """데이터 피드 구독"""
        if not self.websocket or not self.is_authenticated:
            return
        
        subscribe_message = {
            "action": "subscribe",
            "trades": self.subscribed_symbols,
            "quotes": self.subscribed_symbols,
            "bars": self.subscribed_symbols
        }
        
        await self.websocket.send(json.dumps(subscribe_message))
        logger.info(f"구독 설정 완료: {self.subscribed_symbols}")
    
    async def _message_handler_loop(self):
        """WebSocket 메시지 처리 루프"""
        try:
            while self.is_connected and self.websocket:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(), timeout=60.0
                    )
                    
                    self.message_count += 1
                    self.last_heartbeat = datetime.now(timezone.utc)
                    
                    # 메시지 파싱 및 처리
                    try:
                        data = json.loads(message)
                        if isinstance(data, list):
                            for item in data:
                                await self._process_message(item)
                        else:
                            await self._process_message(data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 파싱 오류: {e}")
                        continue
                
                except asyncio.TimeoutError:
                    logger.warning("WebSocket 메시지 타임아웃")
                    break
                except websockets.exceptions.ConnectionClosed:
                    logger.info("WebSocket 연결 종료됨")
                    break
                    
        except Exception as e:
            logger.error(f"메시지 처리 루프 오류: {e}")
            self.error_count += 1
        
        finally:
            self.is_connected = False
            self.is_authenticated = False
            
            if self.on_connection_change:
                await self.on_connection_change(False, "연결 끊어짐")
            
            # 재연결 시도
            await self._attempt_reconnect()
    
    async def _process_message(self, message: Dict):
        """개별 메시지 처리"""
        try:
            msg_type = message.get("T")
            
            # 핵심 매매 시간대가 아니면 일부 메시지 무시
            if not self.is_core_trading_hours():
                if msg_type in ["t", "q"]:  # 거래, 호가 데이터
                    return
            
            if msg_type == "t":  # Trade
                await self._handle_trade_message(message)
            elif msg_type == "q":  # Quote
                await self._handle_quote_message(message)
            elif msg_type == "b":  # Bar
                await self._handle_bar_message(message)
            elif msg_type == "error":
                logger.error(f"Alpaca WebSocket 오류: {message}")
                self.error_count += 1
            elif msg_type == "success":
                logger.debug("성공 메시지 수신")
            else:
                logger.debug(f"알 수 없는 메시지 타입: {msg_type}")
                
        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")
    
    async def _handle_trade_message(self, message: Dict):
        """거래 메시지 처리"""
        try:
            symbol = message.get("S", "")
            timestamp = pd.to_datetime(message.get("t"))
            price = float(message.get("p", 0))
            size = int(message.get("s", 0))
            conditions = message.get("c", [])
            
            # TradeData 객체 생성
            trade_data = TradeData(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
                size=size,
                conditions=conditions
            )
            
            # 데이터 버퍼에 추가
            self.data_buffer.add_trade(trade_data)
            
            # 콜백 호출
            if self.on_trade:
                await self.on_trade({
                    "symbol": symbol,
                    "timestamp": timestamp.timestamp(),
                    "price": price,
                    "size": size,
                    "conditions": conditions
                })
                
        except Exception as e:
            logger.error(f"거래 메시지 처리 오류: {e}")
    
    async def _handle_quote_message(self, message: Dict):
        """호가 메시지 처리"""
        try:
            symbol = message.get("S", "")
            timestamp = pd.to_datetime(message.get("t"))
            bid_price = float(message.get("bp", 0))
            bid_size = int(message.get("bs", 0))
            ask_price = float(message.get("ap", 0))
            ask_size = int(message.get("as", 0))
            
            # QuoteData 객체 생성
            quote_data = QuoteData(
                symbol=symbol,
                timestamp=timestamp,
                bid_price=bid_price,
                bid_size=bid_size,
                ask_price=ask_price,
                ask_size=ask_size
            )
            
            # 콜백 호출
            if self.on_quote:
                await self.on_quote({
                    "symbol": symbol,
                    "timestamp": timestamp.timestamp(),
                    "bid_price": bid_price,
                    "bid_size": bid_size,
                    "ask_price": ask_price,
                    "ask_size": ask_size
                })
                
        except Exception as e:
            logger.error(f"호가 메시지 처리 오류: {e}")
    
    async def _handle_bar_message(self, message: Dict):
        """바 메시지 처리"""
        try:
            symbol = message.get("S", "")
            timestamp = pd.to_datetime(message.get("t"))
            open_price = float(message.get("o", 0))
            high_price = float(message.get("h", 0))
            low_price = float(message.get("l", 0))
            close_price = float(message.get("c", 0))
            volume = int(message.get("v", 0))
            
            # MarketData 객체 생성
            bar_data = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                timeframe="1m",
                source="alpaca"
            )
            
            # 콜백 호출
            if self.on_bar:
                await self.on_bar({
                    "symbol": symbol,
                    "timestamp": timestamp.timestamp(),
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume
                })
                
        except Exception as e:
            logger.error(f"바 메시지 처리 오류: {e}")
    
    async def _websocket_heartbeat(self):
        """WebSocket 연결 상태 모니터링"""
        while self.is_connected:
            try:
                current_time = datetime.now(timezone.utc)
                time_diff = (current_time - self.last_heartbeat).total_seconds()
                
                # 120초 이상 메시지가 없으면 재연결
                if time_diff > 120:
                    logger.warning("WebSocket 하트비트 타임아웃 - 재연결 시도")
                    await self._attempt_reconnect()
                    break
                
                await asyncio.sleep(30)  # 30초마다 체크
                
            except Exception as e:
                logger.error(f"하트비트 모니터링 오류: {e}")
                await asyncio.sleep(30)
    
    async def _attempt_reconnect(self):
        """재연결 시도"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("최대 재연결 시도 횟수 초과 - 폴백 모드로 전환")
            await self._start_fallback_mode()
            return
        
        self.reconnect_attempts += 1
        wait_time = min(300, 2 ** self.reconnect_attempts)  # 최대 5분
        
        logger.info(f"재연결 시도 {self.reconnect_attempts}/{self.max_reconnect_attempts} - {wait_time}초 후")
        
        await asyncio.sleep(wait_time)
        
        try:
            await self._connect_websocket()
        except Exception as e:
            logger.error(f"재연결 실패: {e}")
            # 다시 재연결 시도
            asyncio.create_task(self._attempt_reconnect())
    
    async def stop_websocket(self):
        """WebSocket 연결 중지"""
        self.is_connected = False
        self.is_authenticated = False
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"WebSocket 종료 오류: {e}")
            finally:
                self.websocket = None
        
        logger.info("Alpaca WebSocket 연결 종료됨")
    
    # ================== 폴백 시스템 (yfinance) ==================
    
    async def _start_fallback_mode(self):
        """폴백 모드 시작 (yfinance 사용)"""
        logger.info("폴백 모드 시작 - yfinance 사용")
        
        if self.on_connection_change:
            await self.on_connection_change(False, "폴백 모드")
        
        # 폴백 데이터 수집기 시작
        asyncio.create_task(self._fallback_data_collector())
    
    async def _fallback_data_collector(self):
        """yfinance를 사용한 폴백 데이터 수집"""
        logger.info("폴백 데이터 수집기 시작")
        
        while not self.is_connected and self.subscribed_symbols:
            try:
                for symbol in self.subscribed_symbols:
                    # 핵심 매매 시간대에만 실행
                    if not self.is_core_trading_hours():
                        await asyncio.sleep(60)
                        continue
                    
                    try:
                        # yfinance로 최신 데이터 수집
                        stock = yf.Ticker(symbol)
                        
                        # 1분봉 데이터 수집
                        hist = stock.history(period='1d', interval='1m')
                        
                        if not hist.empty:
                            # 최신 바 데이터 생성
                            latest = hist.iloc[-1]
                            timestamp = hist.index[-1].to_pydatetime()
                            
                            # 폴백 바 데이터 콜백 호출
                            if self.on_bar:
                                await self.on_bar({
                                    "symbol": symbol,
                                    "timestamp": timestamp.timestamp(),
                                    "open": float(latest['Open']),
                                    "high": float(latest['High']),
                                    "low": float(latest['Low']),
                                    "close": float(latest['Close']),
                                    "volume": int(latest['Volume'])
                                })
                            
                            # 모의 거래 데이터 생성
                            if self.on_trade:
                                await self.on_trade({
                                    "symbol": symbol,
                                    "timestamp": timestamp.timestamp(),
                                    "price": float(latest['Close']),
                                    "size": int(latest['Volume'] / 100),  # 추정
                                    "conditions": []
                                })
                        
                    except Exception as e:
                        logger.warning(f"{symbol} 폴백 데이터 수집 실패: {e}")
                    
                    # API 속도 제한 고려
                    await asyncio.sleep(2)
                
                # 60초 간격으로 수집
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"폴백 데이터 수집 오류: {e}")
                await asyncio.sleep(30)
    
    # ================== 데이터 접근 메서드 ==================
    
    def get_realtime_data(self, symbol: str, timeframe: str = '1m', count: int = 100) -> pd.DataFrame:
        """실시간 데이터 조회"""
        return self.data_buffer.get_dataframe(symbol, timeframe, count)
    
    def get_latest_quote(self, symbol: str) -> Dict[str, Any]:
        """최신 호가 정보 조회"""
        # 실제로는 데이터 버퍼에서 최신 호가 반환
        # 여기서는 시뮬레이션
        return {
            "symbol": symbol,
            "bid_price": 0.0,
            "bid_size": 0,
            "ask_price": 0.0,
            "ask_size": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """서비스 통계 반환"""
        uptime = 0
        if hasattr(self, 'start_time'):
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        return {
            "is_connected": self.is_connected,
            "is_authenticated": self.is_authenticated,
            "subscribed_symbols": self.subscribed_symbols,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "reconnect_attempts": self.reconnect_attempts,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "uptime_seconds": uptime,
            "is_core_trading_hours": self.is_core_trading_hours(),
            "data_buffer_status": {
                "1m_symbols": len(self.data_buffer.buffers['1m']),
                "5m_symbols": len(self.data_buffer.buffers['5m']),
                "1h_symbols": len(self.data_buffer.buffers['1h'])
            }
        }

# 사용 예시
if __name__ == "__main__":
    async def test_alpaca_service():
        """완전한 AlpacaService 테스트"""
        
        # 환경 변수에서 API 키 로드 (실제 환경에서)
        api_key = "YOUR_ALPACA_API_KEY"
        secret_key = "YOUR_ALPACA_SECRET_KEY"
        
        async with AlpacaService(api_key, secret_key, paper=True) as alpaca:
            
            print("🔍 완전한 AlpacaService 테스트 시작")
            print("=" * 60)
            
            # 연결 테스트
            connection_ok = await alpaca.test_connection()
            print(f"📡 연결 테스트: {'✅ 성공' if connection_ok else '❌ 실패'}")
            
            if connection_ok:
                # 계정 정보 조회
                account_info = await alpaca.get_account_info()
                print(f"💰 계정 상태: {account_info.get('status', 'Unknown')}")
                
                # 과거 데이터 조회
                historical_data = await alpaca.get_historical_bars(
                    ['AAPL', 'TSLA'], '1Min', limit=100
                )
                print(f"📊 과거 데이터: {len(historical_data)} 심볼")
                
                # 콜백 함수 정의
                async def on_trade(trade_data):
                    print(f"🔄 거래: {trade_data['symbol']} ${trade_data['price']:.2f} x {trade_data['size']}")
                
                async def on_bar(bar_data):
                    print(f"📈 바: {bar_data['symbol']} C:${bar_data['close']:.2f} V:{bar_data['volume']:,}")
                
                async def on_connection_change(connected, message):
                    status = "🟢 연결됨" if connected else "🔴 끊어짐"
                    print(f"{status}: {message}")
                
                # WebSocket 시작
                await alpaca.start_websocket(
                    symbols=['AAPL', 'TSLA', 'MSFT'],
                    on_trade=on_trade,
                    on_bar=on_bar,
                    on_connection_change=on_connection_change
                )
                
                print("🚀 WebSocket 시작됨 - 30초간 데이터 수신...")
                
                # 30초간 실시간 데이터 수신
                await asyncio.sleep(30)
                
                # 통계 출력
                stats = alpaca.get_statistics()
                print(f"📈 통계:")
                print(f"   - 메시지 수신: {stats['message_count']}개")
                print(f"   - 오류 발생: {stats['error_count']}개")
                print(f"   - 재연결 시도: {stats['reconnect_attempts']}회")
                
                # 실시간 데이터 확인
                for symbol in ['AAPL', 'TSLA']:
                    df = alpaca.get_realtime_data(symbol, '1m', 10)
                    print(f"📊 {symbol} 최근 데이터: {len(df)}개 바")
            
            print("\n✅ 테스트 완료!")
    
    # 테스트 실행
    asyncio.run(test_alpaca_service())
