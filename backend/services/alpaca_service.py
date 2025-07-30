"""
Alpaca Service - 실시간 시장 데이터 연동
WebSocket을 통한 실시간 데이터 스트리밍
"""

import asyncio
import json
import logging
import websockets
from typing import Dict, List, Callable, Optional
import ssl

logger = logging.getLogger(__name__)

class AlpacaService:
    """Alpaca Markets API 서비스"""
    
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        
        # WebSocket URLs
        if paper:
            self.ws_url = "wss://stream.data.alpaca.markets/v2/sip"
        else:
            self.ws_url = "wss://stream.data.alpaca.markets/v2/sip"
            
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        
        # 콜백 함수들
        self.on_quote: Optional[Callable] = None
        self.on_trade: Optional[Callable] = None
        self.on_bar: Optional[Callable] = None
    
    async def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            # 간단한 인증 테스트
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with websockets.connect(self.ws_url, ssl=ssl_context) as websocket:
                # 인증 메시지 전송
                auth_message = {
                    "action": "auth",
                    "key": self.api_key,
                    "secret": self.secret_key
                }
                await websocket.send(json.dumps(auth_message))
                
                # 응답 대기
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                response_data = json.loads(response)
                
                if response_data.get("T") == "success":
                    logger.info("Alpaca connection test successful")
                    return True
                else:
                    logger.error(f"Alpaca auth failed: {response_data}")
                    return False
                    
        except Exception as e:
            logger.error(f"Alpaca connection test failed: {e}")
            return False
    
    async def start_websocket(self, symbols: List[str], 
                              on_quote: Optional[Callable] = None,
                              on_trade: Optional[Callable] = None,
                              on_bar: Optional[Callable] = None):
        """WebSocket 연결 시작"""
        self.on_quote = on_quote
        self.on_trade = on_trade  
        self.on_bar = on_bar
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.websocket = await websockets.connect(self.ws_url, ssl=ssl_context)
            self.is_connected = True
            
            # 인증
            auth_message = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.secret_key
            }
            await self.websocket.send(json.dumps(auth_message))
            
            # 구독 설정
            subscribe_message = {
                "action": "subscribe",
                "quotes": symbols,
                "trades": symbols,  
                "bars": symbols
            }
            await self.websocket.send(json.dumps(subscribe_message))
            
            logger.info(f"Alpaca WebSocket connected and subscribed to: {symbols}")
            
            # 메시지 수신 루프 시작
            asyncio.create_task(self.message_handler_loop())
            
        except Exception as e:
            logger.error(f"Failed to start Alpaca WebSocket: {e}")
            self.is_connected = False
            # 데모 모드로 폴백
            asyncio.create_task(self.demo_data_generator(symbols))
    
    async def stop_websocket(self):
        """WebSocket 연결 중지"""
        self.is_connected = False
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        logger.info("Alpaca WebSocket disconnected")
    
    async def message_handler_loop(self):
        """WebSocket 메시지 처리 루프"""
        try:
            while self.is_connected and self.websocket:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                # 메시지 타입별 처리
                if isinstance(data, list):
                    for item in data:
                        await self.process_message(item)
                else:
                    await self.process_message(data)
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Alpaca WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error in message handler loop: {e}")
            self.is_connected = False
    
    async def process_message(self, message: Dict):
        """개별 메시지 처리"""
        msg_type = message.get("T")
        
        if msg_type == "q" and self.on_quote:  # Quote
            await self.on_quote(message)
        elif msg_type == "t" and self.on_trade:  # Trade
            await self.on_trade(message)
        elif msg_type == "b" and self.on_bar:  # Bar
            await self.on_bar(message)
        elif msg_type == "error":
            logger.error(f"Alpaca WebSocket error: {message}")
    
    async def demo_data_generator(self, symbols: List[str]):
        """데모 데이터 생성기 (Alpaca 연결 실패 시 사용)"""
        logger.info("Starting demo data generator")
        
        import random
        
        while self.is_connected:
            try:
                for symbol in symbols:
                    # 랜덤 바 데이터 생성
                    bar_data = {
                        "T": "b",
                        "symbol": symbol,
                        "timestamp": asyncio.get_event_loop().time(),
                        "open": random.uniform(50, 200),
                        "high": random.uniform(55, 205),
                        "low": random.uniform(45, 195),
                        "close": random.uniform(50, 200),
                        "volume": random.randint(10000, 1000000)
                    }
                    
                    if self.on_bar:
                        await self.on_bar(bar_data)
                    
                    # 랜덤 거래 데이터 생성
                    if random.random() < 0.7:  # 70% 확률
                        trade_data = {
                            "T": "t",
                            "symbol": symbol,
                            "timestamp": asyncio.get_event_loop().time(),
                            "price": random.uniform(50, 200),
                            "size": random.randint(100, 10000)
                        }
                        
                        if self.on_trade:
                            await self.on_trade(trade_data)
                
                await asyncio.sleep(15)  # 15초 간격
                
            except Exception as e:
                logger.error(f"Error in demo data generator: {e}")
                await asyncio.sleep(5)
