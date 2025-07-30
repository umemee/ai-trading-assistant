"""
main.py - AI Trading Assistant V5.1 Complete Backend Server
완전한 백엔드 서버 - 모든 새로운 서비스들과 연동

주요 기능:
- Google Sheets API 완전 연동 (sheets_service.py)
- Google Gemini AI 완전 연동 (gemini_service.py)  
- 실시간 아톰 탐지 (atom_detector.py)
- 분자 매칭 및 신호 생성 (molecule_matcher.py)
- 기술적 지표 계산 (technical_indicators.py)
- WebSocket 실시간 통신
- 완전한 에러 처리 및 로깅
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import traceback

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# 새로운 서비스들 import
from services.sheets_service import SheetsService
from services.gemini_service import GeminiService
from services.alpaca_service import AlpacaService
from technical_indicators import TechnicalIndicators
from atom_detector import AtomDetector, AtomSignal
from molecule_matcher import MoleculeMatcher, MoleculeMatchResult

# 기존 모듈들 import
from signal_scanner import SignalScanner

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_assistant.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ConnectionManager:
    """향상된 WebSocket 연결 관리자"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_info: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket):
        """클라이언트 연결"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_info[websocket] = {
            'connected_at': datetime.now(timezone.utc),
            'client_id': str(uuid.uuid4())[:8]
        }
        logger.info(f"클라이언트 연결됨. 총 연결: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """클라이언트 연결 해제"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            if websocket in self.connection_info:
                del self.connection_info[websocket]
            logger.info(f"클라이언트 연결 해제됨. 총 연결: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """개인 메시지 전송"""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.error(f"개인 메시지 전송 오류: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """모든 클라이언트에 브로드캐스트"""
        if not self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message, ensure_ascii=False))
            except Exception as e:
                logger.error(f"브로드캐스트 오류: {e}")
                disconnected.append(connection)
        
        # 끊어진 연결 정리
        for conn in disconnected:
            self.disconnect(conn)

class TradingSystemCore:
    """트레이딩 시스템 핵심 클래스"""
    
    def __init__(self):
        # 서비스 인스턴스들
        self.sheets_service: Optional[SheetsService] = None
        self.gemini_service: Optional[GeminiService] = None
        self.alpaca_service: Optional[AlpacaService] = None
        self.technical_indicators: Optional[TechnicalIndicators] = None
        self.atom_detector: Optional[AtomDetector] = None
        self.molecule_matcher: Optional[MoleculeMatcher] = None
        self.signal_scanner: Optional[SignalScanner] = None
        
        # 상태 관리
        self.is_initialized = False
        self.is_scanning = False
        self.watched_tickers: List[str] = []
        
        # 통계
        self.atoms_detected_total = 0
        self.molecules_triggered_total = 0
        self.system_start_time = datetime.now(timezone.utc)
        
        logger.info("TradingSystemCore 초기화 완료")
    
    async def initialize_services(self, api_settings: Dict[str, str]) -> Dict[str, bool]:
        """모든 서비스 초기화"""
        initialization_results = {}
        
        try:
            # 1. Google Sheets 서비스 초기화
            if api_settings.get('sheetsId') and api_settings.get('googleServiceAccountJson'):
                try:
                    self.sheets_service = SheetsService(
                        spreadsheet_id=api_settings['sheetsId'],
                        service_account_json=api_settings['googleServiceAccountJson']
                    )
                    connection_ok = await self.sheets_service.test_connection()
                    initialization_results['sheets'] = connection_ok
                    logger.info("Google Sheets 서비스 초기화 완료")
                except Exception as e:
                    logger.error(f"Google Sheets 초기화 실패: {e}")
                    initialization_results['sheets'] = False
            
            # 2. Gemini AI 서비스 초기화
            if api_settings.get('geminiKey'):
                try:
                    self.gemini_service = GeminiService(api_key=api_settings['geminiKey'])
                    connection_ok = await self.gemini_service.test_connection()
                    initialization_results['gemini'] = connection_ok
                    logger.info("Gemini AI 서비스 초기화 완료")
                except Exception as e:
                    logger.error(f"Gemini AI 초기화 실패: {e}")
                    initialization_results['gemini'] = False
            
            # 3. Alpaca 서비스 초기화
            if api_settings.get('alpacaKey') and api_settings.get('alpacaSecret'):
                try:
                    self.alpaca_service = AlpacaService(
                        api_key=api_settings['alpacaKey'],
                        secret_key=api_settings['alpacaSecret'],
                        paper=True
                    )
                    connection_ok = await self.alpaca_service.test_connection()
                    initialization_results['alpaca'] = connection_ok
                    logger.info("Alpaca 서비스 초기화 완료")
                except Exception as e:
                    logger.error(f"Alpaca 초기화 실패: {e}")
                    initialization_results['alpaca'] = False
            
            # 4. 기술적 지표 계산기 초기화
            self.technical_indicators = TechnicalIndicators()
            initialization_results['technical_indicators'] = True
            logger.info("기술적 지표 계산기 초기화 완료")
            
            # 5. 아톰 탐지기 초기화
            self.atom_detector = AtomDetector(sheets_service=self.sheets_service)
            await self.atom_detector.initialize()
            initialization_results['atom_detector'] = True
            logger.info("아톰 탐지기 초기화 완료")
            
            # 6. 분자 매칭기 초기화
            self.molecule_matcher = MoleculeMatcher(sheets_service=self.sheets_service)
            await self.molecule_matcher.initialize()
            initialization_results['molecule_matcher'] = True
            logger.info("분자 매칭기 초기화 완료")
            
            # 7. 기존 시그널 스캐너 초기화 (호환성)
            if self.alpaca_service:
                self.signal_scanner = SignalScanner(
                    alpaca_service=self.alpaca_service,
                    sheets_service=self.sheets_service
                )
                initialization_results['signal_scanner'] = True
                logger.info("시그널 스캐너 초기화 완료")
            
            self.is_initialized = True
            logger.info("모든 서비스 초기화 완료")
            
        except Exception as e:
            logger.error(f"서비스 초기화 중 오류: {e}")
            logger.error(traceback.format_exc())
        
        return initialization_results
    
    async def start_scanning(self, tickers: List[str]) -> bool:
        """실시간 스캐닝 시작"""
        try:
            if not self.is_initialized:
                raise ValueError("시스템이 초기화되지 않았습니다")
            
            if not tickers:
                raise ValueError("감시할 종목이 없습니다")
            
            self.watched_tickers = tickers
            self.is_scanning = True
            
            # 실시간 스캐닝 작업 시작
            asyncio.create_task(self.scanning_loop())
            
            logger.info(f"실시간 스캐닝 시작: {tickers}")
            return True
            
        except Exception as e:
            logger.error(f"스캐닝 시작 오류: {e}")
            return False
    
    async def stop_scanning(self) -> bool:
        """실시간 스캐닝 중지"""
        try:
            self.is_scanning = False
            self.watched_tickers = []
            
            if self.signal_scanner:
                await self.signal_scanner.stop()
            
            logger.info("실시간 스캐닝 중지됨")
            return True
            
        except Exception as e:
            logger.error(f"스캐닝 중지 오류: {e}")
            return False
    
    async def scanning_loop(self):
        """메인 스캐닝 루프"""
        logger.info("스캐닝 루프 시작")
        
        while self.is_scanning:
            try:
                for ticker in self.watched_tickers:
                    # 각 종목에 대해 아톰 탐지 실행
                    detected_atoms = await self.atom_detector.detect_atoms_for_ticker(ticker)
                    
                    if detected_atoms:
                        # 탐지된 아톰들 처리
                        for atom_signal in detected_atoms:
                            await self.process_atom_signal(atom_signal)
                    
                    # CPU 과부하 방지
                    await asyncio.sleep(1)
                
                # 스캔 간격 (30초)
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"스캐닝 루프 오류: {e}")
                await asyncio.sleep(5)
    
    async def process_atom_signal(self, atom_signal: AtomSignal):
        """아톰 신호 처리"""
        try:
            self.atoms_detected_total += 1
            
            # 아톰 신호를 분자 매칭기에 전달
            atom_data = {
                'timestamp_utc': atom_signal.timestamp_utc,
                'ticker': atom_signal.ticker,
                'atom_id': atom_signal.atom_id,
                'grade': atom_signal.grade,
                'confidence_score': atom_signal.confidence_score
            }
            
            await self.molecule_matcher.on_atom_signal(atom_data)
            
            # WebSocket으로 클라이언트에 전송
            await manager.broadcast({
                'type': 'atom_signal',
                'ticker': atom_signal.ticker,
                'atom_id': atom_signal.atom_id,
                'atom_name': atom_signal.atom_name,
                'price': atom_signal.price_at_signal,
                'volume': atom_signal.volume_at_signal,
                'grade': atom_signal.grade,
                'timestamp': atom_signal.timestamp_utc
            })
            
            logger.info(f"아톰 신호 처리 완료: {atom_signal.ticker} - {atom_signal.atom_id}")
            
        except Exception as e:
            logger.error(f"아톰 신호 처리 오류: {e}")
    
    async def process_analysis_request(self, ticker: str, date: str, user_insight: str) -> Dict:
        """AI 분석 요청 처리"""
        try:
            if not self.gemini_service:
                raise ValueError("Gemini AI 서비스가 초기화되지 않았습니다")
            
            # Gemini AI로 패턴 분석 실행
            result = await self.gemini_service.analyze_pattern(
                ticker=ticker,
                date=date,
                user_insight=user_insight
            )
            
            logger.info(f"AI 분석 완료: {ticker}")
            return result
            
        except Exception as e:
            logger.error(f"AI 분석 오류: {e}")
            return {
                'success': False,
                'error': str(e),
                'ticker': ticker
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 반환"""
        uptime = datetime.now(timezone.utc) - self.system_start_time
        
        return {
            'is_initialized': self.is_initialized,
            'is_scanning': self.is_scanning,
            'watched_tickers': self.watched_tickers,
            'atoms_detected_total': self.atoms_detected_total,
            'molecules_triggered_total': self.molecules_triggered_total,
            'uptime_seconds': int(uptime.total_seconds()),
            'services': {
                'sheets': self.sheets_service is not None,
                'gemini': self.gemini_service is not None,
                'alpaca': self.alpaca_service is not None,
                'atom_detector': self.atom_detector is not None,
                'molecule_matcher': self.molecule_matcher is not None
            }
        }

# 전역 객체들
manager = ConnectionManager()
trading_system = TradingSystemCore()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 로직"""
    # 시작
    logger.info("🚀 AI Trading Assistant V5.1 Backend Starting...")
    
    # 환경 변수에서 기본 설정 로드
    default_settings = {
        'sheetsId': os.getenv('GOOGLE_SPREADSHEET_ID'),
        'googleServiceAccountJson': os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON'),
        'geminiKey': os.getenv('GEMINI_API_KEY'),
        'alpacaKey': os.getenv('ALPACA_API_KEY'),
        'alpacaSecret': os.getenv('ALPACA_SECRET_KEY')
    }
    
    # 설정이 있으면 자동 초기화
    if any(default_settings.values()):
        logger.info("환경 변수에서 설정 발견 - 자동 초기화 시작")
        await trading_system.initialize_services(default_settings)
    
    yield
    
    # 종료
    logger.info("🛑 AI Trading Assistant V5.1 Backend Shutting down...")
    await trading_system.stop_scanning()

# FastAPI 앱 생성
app = FastAPI(
    title="AI Trading Assistant V5.1",
    description="Complete AI Trading System with Full Integration",
    version="5.1.0",
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
try:
    app.mount("/static", StaticFiles(directory="frontend"), name="static")
except Exception:
    logger.warning("frontend 디렉토리를 찾을 수 없습니다")

@app.get("/")
async def root():
    """홈 페이지"""
    return {
        "message": "AI Trading Assistant V5.1 Backend is running!",
        "status": "active",
        "version": "5.1.0",
        "system_status": trading_system.get_system_status()
    }

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": trading_system.get_system_status()
    }

@app.get("/api/status")
async def get_system_status():
    """시스템 상태 API"""
    return trading_system.get_system_status()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트 - 프론트엔드와 실시간 통신"""
    await manager.connect(websocket)
    
    try:
        # 환영 메시지
        await manager.send_personal_message({
            "type": "system_status",
            "message": "AI Trading Assistant V5.1 백엔드와 연결되었습니다",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_info": trading_system.get_system_status()
        }, websocket)
        
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            message = json.loads(data)
            await handle_websocket_message(message, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        manager.disconnect(websocket)

async def handle_websocket_message(message: dict, websocket: WebSocket):
    """WebSocket 메시지 처리"""
    message_type = message.get("type")
    
    try:
        if message_type == "initialize_system":
            await initialize_system_handler(message, websocket)
        elif message_type == "start_scanner":
            await start_scanner_handler(message, websocket)
        elif message_type == "stop_scanner":
            await stop_scanner_handler(websocket)
        elif message_type == "request_analysis":
            await request_analysis_handler(message, websocket)
        elif message_type == "test_connection":
            await test_connection_handler(message, websocket)
        elif message_type == "get_system_status":
            await get_system_status_handler(websocket)
        else:
            logger.warning(f"알 수 없는 메시지 타입: {message_type}")
            
    except Exception as e:
        logger.error(f"메시지 처리 오류 ({message_type}): {e}")
        logger.error(traceback.format_exc())
        await manager.send_personal_message({
            "type": "error",
            "message": f"오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)

async def initialize_system_handler(message: dict, websocket: WebSocket):
    """시스템 초기화 핸들러"""
    api_settings = message.get("api_settings", {})
    
    if not api_settings:
        raise ValueError("API 설정이 필요합니다")
    
    # 시스템 초기화 실행
    results = await trading_system.initialize_services(api_settings)
    
    await manager.send_personal_message({
        "type": "system_initialized",
        "success": trading_system.is_initialized,
        "results": results,
        "message": "시스템 초기화 완료" if trading_system.is_initialized else "일부 서비스 초기화 실패",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, websocket)

async def start_scanner_handler(message: dict, websocket: WebSocket):
    """스캐너 시작 핸들러"""
    tickers = message.get("tickers", [])
    api_settings = message.get("api_settings", {})
    
    if not tickers:
        raise ValueError("감시할 종목이 없습니다")
    
    # 시스템이 초기화되지 않았으면 먼저 초기화
    if not trading_system.is_initialized and api_settings:
        await trading_system.initialize_services(api_settings)
    
    if not trading_system.is_initialized:
        raise ValueError("시스템이 초기화되지 않았습니다. API 설정을 확인하세요.")
    
    # 스캐너 시작
    success = await trading_system.start_scanning(tickers)
    
    if success:
        await manager.send_personal_message({
            "type": "scanner_started",
            "message": f"스캐너가 시작되었습니다. 감시 종목: {', '.join(tickers)}",
            "tickers": tickers,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
    else:
        raise ValueError("스캐너 시작에 실패했습니다")

async def stop_scanner_handler(websocket: WebSocket):
    """스캐너 정지 핸들러"""
    success = await trading_system.stop_scanning()
    
    await manager.send_personal_message({
        "type": "scanner_stopped",
        "message": "스캐너가 정지되었습니다",
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, websocket)

async def request_analysis_handler(message: dict, websocket: WebSocket):
    """AI 분석 요청 핸들러"""
    ticker = message.get("ticker", "")
    date = message.get("date", "")
    context = message.get("context", "")
    
    if not ticker or not context:
        raise ValueError("티커와 분석 컨텍스트가 필요합니다")
    
    # AI 분석 실행
    result = await trading_system.process_analysis_request(ticker, date, context)
    
    await manager.send_personal_message({
        "type": "analysis_result",
        "ticker": ticker,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, websocket)

async def test_connection_handler(message: dict, websocket: WebSocket):
    """연결 테스트 핸들러"""
    api_settings = message.get("api_settings", {})
    results = {}
    
    # 각 서비스별 연결 테스트
    if api_settings.get("alpacaKey"):
        try:
            alpaca_temp = AlpacaService(
                api_key=api_settings["alpacaKey"],
                secret_key=api_settings.get("alpacaSecret", "")
            )
            success = await alpaca_temp.test_connection()
            results["alpaca"] = {"status": "success" if success else "error", "message": "연결 테스트 완료"}
        except Exception as e:
            results["alpaca"] = {"status": "error", "message": str(e)}
    
    if api_settings.get("sheetsId"):
        try:
            sheets_temp = SheetsService(
                spreadsheet_id=api_settings["sheetsId"],
                service_account_json=api_settings.get("googleServiceAccountJson")
            )
            success = await sheets_temp.test_connection()
            results["sheets"] = {"status": "success" if success else "error", "message": "연결 테스트 완료"}
        except Exception as e:
            results["sheets"] = {"status": "error", "message": str(e)}
    
    if api_settings.get("geminiKey"):
        try:
            gemini_temp = GeminiService(api_key=api_settings["geminiKey"])
            success = await gemini_temp.test_connection()
            results["gemini"] = {"status": "success" if success else "error", "message": "연결 테스트 완료"}
        except Exception as e:
            results["gemini"] = {"status": "error", "message": str(e)}
    
    await manager.send_personal_message({
        "type": "connection_test_result",
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, websocket)

async def get_system_status_handler(websocket: WebSocket):
    """시스템 상태 조회 핸들러"""
    status = trading_system.get_system_status()
    
    await manager.send_personal_message({
        "type": "system_status_response",
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, websocket)

# 에러 핸들러
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"전역 예외 발생: {exc}")
    logger.error(traceback.format_exc())
    return {"error": "내부 서버 오류가 발생했습니다", "detail": str(exc)}

if __name__ == "__main__":
    # 개발 서버 실행
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )
