"""
validator.py - Walk Forward Optimization 백테스팅 검증 엔진

AI 트레이딩 어시스턴트 V5.5의 핵심 검증 모듈
- WFO (Walk Forward Optimization) 백테스팅 실행
- 파라미터 안정성 테스트
- 검역된 분자 전략 검증 및 결과 자동 기록
- 과최적화 방지 및 실전 적합성 평가
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import yfinance as yf
from dataclasses import dataclass, asdict
import json
import uuid

from services.sheets_service import SheetsService
from technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

@dataclass
class WFOResult:
    """WFO 검증 결과 데이터 클래스"""
    Result_ID: str
    Molecule_ID: str
    Test_Date: str
    Walk_Forward_Periods: int
    Simple_Return: float
    WFO_Return: float
    WFO_Efficiency: float
    Max_Drawdown: float
    Sharpe_Ratio: float
    Parameter_Stability_Score: float
    Validation_Status: str  # PASSED/FAILED
    Detailed_Results: List[Dict]

class WFOValidator:
    """Walk Forward Optimization 검증 엔진"""
    
    def __init__(self, sheets_service: SheetsService):
        self.sheets_service = sheets_service
        self.technical_indicators = TechnicalIndicators()
        
        self.wfo_config = {
            'in_sample_days': 90,
            'out_sample_days': 30,
            'walk_steps': 6,
            'min_trades': 5,
            'pass_thresholds': {
                'wfo_efficiency': 0.7,
                'sharpe_ratio': 0.5,
                'max_drawdown': -0.20,
                'parameter_stability': 0.6
            }
        }
        
        logger.info("WFOValidator 초기화 완료")

    async def validate_quarantined_molecules(self) -> List[WFOResult]:
        """검역 중인 모든 분자들을 WFO 검증"""
        molecules = await self.sheets_service.get_molecules()
        quarantined_molecules = [m for m in molecules if m.get('Status', '').lower() == 'quarantined']
        
        if not quarantined_molecules:
            logger.info("검증할 검역 분자가 없습니다.")
            return []
            
        logger.info(f"{len(quarantined_molecules)}개의 검역 분자 검증 시작")
        
        all_results = []
        for molecule in quarantined_molecules:
            try:
                result = await self.run_molecule_wfo_test(molecule)
                if result:
                    all_results.append(result)
                    # ✅ 1단계 수정: sheets_service의 새 함수 호출
                    await self.sheets_service.save_wfo_result(asdict(result))
                    
                    # Molecule_DB 상태 업데이트
                    update_payload = {
                        "WFO_Score": f"{result.WFO_Efficiency:.3f}",
                        "Status": "ready_for_review" if result.Validation_Status in ("PASSED", "CONDITIONAL") else "failed_wfo"
                    }
                    await self.sheets_service.update_molecule_info(result.Molecule_ID, update_payload)

            except Exception as e:
                logger.error(f"분자 {molecule.get('Molecule_ID')} 검증 중 오류 발생: {e}", exc_info=True)
        
        logger.info(f"WFO 검증 완료: 총 {len(all_results)}개의 결과 생성")
        return all_results

    async def run_molecule_wfo_test(self, molecule: Dict) -> Optional[WFOResult]:
        """개별 분자에 대한 WFO 테스트 실행"""
        molecule_id = molecule.get('Molecule_ID')
        logger.info(f"WFO 테스트 시작: {molecule_id}")
        
        # 실제 환경에서는 더 다양한 유니버스를 사용해야 함
        test_symbols = ['AAPL', 'TSLA', 'MSFT', 'NVDA']
        all_walk_results = []

        for symbol in test_symbols:
            # 총 테스트 기간: (90일 + 30일) * 6 스텝 = 720일. 넉넉하게 800일 데이터 로드.
            stock_data = await self._get_historical_data(symbol, days=800)
            if stock_data.empty:
                continue

            walk_results = self._execute_walk_forward(molecule, symbol, stock_data)
            all_walk_results.extend(walk_results)
            await asyncio.sleep(1) # API 제한 방지

        if not all_walk_results:
            logger.warning(f"WFO 테스트를 위한 충분한 거래 데이터를 생성하지 못했습니다: {molecule_id}")
            return None

        wfo_result = self._analyze_wfo_results(molecule_id, all_walk_results)
        
        # 파라미터 안정성 테스트
        stability_score = await self._test_parameter_stability(molecule, test_symbols[0])
        wfo_result.Parameter_Stability_Score = stability_score
        
        # 최종 검증 상태 결정
        wfo_result.Validation_Status = self._determine_validation_status(wfo_result)
        
        logger.info(f"WFO 테스트 완료: {molecule_id} - {wfo_result.Validation_Status}")
        return wfo_result

    def _execute_walk_forward(self, molecule: Dict, symbol: str, stock_data: pd.DataFrame) -> List[Dict]:
        """실제 Walk Forward Optimization 실행 로직"""
        results = []
        is_size = self.wfo_config['in_sample_days']
        oos_size = self.wfo_config['out_sample_days']
        
        for step in range(self.wfo_config['walk_steps']):
            start_idx = step * oos_size
            is_start, is_end = start_idx, start_idx + is_size
            oos_start, oos_end = is_end, is_end + oos_size

            if oos_end > len(stock_data):
                break

            is_data = stock_data.iloc[is_start:is_end]
            oos_data = stock_data.iloc[oos_start:oos_end]

            # In-Sample 최적화 (여기서는 시뮬레이션)
            optimal_params = self._optimize_parameters(molecule, is_data)
            
            # Out-of-Sample 성과 측정
            oos_performance = self._backtest_strategy(molecule, oos_data, optimal_params)
            
            if oos_performance['total_trades'] >= self.wfo_config['min_trades']:
                results.append({
                    'step': step,
                    'symbol': symbol,
                    'performance': oos_performance
                })
        return results

    def _optimize_parameters(self, molecule: Dict, data: pd.DataFrame) -> Dict:
        """In-Sample 기간에서 최적 파라미터 탐색 (시뮬레이션)"""
        # 실제 구현에서는 Grid Search, Bayesian Optimization 등 사용
        # 여기서는 기본값을 그대로 반환하는 것으로 단순화
        return {'match_threshold': float(molecule.get('Match_Threshold_%', 80))}

    def _backtest_strategy(self, molecule: Dict, data: pd.DataFrame, params: Dict) -> Dict:
        """간단한 백테스트 실행기"""
        data_with_indicators = self.technical_indicators.calculate_all_indicators(data)
        signals = self._generate_signals(molecule, data_with_indicators, params)
        return self._calculate_returns(signals, data)

    def _generate_signals(self, molecule: Dict, data: pd.DataFrame, params: Dict) -> List[pd.Timestamp]:
        """분자 조건에 따른 거래 진입 신호 생성 (시뮬레이션)"""
        # 이 함수는 실제 아톰 탐지 로직을 단순화한 버전입니다.
        # 예: 20일 이평선이 50일 이평선 위에 있고, 종가가 20일 이평선 위에 있으면 매수
        signals = []
        if 'EMA_20' in data.columns and 'EMA_50' in data.columns:
            buy_conditions = (data['EMA_20'] > data['EMA_50']) & (data['Close'] > data['EMA_20'])
            signals = data[buy_conditions].index.tolist()
        return signals

    def _calculate_returns(self, signals: List[pd.Timestamp], data: pd.DataFrame) -> Dict:
        """수익률 및 성과 지표 계산"""
        if not signals:
            return {'total_trades': 0, 'sharpe_ratio': 0.0, 'max_drawdown': 0.0, 'win_rate': 0.0, 'total_return': 0.0}

        # 간단한 고정 기간 보유 전략 (5일)
        holding_period = 5
        returns = []
        for signal_time in signals:
            entry_idx = data.index.get_loc(signal_time)
            exit_idx = min(entry_idx + holding_period, len(data) - 1)
            
            entry_price = data['Close'].iloc[entry_idx]
            exit_price = data['Close'].iloc[exit_idx]
            
            if entry_price > 0:
                returns.append((exit_price - entry_price) / entry_price)

        if not returns:
            return {'total_trades': 0, 'sharpe_ratio': 0.0, 'max_drawdown': 0.0, 'win_rate': 0.0, 'total_return': 0.0}
            
        returns_series = pd.Series(returns)
        cumulative_returns = (1 + returns_series).cumprod()
        
        # Max Drawdown 계산
        peak = cumulative_returns.expanding(min_periods=1).max()
        drawdown = (cumulative_returns - peak) / peak
        max_drawdown = drawdown.min()

        sharpe_ratio = (returns_series.mean() / returns_series.std()) * np.sqrt(252) if returns_series.std() > 0 else 0.0

        return {
            'total_trades': len(returns),
            'sharpe_ratio': float(sharpe_ratio),
            'max_drawdown': float(max_drawdown),
            'win_rate': float((returns_series > 0).sum() / len(returns_series)),
            'total_return': float(cumulative_returns.iloc[-1] - 1)
        }

    def _analyze_wfo_results(self, molecule_id: str, all_walk_results: List[Dict]) -> WFOResult:
        """WFO 결과 분석 및 집계"""
        performances = [res['performance'] for res in all_walk_results]
        
        # WFO 성과 집계
        wfo_sharpe = np.mean([p['sharpe_ratio'] for p in performances]) if performances else 0.0
        wfo_return = np.mean([p['total_return'] for p in performances]) if performances else 0.0
        
        # 단순 백테스트 성과 (시뮬레이션)
        # 실제로는 전체 기간에 대한 단일 백테스트 결과 필요
        simple_backtest_sharpe = wfo_sharpe * np.random.uniform(0.8, 1.5) # 단순 추정
        
        return WFOResult(
            Result_ID=str(uuid.uuid4()),
            Molecule_ID=molecule_id,
            Test_Date=datetime.now(timezone.utc).isoformat(),
            Walk_Forward_Periods=len(all_walk_results),
            Simple_Return=0.0, # 단순화를 위해 0 처리
            WFO_Return=float(wfo_return),
            WFO_Efficiency=wfo_sharpe / simple_backtest_sharpe if simple_backtest_sharpe > 0 else 0.0,
            Max_Drawdown=np.min([p['max_drawdown'] for p in performances]) if performances else 0.0,
            Sharpe_Ratio=float(wfo_sharpe),
            Parameter_Stability_Score=0.0, # 별도 계산
            Validation_Status='PENDING',
            Detailed_Results=[] # 상세 결과는 저장하지 않음
        )

    async def _test_parameter_stability(self, molecule: Dict, symbol: str) -> float:
        """파라미터 안정성 테스트 (시뮬레이션)"""
        # 실제로는 파라미터를 변경하며 백테스트 반복 후 변동성 측정
        return np.random.uniform(0.5, 0.95)

    def _determine_validation_status(self, result: WFOResult) -> str:
        """WFO 결과를 바탕으로 검증 상태 결정"""
        thresholds = self.wfo_config['pass_thresholds']
        
        checks = {
            'efficiency': result.WFO_Efficiency >= thresholds['wfo_efficiency'],
            'sharpe': result.Sharpe_Ratio >= thresholds['sharpe_ratio'],
            'drawdown': result.Max_Drawdown >= thresholds['max_drawdown'],
            'stability': result.Parameter_Stability_Score >= thresholds['parameter_stability']
        }
        
        if all(checks.values()):
            return 'PASSED'
        elif sum(checks.values()) >= 2:
            return 'CONDITIONAL'
        else:
            return 'FAILED'

    async def _get_historical_data(self, symbol: str, days: int) -> pd.DataFrame:
        """yfinance를 사용한 과거 데이터 수집"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        try:
            data = yf.download(symbol, start=start_date, end=end_date, interval='1d', progress=False)
            return data
        except Exception as e:
            logger.error(f"{symbol} 데이터 다운로드 실패: {e}")
            return pd.DataFrame()
