"""
risk_monitor.py - 실시간 성과 모니터링 및 위험 관리 시스템

운영 중인 분자들의 실시간 성과 추적 및 자동 위험 관리
- Max Drawdown 추적 및 자동 전략 비활성화
- 실시간 성과 지표 계산 및 업데이트
- 위험 알림 생성 및 자동 기록
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
import uuid

from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)

@dataclass
class RiskAlert:
    """위험 알림 데이터 클래스"""
    Alert_ID: str
    Molecule_ID: str
    Alert_Type: str
    Alert_Level: str
    Current_Drawdown: float
    Alert_Details: str
    Triggered_Date: str
    Auto_Action: str

@dataclass
class PerformanceMetrics:
    """성과 지표 데이터 클래스"""
    molecule_id: str
    total_trades: int
    win_rate: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    consecutive_losses: int
    last_updated: str

class RiskMonitor:
    """실시간 위험 관리 시스템"""
    
    def __init__(self, sheets_service: SheetsService):
        self.sheets_service = sheets_service
        
        self.risk_thresholds = {
            'max_drawdown': -0.20,
            'critical_drawdown': -0.15,
            'warning_drawdown': -0.10,
            'consecutive_losses': 10,
            'min_sharpe_ratio': 0.5,
            'min_profit_factor': 1.2
        }
        
        self.monitoring_active = False
        self.monitoring_task = None
        
        logger.info("RiskMonitor 초기화 완료")

    def start_monitoring(self, interval_seconds: int = 300):
        """실시간 모니터링 시작"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop(interval_seconds))
            logger.info(f"실시간 위험 모니터링 시작 (주기: {interval_seconds}초)")

    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            self.monitoring_task = None
        logger.info("실시간 위험 모니터링 중지")

    async def _monitoring_loop(self, interval_seconds: int):
        """모니터링 메인 루프"""
        while self.monitoring_active:
            try:
                await self.run_risk_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"모니터링 루프 중 오류 발생: {e}", exc_info=True)
            await asyncio.sleep(interval_seconds)

    async def run_risk_check(self):
        """모든 활성 분자에 대한 위험 체크 실행"""
        logger.info("활성 분자 위험 체크 시작...")
        molecules = await self.sheets_service.get_molecules()
        active_molecules = [m for m in molecules if m.get('Status', '').lower() == 'active']

        if not active_molecules:
            logger.info("모니터링할 활성 분자가 없습니다.")
            return

        for molecule in active_molecules:
            molecule_id = molecule.get('Molecule_ID')
            if not molecule_id:
                continue
            
            # 이 부분은 실제 거래 기록을 기반으로 계산해야 합니다.
            # 지금은 시뮬레이션 데이터를 사용합니다.
            performance = self._simulate_performance_metrics(molecule_id)
            
            if performance:
                alerts = self._evaluate_risks(performance)
                if alerts:
                    await self._process_risk_alerts(alerts)
                
                # 성과 대시보드 업데이트
                await self._update_performance_dashboard(performance)
    
    def _simulate_performance_metrics(self, molecule_id: str) -> PerformanceMetrics:
        """성과 지표 시뮬레이션 (실제로는 SIDB 거래 기록 기반으로 계산 필요)"""
        return PerformanceMetrics(
            molecule_id=molecule_id,
            total_trades=np.random.randint(20, 100),
            win_rate=np.random.uniform(0.4, 0.7),
            max_drawdown=-np.random.uniform(0.05, 0.25), # 5% ~ 25% 손실
            current_drawdown=-np.random.uniform(0, 0.1),
            sharpe_ratio=np.random.uniform(0.3, 1.5),
            profit_factor=np.random.uniform(0.8, 2.0),
            consecutive_losses=np.random.randint(0, 12),
            last_updated=datetime.now(timezone.utc).isoformat()
        )

    def _evaluate_risks(self, performance: PerformanceMetrics) -> List[RiskAlert]:
        """성과 지표를 바탕으로 위험 평가 및 알림 생성"""
        alerts = []
        # 최대 손실폭 체크
        if performance.max_drawdown <= self.risk_thresholds['max_drawdown']:
            alerts.append(RiskAlert(
                Alert_ID=f"DD_CRITICAL_{performance.molecule_id}_{uuid.uuid4().hex[:8]}",
                Molecule_ID=performance.molecule_id,
                Alert_Type='DRAWDOWN', Alert_Level='CRITICAL',
                Current_Drawdown=performance.max_drawdown,
                Alert_Details=f"최대 손실폭({performance.max_drawdown:.1%})이 임계치({self.risk_thresholds['max_drawdown']:.0%})를 초과했습니다.",
                Triggered_Date=datetime.now(timezone.utc).isoformat(), Auto_Action='DISABLE'
            ))
        # 연속 손실 체크
        if performance.consecutive_losses >= self.risk_thresholds['consecutive_losses']:
            alerts.append(RiskAlert(
                Alert_ID=f"CL_HIGH_{performance.molecule_id}_{uuid.uuid4().hex[:8]}",
                Molecule_ID=performance.molecule_id,
                Alert_Type='CONSECUTIVE_LOSS', Alert_Level='HIGH',
                Current_Drawdown=performance.current_drawdown, # 현재 MDD를 참고로 기록
                Alert_Details=f"연속 손실({performance.consecutive_losses}회)이 임계치({self.risk_thresholds['consecutive_losses']}회)에 도달했습니다.",
                Triggered_Date=datetime.now(timezone.utc).isoformat(), Auto_Action='PAUSE'
            ))
        return alerts

    async def _process_risk_alerts(self, alerts: List[RiskAlert]):
        """위험 알림 처리 (자동 조치 및 기록)"""
        for alert in alerts:
            logger.warning(f"🚨 위험 알림 발생: {alert.Molecule_ID} - {alert.Alert_Details}")
            
            # ✅ 1단계 수정: sheets_service의 새 함수 호출
            await self.sheets_service.save_risk_alert(asdict(alert))

            if alert.Auto_Action == 'DISABLE':
                await self._auto_disable_molecule(alert.Molecule_ID, alert.Alert_Details)
            elif alert.Auto_Action == 'PAUSE':
                # PAUSE 로직은 현재 update_molecule_info로 상태 변경 가능
                logger.warning(f"전략 일시정지 필요: {alert.Molecule_ID}")


    async def _auto_disable_molecule(self, molecule_id: str, reason: str):
        """자동으로 분자를 비활성화 (deprecated 상태로 변경)"""
        logger.critical(f"🔴 전략 자동 비활성화 실행: {molecule_id} | 사유: {reason}")
        
        # ✅ 1단계 수정: sheets_service의 업데이트 함수 호출
        update_payload = {
            "Status": "deprecated",
            "Auto_Disabled_Date": datetime.now(timezone.utc).isoformat(),
            "Disable_Reason": reason # 이 컬럼은 시트에 수동 추가 필요
        }
        success = await self.sheets_service.update_molecule_info(molecule_id, update_payload)
        
        if not success:
            logger.error(f"자동 비활성화 DB 업데이트 실패: {molecule_id}")

    async def _update_performance_dashboard(self, performance: PerformanceMetrics):
        """성과 대시보드 시트 업데이트"""
        logger.info(f"성과 대시보드 업데이트: {performance.molecule_id}")
        
        # ✅ 1단계 수정: sheets_service의 업데이트 함수 호출
        update_payload = {
            "Total_Trades": performance.total_trades,
            "Win_Rate_%": f"{performance.win_rate:.1%}",
            "Max_Drawdown_%": f"{performance.max_drawdown:.1%}",
            "Current_Drawdown_%": f"{performance.current_drawdown:.1%}",
            "Sharpe_Ratio": f"{performance.sharpe_ratio:.2f}",
            "Profit_Factor": f"{performance.profit_factor:.2f}",
            "Last_Updated": performance.last_updated
        }
        await self.sheets_service.update_molecule_info(performance.molecule_id, update_payload)
