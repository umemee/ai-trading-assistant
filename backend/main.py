"""
main.py - AI Trading Assistant V5.5 Complete Backend Server
완전한 백엔드 서버 - 모든 새로운 서비스들과 연동

주요 기능:
- Google Sheets API 완전 연동 (sheets_service.py)
- Google Gemini AI 완전 연동 (gemini_service.py)
- 실시간 아톰 탐지 및 분자 매칭
- WebSocket 실시간 통신
- 검역, 승인, 위험 관리 API 엔드포인트 제공
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
from pydantic import BaseModel

# --- 서비스 모듈 Import ---
from services.sheets_service import SheetsService
from services.gemini_service import GeminiService
from services.alpaca_service import AlpacaService
from technical_indicators import TechnicalIndicators
from atom_detector import AtomDetector
from molecule_matcher import MoleculeMatcher
from approval_manager import ApprovalManager
from quarantine_manager import QuarantineManager
from risk_monitor import RiskMonitor
from version_controller import VersionController
from environment_manager import get_env_manager, get_current_env, EnvironmentConfig

# --- 로깅 설정 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_assistant.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# --- 시스템 상태 및 서비스 관리 ---
class SystemServices:
    """모든 서비스 인스턴스를 관리하는 중앙 클래스"""
    def __init__(self):
        self.env_config: Optional[EnvironmentConfig] = None
        self.sheets: Optional[SheetsService] = None
        self.gemini: Optional[GeminiService] = None
        self.alpaca: Optional[AlpacaService] = None
        self.tech_indicators: Optional[TechnicalIndicators] = None
        self.atom_detector: Optional[AtomDetector] = None
        self.molecule_matcher: Optional[MoleculeMatcher] = None
        self.approval_manager: Optional[ApprovalManager] = None
        self.quarantine_manager: Optional[QuarantineManager] = None
        self.risk_monitor: Optional[RiskMonitor] = None
        self.version_controller: Optional[VersionController] = None
        self.is_initialized = False

    def initialize_services(self):
        """환경 설정을 기반으로 모든 서비스를 초기화합니다."""
        try:
            self.env_config = get_current_env()
            logger.info(f"'{self.env_config.name}' 환경으로 서비스 초기화 시작...")

            self.sheets = SheetsService(
                spreadsheet_id=self.env_config.sheets_id,
                credentials_path="credentials.json"
            )
            self.gemini = GeminiService(api_key=self.env_config.gemini_api_key)
            
            # alpaca_config = get_env_manager().get_alpaca_config()
            # self.alpaca = AlpacaService(api_key=alpaca_config['api_key'], secret_key=alpaca_config['secret_key'])

            self.tech_indicators = TechnicalIndicators()
            self.atom_detector = AtomDetector(self.sheets)
            self.molecule_matcher = MoleculeMatcher(self.sheets)
            self.approval_manager = ApprovalManager(self.sheets)
            self.quarantine_manager = QuarantineManager(self.sheets)
            self.risk_monitor = RiskMonitor(self.sheets)
            self.version_controller = VersionController(self.sheets)
            
            self.is_initialized = True
            logger.info("모든 서비스가 성공적으로 초기화되었습니다.")

        except Exception as e:
            logger.error(f"서비스 초기화 중 심각한 오류 발생: {e}", exc_info=True)
            self.is_initialized = False
            raise

# 전역 서비스 인스턴스
services = SystemServices()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 서비스 초기화"""
    load_dotenv()
    try:
        services.initialize_services()
        # 리스크 모니터 자동 시작
        if services.risk_monitor:
            services.risk_monitor.start_monitoring()
    except Exception as e:
        logger.critical(f"애플리케이션 시작 실패: {e}")
    yield
    # 앱 종료 시 정리
    if services.risk_monitor and services.risk_monitor.monitoring_active:
        services.risk_monitor.stop_monitoring()
    logger.info("애플리케이션 종료.")

# FastAPI 앱 생성
app = FastAPI(
    title="AI Trading Assistant V5.5",
    description="Complete AI Trading System with Full Integration",
    version="5.5.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# --- API 요청/응답 모델 ---
class ApprovalRequest(BaseModel):
    reviewer: str
    notes: str

class RejectionRequest(BaseModel):
    reviewer: str
    reason: str


# --- 기본 API 엔드포인트 ---
@app.get("/")
async def root():
    return {"message": "AI Trading Assistant V5.5 Backend is running!"}

@app.get("/api/status")
async def get_system_status():
    return {
        "is_initialized": services.is_initialized,
        "environment": services.env_config.name if services.env_config else "N/A",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# --- ✅ 2단계 목표: 승인 워크플로우 API 구현 ---

@app.get("/api/quarantine/list", response_model=List[Dict])
async def get_quarantine_list():
    """검토 대기 중인 분자 목록을 반환합니다."""
    if not services.is_initialized:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다.")
    try:
        queue = await services.approval_manager.get_quarantine_queue()
        return queue
    except Exception as e:
        logger.error(f"검역 큐 조회 API 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="검역 큐를 가져오는 중 오류 발생")

@app.post("/api/quarantine/approve/{molecule_id}", response_model=Dict)
async def approve_strategy(molecule_id: str, request: ApprovalRequest):
    """특정 분자를 승인하여 'active' 상태로 변경합니다."""
    if not services.is_initialized:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다.")
    try:
        success = await services.approval_manager.approve_molecule(
            molecule_id=molecule_id,
            approver=request.reviewer,
            approval_notes=request.notes
        )
        if success:
            return {"status": "success", "message": f"{molecule_id}가 성공적으로 승인되었습니다."}
        else:
            raise HTTPException(status_code=400, detail="분자 승인에 실패했습니다. 로그를 확인하세요.")
    except Exception as e:
        logger.error(f"분자 승인 API 오류 ({molecule_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="분자 승인 중 서버 오류 발생")

@app.post("/api/quarantine/reject/{molecule_id}", response_model=Dict)
async def reject_strategy(molecule_id: str, request: RejectionRequest):
    """특정 분자를 거부하여 'deprecated' 상태로 변경합니다."""
    if not services.is_initialized:
        raise HTTPException(status_code=503, detail="서비스가 초기화되지 않았습니다.")
    try:
        success = await services.approval_manager.reject_molecule(
            molecule_id=molecule_id,
            reviewer=request.reviewer,
            rejection_reason=request.reason
        )
        if success:
            return {"status": "success", "message": f"{molecule_id}가 거부 처리되었습니다."}
        else:
            raise HTTPException(status_code=400, detail="분자 거부에 실패했습니다. 로그를 확인하세요.")
    except Exception as e:
        logger.error(f"분자 거부 API 오류 ({molecule_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="분자 거부 중 서버 오류 발생")


# --- WebSocket (실시간 통신) ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 현재는 클라이언트로부터 메시지를 받지 않고, 서버에서 브로드캐스트만 하는 구조
            await asyncio.sleep(1) 
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket 클라이언트 연결 해제")


# --- 정적 파일 서빙 ---
# UI 파일이 위치할 경로를 지정합니다.
# app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")


if __name__ == "__main__":
    # 개발 서버 실행
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
