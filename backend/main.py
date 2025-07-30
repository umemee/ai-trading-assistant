"""
AI Trading Assistant V5.5 - FastAPI Backend Server
실제 Python 로직을 실행하는 백엔드 서버
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from modules.signal_scanner import SignalScanner
from modules.logic_discoverer import LogicDiscoverer  
from modules.meta_learner import MetaLearner
from services.alpaca_service import AlpacaService
from services.sheets_service import SheetsService
from services.gemini_service import GeminiService
from utils.scheduler import TaskScheduler
from utils.database import DatabaseManager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket 연결 관리자"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected.append(connection)
        
        # 끊어진 연결 제거
        for conn in disconnected:
            self.disconnect(conn)

# 전역 객체들
manager = ConnectionManager()
signal_scanner: Optional[SignalScanner] = None
logic_discoverer: Optional[LogicDiscoverer] = None
meta_learner: Optional[MetaLearner] = None
task_scheduler: Optional[TaskScheduler] = None
database_manager: Optional[DatabaseManager] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 로직"""
    # 시작
    logger.info("🚀 AI Trading Assistant V5.5 Backend Starting...")
    
    global database_manager, task_scheduler
    database_manager = DatabaseManager()
    task_scheduler = TaskScheduler()
    
    # 스케줄러 시작
    task_scheduler.start()
    logger.info("✅ Task scheduler started")
    
    yield
    
    # 종료
    logger.info("🛑 AI Trading Assistant V5.5 Backend Shutting down...")
    if task_scheduler:
        task_scheduler.stop()
    if signal_scanner:
        await signal_scanner.stop()

# FastAPI 앱 생성
app = FastAPI(
    title="AI Trading Assistant V5.5",
    description="Complete AI Trading System with Real Backend",
    version="5.5.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 (프론트엔드)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    """홈 페이지"""
    return {"message": "AI Trading Assistant V5.5 Backend is running!"}

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "modules": {
            "signal_scanner": signal_scanner is not None and signal_scanner.is_running,
            "logic_discoverer": logic_discoverer is not None,
            "meta_learner": meta_learner is not None,
            "task_scheduler": task_scheduler is not None and task_scheduler.is_running,
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트 - 프론트엔드와 실시간 통신"""
    await manager.connect(websocket)
    
    try:
        # 환영 메시지
        await manager.send_personal_message({
            "type": "system_status",
            "message": "백엔드 서버와 연결되었습니다",
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)
        
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            message = json.loads(data)
            
            await handle_websocket_message(message, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def handle_websocket_message(message: dict, websocket: WebSocket):
    """WebSocket 메시지 처리"""
    message_type = message.get("type")
    
    try:
        if message_type == "start_scanner":
            await start_scanner_handler(message, websocket)
        elif message_type == "stop_scanner":
            await stop_scanner_handler(websocket)
        elif message_type == "request_analysis":
            await request_analysis_handler(message, websocket)
        elif message_type == "test_connection":
            await test_connection_handler(message, websocket)
        else:
            logger.warning(f"Unknown message type: {message_type}")
            
    except Exception as e:
        logger.error(f"Error handling message {message_type}: {e}")
        await manager.send_personal_message({
            "type": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)

async def start_scanner_handler(message: dict, websocket: WebSocket):
    """스캐너 시작 핸들러"""
    global signal_scanner
    
    tickers = message.get("tickers", [])
    api_settings = message.get("api_settings", {})
    
    if not tickers:
        raise ValueError("감시할 종목이 없습니다")
    
    if not api_settings.get("alpacaKey"):
        raise ValueError("Alpaca API 키가 설정되지 않았습니다")
    
    # SignalScanner 초기화
    if signal_scanner:
        await signal_scanner.stop()
    
    # 서비스 초기화
    alpaca_service = AlpacaService(
        api_key=api_settings["alpacaKey"],
        secret_key=api_settings["alpacaSecret"]
    )
    
    sheets_service = None
    if api_settings.get("sheetsId"):
        sheets_service = SheetsService(
            spreadsheet_id=api_settings["sheetsId"]
        )
    
    signal_scanner = SignalScanner(
        alpaca_service=alpaca_service,
        sheets_service=sheets_service,
        database_manager=database_manager
    )
    
    # 신호 콜백 설정
    signal_scanner.set_signal_callback(lambda signal: asyncio.create_task(
        manager.broadcast({
            "type": "atom_signal",
            "ticker": signal["ticker"],
            "atom_id": signal["atom_id"],
            "atom_name": signal["atom_name"],
            "price": signal["price"],
            "volume": signal["volume"],
            "grade": signal["grade"],
            "timestamp": signal["timestamp"]
        })
    ))
    
    signal_scanner.set_molecule_callback(lambda signal: asyncio.create_task(
        manager.broadcast({
            "type": "molecule_signal",
            "ticker": signal["ticker"],
            "molecule_id": signal["molecule_id"],
            "molecule_name": signal["molecule_name"],
            "grade": signal["grade"],
            "timestamp": signal["timestamp"]
        })
    ))
    
    # 스캐너 시작
    await signal_scanner.start(tickers)
    
    await manager.send_personal_message({
        "type": "system_status",
        "message": f"스캐너가 시작되었습니다. 감시 종목: {', '.join(tickers)}",
        "timestamp": datetime.utcnow().isoformat()
    }, websocket)

async def stop_scanner_handler(websocket: WebSocket):
    """스캐너 정지 핸들러"""
    global signal_scanner
    
    if signal_scanner:
        await signal_scanner.stop()
        signal_scanner = None
    
    await manager.send_personal_message({
        "type": "system_status",
        "message": "스캐너가 정지되었습니다",
        "timestamp": datetime.utcnow().isoformat()
    }, websocket)

async def request_analysis_handler(message: dict, websocket: WebSocket):
    """AI 분석 요청 핸들러"""
    global logic_discoverer
    
    ticker = message.get("ticker")
    context = message.get("context", "")
    api_settings = message.get("api_settings", {})
    
    if not api_settings.get("geminiKey"):
        raise ValueError("Gemini API 키가 설정되지 않았습니다")
    
    # LogicDiscoverer 초기화
    if not logic_discoverer:
        gemini_service = GeminiService(api_key=api_settings["geminiKey"])
        logic_discoverer = LogicDiscoverer(
            gemini_service=gemini_service,
            database_manager=database_manager
        )
    
    try:
        # AI 분석 실행
        result = await logic_discoverer.analyze_pattern(ticker, context)
        
        await manager.send_personal_message({
            "type": "analysis_result",
            "ticker": ticker,
            "success": True,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)
        
    except Exception as e:
        await manager.send_personal_message({
            "type": "analysis_result",
            "ticker": ticker,
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)

async def test_connection_handler(message: dict, websocket: WebSocket):
    """연결 테스트 핸들러"""
    api_settings = message.get("api_settings", {})
    results = {}
    
    # Alpaca 연결 테스트
    if api_settings.get("alpacaKey"):
        try:
            alpaca_service = AlpacaService(
                api_key=api_settings["alpacaKey"],
                secret_key=api_settings["alpacaSecret"]
            )
            await alpaca_service.test_connection()
            results["alpaca"] = {"status": "success", "message": "연결 성공"}
        except Exception as e:
            results["alpaca"] = {"status": "error", "message": str(e)}
    
    # Google Sheets 연결 테스트
    if api_settings.get("sheetsId"):
        try:
            sheets_service = SheetsService(spreadsheet_id=api_settings["sheetsId"])
            await sheets_service.test_connection()
            results["sheets"] = {"status": "success", "message": "연결 성공"}
        except Exception as e:
            results["sheets"] = {"status": "error", "message": str(e)}
    
    # Gemini 연결 테스트
    if api_settings.get("geminiKey"):
        try:
            gemini_service = GeminiService(api_key=api_settings["geminiKey"])
            await gemini_service.test_connection()
            results["gemini"] = {"status": "success", "message": "연결 성공"}
        except Exception as e:
            results["gemini"] = {"status": "error", "message": str(e)}
    
    await manager.send_personal_message({
        "type": "connection_test_result",
        "results": results,
        "timestamp": datetime.utcnow().isoformat()
    }, websocket)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
