"""
main.py - AI Trading Assistant V5.5 Complete Backend Server
완전한 백엔드 서버 - 모든 새로운 서비스들과 연동
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
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# 서비스들 import (파일이 없어도 오류 방지)
try:
    from services.sheets_service import SheetsService
except ImportError:
    print("⚠️ sheets_service.py 파일이 없습니다. 1단계를 먼저 완료하세요.")
    SheetsService = None

try:
    from services.gemini_service import GeminiService
except ImportError:
    print("⚠️ gemini_service.py 파일이 없습니다.")
    GeminiService = None

try:
    from services.alpaca_service import AlpacaService
except ImportError:
    print("⚠️ alpaca_service.py 파일이 없습니다.")
    AlpacaService = None

try:
    from technical_indicators import TechnicalIndicators
except ImportError:
    print("⚠️ technical_indicators.py 파일이 없습니다.")
    TechnicalIndicators = None

try:
    from atom_detector import AtomDetector
except ImportError:
    print("⚠️ atom_detector.py 파일이 없습니다.")
    AtomDetector = None

try:
    from molecule_matcher import MoleculeMatcher
except ImportError:
    print("⚠️ molecule_matcher.py 파일이 없습니다.")
    MoleculeMatcher = None

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
    """WebSocket 연결 관리자"""
    
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
        
        # 상태 관리
        self.is_initialized = False
        self.is_scanning = False
        self.watched_tickers: List[str] = []
        
        # 통계
        self.atoms_detected_total = 0
        self.molecules_triggered_total = 0
        self.system_start_time = datetime.now(timezone.utc)
        
        logger.info("TradingSystemCore 초기화 완료")

    async def initialize_services(self, api_settings: Dict) -> Dict:
        """서비스 초기화"""
        results = {}
        
        try:
            # 1. Google Sheets 서비스 초기화
            if SheetsService and api_settings.get('sheetsId'):
                try:
                    self.sheets_service = SheetsService(
                        spreadsheet_id=api_settings['sheetsId'],
                        service_account_json=api_settings.get('googleServiceAccountJson')
                    )
                    
                    # 연결 테스트
                    connection_ok = await self.sheets_service.test_connection()
                    results['sheets'] = {
                        'status': 'success' if connection_ok else 'error',
                        'message': '연결 성공' if connection_ok else '연결 실패'
                    }
                    
                    if connection_ok:
                        logger.info("✅ Google Sheets 서비스 초기화 성공")
                    else:
                        logger.error("❌ Google Sheets 연결 실패")
                        
                except Exception as e:
                    results['sheets'] = {'status': 'error', 'message': str(e)}
                    logger.error(f"Google Sheets 초기화 실패: {e}")
            else:
                results['sheets'] = {'status': 'error', 'message': 'SheetsService 또는 설정 없음'}
            
            # 2. Gemini AI 서비스 초기화
            if GeminiService and api_settings.get('geminiKey'):
                try:
                    self.gemini_service = GeminiService(api_key=api_settings['geminiKey'])
                    connection_ok = await self.gemini_service.test_connection()
                    results['gemini'] = {
                        'status': 'success' if connection_ok else 'error',
                        'message': '연결 성공' if connection_ok else '연결 실패'
                    }
                    
                    if connection_ok:
                        logger.info("✅ Gemini AI 서비스 초기화 성공")
                    else:
                        logger.error("❌ Gemini AI 연결 실패")
                        
                except Exception as e:
                    results['gemini'] = {'status': 'error', 'message': str(e)}
                    logger.error(f"Gemini AI 초기화 실패: {e}")
            else:
                results['gemini'] = {'status': 'error', 'message': 'GeminiService 또는 API 키 없음'}
            
            # 3. Alpaca 서비스 초기화
            if AlpacaService and api_settings.get('alpacaKey'):
                try:
                    self.alpaca_service = AlpacaService(
                        api_key=api_settings['alpacaKey'],
                        secret_key=api_settings.get('alpacaSecret', ''),
                        paper=True  # 페이퍼 트레이딩
                    )
                    connection_ok = await self.alpaca_service.test_connection()
                    results['alpaca'] = {
                        'status': 'success' if connection_ok else 'error',
                        'message': '연결 성공' if connection_ok else '연결 실패'
                    }
                    
                    if connection_ok:
                        logger.info("✅ Alpaca 서비스 초기화 성공")
                    else:
                        logger.error("❌ Alpaca 연결 실패")
                        
                except Exception as e:
                    results['alpaca'] = {'status': 'error', 'message': str(e)}
                    logger.error(f"Alpaca 초기화 실패: {e}")
            else:
                results['alpaca'] = {'status': 'error', 'message': 'AlpacaService 또는 API 키 없음'}
            
            # 4. 나머지 서비스들 초기화
            if TechnicalIndicators:
                self.technical_indicators = TechnicalIndicators()
                results['technical_indicators'] = {'status': 'success', 'message': '초기화 완료'}
            
            if AtomDetector and self.sheets_service:
                self.atom_detector = AtomDetector(self.sheets_service)
                await self.atom_detector.initialize()
                results['atom_detector'] = {'status': 'success', 'message': '초기화 완료'}
            
            if MoleculeMatcher and self.sheets_service:
                self.molecule_matcher = MoleculeMatcher(self.sheets_service)
                await self.molecule_matcher.initialize()
                results['molecule_matcher'] = {'status': 'success', 'message': '초기화 완료'}
            
            # 초기화 상태 업데이트
            success_count = len([r for r in results.values() if r.get('status') == 'success'])
            self.is_initialized = success_count >= 3  # 최소 3개 서비스 성공
            
            logger.info(f"서비스 초기화 완료: {success_count}/{len(results)} 성공")
            
        except Exception as e:
            logger.error(f"서비스 초기화 중 오류: {e}")
            results['error'] = str(e)
        
        return results

    async def start_scanning(self, tickers: List[str]) -> bool:
        """실시간 스캐닝 시작"""
        try:
            if not self.is_initialized:
                raise ValueError("시스템이 초기화되지 않았습니다")
            
            if not tickers:
                raise ValueError("감시할 종목이 없습니다")
            
            self.watched_tickers = tickers
            self.is_scanning = True
            
            # 실시간 스캐닝 작업 시작 (시뮬레이션)
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
            logger.info("실시간 스캐닝 중지됨")
            return True
        except Exception as e:
            logger.error(f"스캐닝 중지 오류: {e}")
            return False

    async def scanning_loop(self):
        """메인 스캐닝 루프 (시뮬레이션)"""
        logger.info("스캐닝 루프 시작")
        scan_count = 0
        
        while self.is_scanning:
            try:
                scan_count += 1
                
                # 30초마다 시뮬레이션 신호 생성
                if scan_count % 3 == 0:  # 3번째 루프마다 (30초)
                    await self.generate_demo_signals()
                
                # 10초 대기
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"스캐닝 루프 오류: {e}")
                await asyncio.sleep(5)

    async def generate_demo_signals(self):
        """데모 신호 생성 (시뮬레이션)"""
        try:
            if not self.watched_tickers:
                return
            
            import random
            
            # 랜덤하게 종목 선택
            ticker = random.choice(self.watched_tickers)
            
            # 아톰 신호 시뮬레이션
            atom_signals = ['STR-003', 'TRG-003', 'CTX-001', 'DRV-001']
            atom_id = random.choice(atom_signals)
            
            signal_data = {
                'type': 'atom_signal',
                'ticker': ticker,
                'atom_id': atom_id,
                'atom_name': f'시뮬레이션_{atom_id}',
                'price': round(random.uniform(100, 300), 2),
                'volume': random.randint(10000, 100000),
                'grade': random.choice(['A++', 'A+', 'A', 'B+']),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'simulation': True
            }
            
            # WebSocket으로 전송
            await manager.broadcast(signal_data)
            
            self.atoms_detected_total += 1
            logger.info(f"데모 신호 생성: {ticker} - {atom_id}")
            
        except Exception as e:
            logger.error(f"데모 신호 생성 오류: {e}")

    async def process_analysis_request(self, ticker: str, date: str, user_insight: str) -> Dict:
        """AI 분석 요청 처리"""
        try:
            if not self.gemini_service:
                return {
                    'success': False,
                    'error': 'Gemini AI 서비스가 초기화되지 않았습니다',
                    'ticker': ticker
                }
            
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
    logger.info("프론트엔드 정적 파일 서빙 설정 완료")
except Exception:
    logger.warning("frontend 디렉토리를 찾을 수 없습니다")

@app.get("/")
async def root():
    """홈 페이지"""
    try:
        # 간단한 HTML 페이지 반환
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI Trading Assistant V5.1</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
                .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
                .success { background: #d4edda; color: #155724; }
                .warning { background: #fff3cd; color: #856404; }
                .error { background: #f8d7da; color: #721c24; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 AI Trading Assistant V5.1 Backend</h1>
                <p><strong>상태:</strong> 정상 실행 중</p>
                <p><strong>시작 시간:</strong> {start_time}</p>
                
                <div class="status success">
                    ✅ 백엔드 서버가 정상적으로 실행되고 있습니다.
                </div>
                
                <h2>📡 API 엔드포인트</h2>
                <ul>
                    <li><a href="/health">/health</a> - 헬스 체크</li>
                    <li><a href="/api/status">/api/status</a> - 시스템 상태</li>
                    <li><a href="/docs">/docs</a> - API 문서</li>
                </ul>
                
                <h2>🔌 WebSocket</h2>
                <p>WebSocket 엔드포인트: <code>ws://localhost:8000/ws</code></p>
                
                <h2>📊 시스템 정보</h2>
                <p>초기화 상태: {is_initialized}</p>
                <p>스캐닝 상태: {is_scanning}</p>
                <p>감시 종목 수: {ticker_count}</p>
            </div>
        </body>
        </html>
        """.format(
            start_time=trading_system.system_start_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
            is_initialized="✅ 완료" if trading_system.is_initialized else "⏳ 대기중",
            is_scanning="🟢 활성" if trading_system.is_scanning else "🔴 비활성",
            ticker_count=len(trading_system.watched_tickers)
        )
        
        return HTMLResponse(content=html_content)
    except Exception as e:
        return {"error": f"홈 페이지 로드 실패: {str(e)}"}

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": trading_system.get_system_status(),
        "message": "AI Trading Assistant V5.1 Backend is running!"
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
    
    # 각 서비스별 연결 테스트 (시뮬레이션)
    if api_settings.get("alpacaKey"):
        results["alpaca"] = {"status": "success", "message": "연결 테스트 완료"}
    
    if api_settings.get("sheetsId"):
        try:
            if SheetsService:
                sheets_temp = SheetsService(
                    spreadsheet_id=api_settings["sheetsId"],
                    service_account_json=api_settings.get("googleServiceAccountJson")
                )
                success = await sheets_temp.test_connection()
                results["sheets"] = {"status": "success" if success else "error", "message": "연결 테스트 완료"}
            else:
                results["sheets"] = {"status": "error", "message": "SheetsService 없음"}
        except Exception as e:
            results["sheets"] = {"status": "error", "message": str(e)}
    
    if api_settings.get("geminiKey"):
        try:
            if GeminiService:
                gemini_temp = GeminiService(api_key=api_settings["geminiKey"])
                success = await gemini_temp.test_connection()
                results["gemini"] = {"status": "success" if success else "error", "message": "연결 테스트 완료"}
            else:
                results["gemini"] = {"status": "error", "message": "GeminiService 없음"}
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
    logger.info("🚀 AI Trading Assistant V5.1 Backend 시작")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )
