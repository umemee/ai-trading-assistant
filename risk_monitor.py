"""
risk_monitor.py - 실시간 성과 모니터링 및 위험 관리 시스템

운영 중인 분자들의 실시간 성과 추적 및 자동 위험 관리
- Max Drawdown 추적 및 자동 전략 비활성화
- 실시간 성과 지표 계산 및 업데이트
- 위험 알림 생성 및 전송
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass
import json

from services.sheets_service import SheetsService
from environment_manager import get_current_env

logger = logging.getLogger(__name__)

@dataclass
class RiskAlert:
    """위험 알림 데이터 클래스"""
    alert_id: str
    molecule_id: str
    alert_type: str  # DRAWDOWN, CONSECUTIVE_LOSS, PERFORMANCE_DROP
    alert_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    current_value: float
    threshold: float
    triggered_date: str
    auto_action: str  # NONE, PAUSE, DISABLE
    alert_details: str

@dataclass
class PerformanceMetrics:
    """성과 지표 데이터 클래스"""
    molecule_id: str
    total_trades: int
    win_rate: float
    avg_return: float
    total_return: float
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
        self.env_config = get_current_env()
        
        # 위험 임계값 설정
        self.risk_thresholds = {
            'max_drawdown': -0.20,           # -20% 최대 손실
            'critical_drawdown': -0.15,      # -15% 위험 수준
            'warning_drawdown': -0.10,       # -10% 경고 수준
            'consecutive_losses': 10,         # 연속 손실 10회
            'min_sharpe_ratio': 0.5,         # 최소 샤프 비율
            'min_profit_factor': 1.2         # 최소 수익 팩터
        }
        
        # 모니터링 상태
        self.monitoring_active = True
        self.last_check_time = None
        self.performance_cache = {}
        
        logger.info("위험 모니터 초기화 완료")

    async def start_monitoring(self, check_interval: int = 300):
        """실시간 모니터링 시작 (5분 간격)"""
        logger.info("🔍 실시간 성과 모니터링 시작")
        
        while self.monitoring_active:
            try:
                await self.run_risk_check()
                self.last_check_time = datetime.now(timezone.utc)
                
                # 체크 간격만큼 대기
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"모니터링 오류: {e}")
                await asyncio.sleep(60)  # 오류 시 1분 후 재시도

    async def run_risk_check(self):
        """위험 체크 실행"""
        try:
            # 활성 분자들 조회
            active_molecules = await self.get_active_molecules()
            
            if not active_molecules:
                logger.info("활성 분자가 없습니다")
                return
            
            logger.info(f"위험 체크 시작: {len(active_molecules)}개 분자")
            
            alerts_generated = []
            
            for molecule in active_molecules:
                molecule_id = molecule.get('Molecule_ID')
                if not molecule_id:
                    continue
                
                # 성과 지표 계산
                performance = await self.calculate_performance_metrics(molecule_id)
                
                if performance:
                    # 위험 평가
                    alerts = await self.evaluate_risks(performance)
                    alerts_generated.extend(alerts)
                    
                    # 성과 지표 업데이트
                    await self.update_performance_dashboard(performance)
            
            # 위험 알림 처리
            if alerts_generated:
                await self.process_risk_alerts(alerts_generated)
                
            logger.info(f"위험 체크 완료: {len(alerts_generated)}개 알림")
            
        except Exception as e:
            logger.error(f"위험 체크 실행 실패: {e}")

    async def get_active_molecules(self) -> List[Dict]:
        """활성 분자들 조회"""
        try:
            molecules = await self.sheets_service.get_molecules()
            active_molecules = [
                m for m in molecules 
                if m.get('Status', '').lower() == 'active'
            ]
            return active_molecules
            
        except Exception as e:
            logger.error(f"활성 분자 조회 실패: {e}")
            return []

    async def calculate_performance_metrics(self, molecule_id: str) -> Optional[PerformanceMetrics]:
        """분자별 성과 지표 계산"""
        try:
            # SIDB에서 해당 분자의 거래 기록 조회
            trades = await self.get_molecule_trades(molecule_id)
            
            if not trades:
                return None
            
            # 기본 통계 계산
            total_trades = len(trades)
            winning_trades = [t for t in trades if t.get('realized_pnl', 0) > 0]
            losing_trades = [t for t in trades if t.get('realized_pnl', 0) < 0]
            
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
            
            # 수익률 계산
            returns = [t.get('realized_pnl', 0) for t in trades]
            total_return = sum(returns)
            avg_return = np.mean(returns) if returns else 0
            
            # 최대 손실폭 계산
            cumulative_returns = np.cumsum(returns)
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdowns = cumulative_returns - running_max
            max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0
            current_drawdown = drawdowns[-1] if len(drawdowns) > 0 else 0
            
            # 샤프 비율 계산
            if len(returns) > 1:
                std_return = np.std(returns)
                sharpe_ratio = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
            else:
                sharpe_ratio = 0
            
            # 수익 팩터 계산
            gross_profit = sum([r for r in returns if r > 0])
            gross_loss = abs(sum([r for r in returns if r < 0]))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0
            
            # 연속 손실 계산
            consecutive_losses = self.calculate_consecutive_losses(returns)
            
            return PerformanceMetrics(
                molecule_id=molecule_id,
                total_trades=total_trades,
                win_rate=win_rate,
                avg_return=avg_return,
                total_return=total_return,
                max_drawdown=max_drawdown,
                current_drawdown=current_drawdown,
                sharpe_ratio=sharpe_ratio,
                profit_factor=profit_factor,
                consecutive_losses=consecutive_losses,
                last_updated=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            logger.error(f"성과 지표 계산 실패: {e}")
            return None

    async def get_molecule_trades(self, molecule_id: str) -> List[Dict]:
        """분자별 거래 기록 조회 (SIDB에서)"""
        try:
            # SIDB에서 해당 분자의 거래 기록 조회
            sidb_data = await self.sheets_service.get_sidb_records()
            
            # 해당 분자와 관련된 거래만 필터링
            molecule_trades = [
                record for record in sidb_data
                if record.get('used_molecule_id') == molecule_id
                and record.get('realized_pnl') is not None
            ]
            
            return molecule_trades
            
        except Exception as e:
            logger.error(f"분자 거래 기록 조회 실패: {e}")
            return []

    def calculate_consecutive_losses(self, returns: List[float]) -> int:
        """연속 손실 횟수 계산"""
        if not returns:
            return 0
        
        consecutive = 0
        max_consecutive = 0
        
        # 뒤에서부터 계산 (최근 연속 손실)
        for ret in reversed(returns):
            if ret < 0:
                consecutive += 1
            else:
                break
        
        return consecutive

    async def evaluate_risks(self, performance: PerformanceMetrics) -> List[RiskAlert]:
        """위험 평가 및 알림 생성"""
        alerts = []
        
        try:
            # 1. 최대 손실폭 체크
            if performance.max_drawdown <= self.risk_thresholds['max_drawdown']:
                alerts.append(RiskAlert(
                    alert_id=f"DD_{performance.molecule_id}_{int(datetime.now().timestamp())}",
                    molecule_id=performance.molecule_id,
                    alert_type='DRAWDOWN',
                    alert_level='CRITICAL',
                    current_value=performance.max_drawdown,
                    threshold=self.risk_thresholds['max_drawdown'],
                    triggered_date=datetime.now(timezone.utc).isoformat(),
                    auto_action='DISABLE',
                    alert_details=f'최대 손실폭 {performance.max_drawdown:.1%} 초과'
                ))
            
            elif performance.max_drawdown <= self.risk_thresholds['critical_drawdown']:
                alerts.append(RiskAlert(
                    alert_id=f"DD_{performance.molecule_id}_{int(datetime.now().timestamp())}",
                    molecule_id=performance.molecule_id,
                    alert_type='DRAWDOWN',
                    alert_level='HIGH',
                    current_value=performance.max_drawdown,
                    threshold=self.risk_thresholds['critical_drawdown'],
                    triggered_date=datetime.now(timezone.utc).isoformat(),
                    auto_action='PAUSE',
                    alert_details=f'위험 수준 손실폭 {performance.max_drawdown:.1%}'
                ))
            
            # 2. 연속 손실 체크
            if performance.consecutive_losses >= self.risk_thresholds['consecutive_losses']:
                alerts.append(RiskAlert(
                    alert_id=f"CL_{performance.molecule_id}_{int(datetime.now().timestamp())}",
                    molecule_id=performance.molecule_id,
                    alert_type='CONSECUTIVE_LOSS',
                    alert_level='HIGH',
                    current_value=performance.consecutive_losses,
                    threshold=self.risk_thresholds['consecutive_losses'],
                    triggered_date=datetime.now(timezone.utc).isoformat(),
                    auto_action='PAUSE',
                    alert_details=f'연속 손실 {performance.consecutive_losses}회'
                ))
            
            # 3. 샤프 비율 체크
            if (performance.total_trades >= 20 and 
                performance.sharpe_ratio < self.risk_thresholds['min_sharpe_ratio']):
                alerts.append(RiskAlert(
                    alert_id=f"SR_{performance.molecule_id}_{int(datetime.now().timestamp())}",
                    molecule_id=performance.molecule_id,
                    alert_type='PERFORMANCE_DROP',
                    alert_level='MEDIUM',
                    current_value=performance.sharpe_ratio,
                    threshold=self.risk_thresholds['min_sharpe_ratio'],
                    triggered_date=datetime.now(timezone.utc).isoformat(),
                    auto_action='NONE',
                    alert_details=f'샤프 비율 저하 {performance.sharpe_ratio:.2f}'
                ))
            
            return alerts
            
        except Exception as e:
            logger.error(f"위험 평가 실패: {e}")
            return []

    async def process_risk_alerts(self, alerts: List[RiskAlert]):
        """위험 알림 처리"""
        try:
            for alert in alerts:
                # 자동 액션 실행
                if alert.auto_action == 'DISABLE':
                    await self.auto_disable_molecule(alert.molecule_id, alert.alert_details)
                elif alert.auto_action == 'PAUSE':
                    await self.auto_pause_molecule(alert.molecule_id, alert.alert_details)
                
                # 알림 기록
                await self.save_risk_alert(alert)
                
                # 로그 출력
                logger.warning(f"🚨 위험 알림: {alert.molecule_id} - {alert.alert_details}")
            
        except Exception as e:
            logger.error(f"위험 알림 처리 실패: {e}")

    async def auto_disable_molecule(self, molecule_id: str, reason: str):
        """자동 분자 비활성화"""
        try:
            # 분자 상태를 deprecated로 변경
            molecules = await self.sheets_service.get_molecules()
            
            for molecule in molecules:
                if molecule.get('Molecule_ID') == molecule_id:
                    molecule['Status'] = 'deprecated'
                    molecule['Auto_Disabled_Date'] = datetime.now(timezone.utc).isoformat()
                    molecule['Disable_Reason'] = reason
                    break
            
            # 실제 업데이트는 sheets_service에 구현 필요
            logger.critical(f"🔴 자동 비활성화: {molecule_id} - {reason}")
            
        except Exception as e:
            logger.error(f"자동 비활성화 실패: {e}")

    async def auto_pause_molecule(self, molecule_id: str, reason: str):
        """자동 분자 일시정지"""
        try:
            # 분자 상태를 paused로 변경
            molecules = await self.sheets_service.get_molecules()
            
            for molecule in molecules:
                if molecule.get('Molecule_ID') == molecule_id:
                    molecule['Status'] = 'paused'
                    molecule['Pause_Date'] = datetime.now(timezone.utc).isoformat()
                    molecule['Pause_Reason'] = reason
                    break
            
            logger.warning(f"⏸️ 자동 일시정지: {molecule_id} - {reason}")
            
        except Exception as e:
            logger.error(f"자동 일시정지 실패: {e}")

    async def update_performance_dashboard(self, performance: PerformanceMetrics):
        """성과 대시보드 업데이트"""
        try:
            # Performance_Dashboard 시트 업데이트
            dashboard_data = {
                'Molecule_ID': performance.molecule_id,
                'Total_Trades': performance.total_trades,
                'Win_Rate_%': performance.win_rate * 100,
                'Avg_Return': performance.avg_return,
                'Total_Return': performance.total_return,
                'Max_Drawdown_%': performance.max_drawdown * 100,
                'Current_Drawdown_%': performance.current_drawdown * 100,
                'Sharpe_Ratio': performance.sharpe_ratio,
                'Profit_Factor': performance.profit_factor,
                'Consecutive_Losses': performance.consecutive_losses,
                'Last_Updated': performance.last_updated,
                'Risk_Alert_Level': self.get_risk_level(performance)
            }
            
            # 실제 업데이트 로직 (sheets_service에 구현 필요)
            logger.info(f"성과 업데이트: {performance.molecule_id}")
            
        except Exception as e:
            logger.error(f"성과 대시보드 업데이트 실패: {e}")

    def get_risk_level(self, performance: PerformanceMetrics) -> str:
        """위험 등급 계산"""
        if performance.max_drawdown <= self.risk_thresholds['max_drawdown']:
            return 'CRITICAL'
        elif performance.max_drawdown <= self.risk_thresholds['critical_drawdown']:
            return 'HIGH'
        elif performance.max_drawdown <= self.risk_thresholds['warning_drawdown']:
            return 'MEDIUM'
        else:
            return 'LOW'

    async def save_risk_alert(self, alert: RiskAlert):
        """위험 알림 저장"""
        try:
            alert_data = {
                'Alert_ID': alert.alert_id,
                'Molecule_ID': alert.molecule_id,
                'Alert_Type': alert.alert_type,
                'Alert_Level': alert.alert_level,
                'Current_Value': alert.current_value,
                'Threshold': alert.threshold,
                'Triggered_Date': alert.triggered_date,
                'Auto_Action': alert.auto_action,
                'Alert_Details': alert.alert_details
            }
            
            # Risk_Alerts 시트에 저장 (구현 필요)
            logger.info(f"위험 알림 저장: {alert.alert_id}")
            
        except Exception as e:
            logger.error(f"위험 알림 저장 실패: {e}")

    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring_active = False
        logger.info("위험 모니터링 중지")

    async def get_monitoring_status(self) -> Dict:
        """모니터링 상태 조회"""
        try:
            active_molecules = await self.get_active_molecules()
            
            return {
                'monitoring_active': self.monitoring_active,
                'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
                'active_molecules_count': len(active_molecules),
                'environment': self.env_config.name,
                'risk_thresholds': self.risk_thresholds
            }
            
        except Exception as e:
            logger.error(f"모니터링 상태 조회 실패: {e}")
            return {}

# 사용 예시
if __name__ == "__main__":
    async def test_risk_monitor():
        """위험 모니터 테스트"""
        # sheets_service = SheetsService(...)  # 실제 사용 시 필요
        # risk_monitor = RiskMonitor(sheets_service)
        
        print("🔍 위험 모니터 테스트")
        print("실제 사용을 위해서는 sheets_service가 필요합니다")
        
        # 테스트 성과 데이터
        test_performance = PerformanceMetrics(
            molecule_id='TEST-001',
            total_trades=50,
            win_rate=0.45,
            avg_return=0.002,
            total_return=0.1,
            max_drawdown=-0.18,  # -18% (위험 수준)
            current_drawdown=-0.05,
            sharpe_ratio=0.8,
            profit_factor=1.3,
            consecutive_losses=3,
            last_updated=datetime.now(timezone.utc).isoformat()
        )
        
        risk_monitor = RiskMonitor(None)  # sheets_service 없이 테스트
        alerts = await risk_monitor.evaluate_risks(test_performance)
        
        print(f"생성된 알림: {len(alerts)}개")
        for alert in alerts:
            print(f"  - {alert.alert_type}: {alert.alert_details}")

    asyncio.run(test_risk_monitor())
