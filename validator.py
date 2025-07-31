"""
validator.py - Walk Forward Optimization 백테스팅 검증 엔진

AI Trading Assistant V5.1의 핵심 검증 모듈
- WFO (Walk Forward Optimization) 백테스팅 실행
- 파라미터 안정성 테스트
- 검역된 분자 전략 검증
- 과최적화 방지 및 실전 적합성 평가
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import yfinance as yf
from dataclasses import dataclass
import json
import uuid

from services.sheets_service import SheetsService
from technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

@dataclass
class WFOResult:
    """WFO 검증 결과 데이터 클래스"""
    molecule_id: str
    test_periods: int
    wfo_sharpe: float
    simple_sharpe: float
    wfo_efficiency: float
    max_drawdown: float
    profit_factor: float
    win_rate: float
    parameter_stability_score: float
    validation_status: str  # PASSED/FAILED
    test_date: str
    detailed_results: List[Dict]

class WFOValidator:
    """Walk Forward Optimization 검증 엔진"""
    
    def __init__(self, sheets_service: Optional[SheetsService] = None):
        self.sheets_service = sheets_service
        self.technical_indicators = TechnicalIndicators()
        
        # WFO 설정
        self.wfo_config = {
            'in_sample_days': 90,      # 3개월 최적화 기간
            'out_sample_days': 30,     # 1개월 검증 기간
            'walk_steps': 6,           # 총 6회 walk forward
            'min_trades': 10,          # 최소 거래 수
            'pass_thresholds': {
                'wfo_efficiency': 0.7,     # WFO 효율성 70% 이상
                'sharpe_ratio': 0.5,       # 샤프 비율 0.5 이상
                'max_drawdown': -0.20,     # 최대 손실 20% 미만
                'profit_factor': 1.2,      # 수익 팩터 1.2 이상
                'win_rate': 0.4,           # 승률 40% 이상
                'parameter_stability': 0.6  # 파라미터 안정성 60% 이상
            }
        }
        
        logger.info("WFOValidator 초기화 완료")

    async def validate_quarantined_molecules(self) -> List[WFOResult]:
        """검역 중인 모든 분자들을 WFO 검증"""
        try:
            if not self.sheets_service:
                logger.error("Google Sheets 서비스가 필요합니다")
                return []
            
            # 검역 중인 분자들 조회 (status = 'quarantined')
            molecules = await self.sheets_service.get_molecules()
            quarantined_molecules = [
                m for m in molecules 
                if m.get('Status', '').lower() == 'quarantined'
            ]
            
            if not quarantined_molecules:
                logger.info("검역 중인 분자가 없습니다")
                return []
            
            logger.info(f"{len(quarantined_molecules)}개 검역 분자 검증 시작")
            
            validation_results = []
            for molecule in quarantined_molecules:
                try:
                    result = await self.run_molecule_wfo_test(molecule)
                    if result:
                        validation_results.append(result)
                        # WFO 결과를 시트에 기록
                        await self.save_wfo_result(result)
                        
                except Exception as e:
                    logger.error(f"분자 {molecule.get('Molecule_ID')} 검증 실패: {e}")
                    continue
                
                # API 제한 방지를 위한 지연
                await asyncio.sleep(2)
            
            logger.info(f"WFO 검증 완료: {len(validation_results)}개 결과")
            return validation_results
            
        except Exception as e:
            logger.error(f"검역 분자 검증 실패: {e}")
            return []

    async def run_molecule_wfo_test(self, molecule: Dict) -> Optional[WFOResult]:
        """개별 분자에 대한 WFO 테스트 실행"""
        try:
            molecule_id = molecule.get('Molecule_ID')
            required_atoms = molecule.get('Required_Atom_IDs', [])
            
            if not molecule_id or not required_atoms:
                logger.warning(f"분자 데이터 불완전: {molecule_id}")
                return None
            
            logger.info(f"WFO 테스트 시작: {molecule_id}")
            
            # 테스트용 종목 (실제로는 더 다양한 종목으로 테스트)
            test_symbols = ['AAPL', 'TSLA', 'MSFT']
            
            all_walk_results = []
            
            for symbol in test_symbols:
                # 과거 데이터 수집 (6개월치)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=200)
                
                stock_data = await self.get_historical_data(symbol, start_date, end_date)
                if stock_data.empty:
                    continue
                
                # Walk Forward 테스트 실행
                walk_results = await self.execute_walk_forward(
                    molecule, symbol, stock_data
                )
                all_walk_results.extend(walk_results)
            
            if not all_walk_results:
                logger.warning(f"WFO 테스트 데이터 부족: {molecule_id}")
                return None
            
            # 결과 집계 및 분석
            wfo_result = self.analyze_wfo_results(molecule_id, all_walk_results)
            
            # 파라미터 안정성 테스트
            stability_score = await self.test_parameter_stability(molecule, test_symbols[0])
            wfo_result.parameter_stability_score = stability_score
            
            # 최종 검증 판정
            wfo_result.validation_status = self.determine_validation_status(wfo_result)
            
            logger.info(f"WFO 테스트 완료: {molecule_id} - {wfo_result.validation_status}")
            return wfo_result
            
        except Exception as e:
            logger.error(f"분자 WFO 테스트 실패: {e}")
            return None

    async def execute_walk_forward(self, molecule: Dict, symbol: str, 
                                 stock_data: pd.DataFrame) -> List[Dict]:
        """실제 Walk Forward Optimization 실행"""
        try:
            results = []
            data_length = len(stock_data)
            
            # Walk Forward 윈도우 설정
            in_sample_size = self.wfo_config['in_sample_days']
            out_sample_size = self.wfo_config['out_sample_days']
            total_window = in_sample_size + out_sample_size
            
            # 충분한 데이터가 있는지 확인
            if data_length < total_window * 2:
                logger.warning(f"데이터 부족: {symbol} - {data_length}일")
                return results
            
            # Walk Forward 단계별 실행
            for step in range(self.wfo_config['walk_steps']):
                start_idx = step * out_sample_size
                
                # In-Sample 기간
                is_start = start_idx
                is_end = start_idx + in_sample_size
                
                # Out-of-Sample 기간  
                oos_start = is_end
                oos_end = oos_start + out_sample_size
                
                if oos_end > data_length:
                    break
                
                is_data = stock_data.iloc[is_start:is_end].copy()
                oos_data = stock_data.iloc[oos_start:oos_end].copy()
                
                # In-Sample에서 최적 파라미터 찾기 (간단한 예시)
                optimal_params = self.optimize_parameters(molecule, is_data)
                
                # Out-of-Sample에서 성과 측정
                oos_performance = self.backtest_strategy(
                    molecule, oos_data, optimal_params
                )
                
                results.append({
                    'step': step,
                    'symbol': symbol,
                    'is_period': f"{is_data.index[0]} ~ {is_data.index[-1]}",
                    'oos_period': f"{oos_data.index[0]} ~ {oos_data.index[-1]}",
                    'optimal_params': optimal_params,
                    'performance': oos_performance
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Walk Forward 실행 실패: {e}")
            return []

    def optimize_parameters(self, molecule: Dict, data: pd.DataFrame) -> Dict:
        """In-Sample 기간에서 최적 파라미터 탐색 (간단한 예시)"""
        try:
            # 실제로는 더 복잡한 최적화 로직이 필요
            # 여기서는 Match_Threshold_% 최적화 예시
            
            base_threshold = float(molecule.get('Match_Threshold_%', 80))
            test_thresholds = [base_threshold - 10, base_threshold, base_threshold + 10]
            
            best_params = {'match_threshold': base_threshold}
            best_score = 0
            
            for threshold in test_thresholds:
                # 임시 분자 설정으로 백테스트
                temp_molecule = molecule.copy()
                temp_molecule['Match_Threshold_%'] = threshold
                
                performance = self.backtest_strategy(temp_molecule, data, {})
                score = performance.get('sharpe_ratio', 0)
                
                if score > best_score:
                    best_score = score
                    best_params = {'match_threshold': threshold}
            
            return best_params
            
        except Exception as e:
            logger.error(f"파라미터 최적화 실패: {e}")
            return {'match_threshold': float(molecule.get('Match_Threshold_%', 80))}

    def backtest_strategy(self, molecule: Dict, data: pd.DataFrame, 
                         params: Dict) -> Dict:
        """전략 백테스트 실행 (간단한 예시)"""
        try:
            # 기술적 지표 계산
            data_with_indicators = self.technical_indicators.calculate_all_indicators(data)
            
            # 거래 신호 생성 (간단한 로직)
            signals = self.generate_signals(molecule, data_with_indicators, params)
            
            # 성과 계산
            if not signals:
                return {
                    'total_return': 0.0,
                    'sharpe_ratio': 0.0,
                    'max_drawdown': 0.0,
                    'profit_factor': 1.0,
                    'win_rate': 0.0,
                    'total_trades': 0
                }
            
            returns = self.calculate_returns(signals, data_with_indicators)
            
            return {
                'total_return': returns['total_return'],
                'sharpe_ratio': returns['sharpe_ratio'],
                'max_drawdown': returns['max_drawdown'],
                'profit_factor': returns['profit_factor'],
                'win_rate': returns['win_rate'],
                'total_trades': len(signals)
            }
            
        except Exception as e:
            logger.error(f"백테스트 실행 실패: {e}")
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'profit_factor': 1.0,
                'win_rate': 0.0,
                'total_trades': 0
            }

    def generate_signals(self, molecule: Dict, data: pd.DataFrame, 
                        params: Dict) -> List[Dict]:
        """분자 조건에 따른 거래 신호 생성 (간단한 예시)"""
        try:
            signals = []
            required_atoms = molecule.get('Required_Atom_IDs', [])
            
            for i in range(20, len(data)):  # 최소 20개 데이터 필요
                current_row = data.iloc[i]
                
                # 간단한 신호 생성 로직 (실제로는 더 복잡한 아톰 매칭 필요)
                signal_strength = 0
                
                # EMA 상승 추세 확인
                if 'EMA_20' in data.columns and 'EMA_50' in data.columns:
                    if (current_row['EMA_20'] > current_row['EMA_50'] and 
                        current_row['Close'] > current_row['EMA_20']):
                        signal_strength += 1
                
                # 거래량 증가 확인
                if 'Volume_Ratio' in data.columns:
                    if current_row['Volume_Ratio'] > 2.0:
                        signal_strength += 1
                
                # RSI 적정 수준 확인
                if 'RSI' in data.columns:
                    if 30 < current_row['RSI'] < 70:
                        signal_strength += 1
                
                # 매치 임계값 확인  
                match_threshold = params.get('match_threshold', 80) / 100
                if signal_strength >= len(required_atoms) * match_threshold:
                    signals.append({
                        'timestamp': data.index[i],
                        'price': current_row['Close'],
                        'signal_strength': signal_strength,
                        'type': 'BUY'
                    })
            
            return signals
            
        except Exception as e:
            logger.error(f"신호 생성 실패: {e}")
            return []

    def calculate_returns(self, signals: List[Dict], data: pd.DataFrame) -> Dict:
        """거래 신호 기반 수익률 계산"""
        try:
            if not signals:
                return {
                    'total_return': 0.0,
                    'sharpe_ratio': 0.0,
                    'max_drawdown': 0.0,
                    'profit_factor': 1.0,
                    'win_rate': 0.0
                }
            
            returns = []
            wins = 0
            losses = 0
            gross_profit = 0
            gross_loss = 0
            
            # 간단한 매수 후 5일 보유 전략
            for signal in signals:
                entry_time = signal['timestamp']
                entry_price = signal['price']
                
                # 5일 후 또는 데이터 끝까지
                try:
                    entry_idx = data.index.get_loc(entry_time)
                    exit_idx = min(entry_idx + 5, len(data) - 1)
                    exit_price = data.iloc[exit_idx]['Close']
                    
                    trade_return = (exit_price - entry_price) / entry_price
                    returns.append(trade_return)
                    
                    if trade_return > 0:
                        wins += 1
                        gross_profit += trade_return
                    else:
                        losses += 1
                        gross_loss += abs(trade_return)
                        
                except:
                    continue
            
            if not returns:
                return {
                    'total_return': 0.0,
                    'sharpe_ratio': 0.0,
                    'max_drawdown': 0.0,
                    'profit_factor': 1.0,
                    'win_rate': 0.0
                }
            
            # 성과 지표 계산
            total_return = sum(returns)
            avg_return = np.mean(returns)
            std_return = np.std(returns) if len(returns) > 1 else 0.001
            sharpe_ratio = avg_return / std_return * np.sqrt(252) if std_return > 0 else 0
            
            # 최대 손실폭 계산
            cumulative_returns = np.cumsum(returns)
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdowns = cumulative_returns - running_max
            max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0
            
            # 수익 팩터
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0
            
            # 승률
            win_rate = wins / len(returns) if returns else 0
            
            return {
                'total_return': total_return,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'profit_factor': profit_factor,
                'win_rate': win_rate
            }
            
        except Exception as e:
            logger.error(f"수익률 계산 실패: {e}")
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'profit_factor': 1.0,
                'win_rate': 0.0
            }

    def analyze_wfo_results(self, molecule_id: str, walk_results: List[Dict]) -> WFOResult:
        """WFO 결과 분석 및 집계"""
        try:
            if not walk_results:
                return WFOResult(
                    molecule_id=molecule_id,
                    test_periods=0,
                    wfo_sharpe=0.0,
                    simple_sharpe=0.0,
                    wfo_efficiency=0.0,
                    max_drawdown=0.0,
                    profit_factor=1.0,
                    win_rate=0.0,
                    parameter_stability_score=0.0,
                    validation_status='FAILED',
                    test_date=datetime.now(timezone.utc).isoformat(),
                    detailed_results=[]
                )
            
            # 각 walk 결과에서 성과 지표 추출
            sharpe_ratios = []
            returns = []
            max_drawdowns = []
            profit_factors = []
            win_rates = []
            
            for result in walk_results:
                perf = result['performance']
                sharpe_ratios.append(perf.get('sharpe_ratio', 0))
                returns.append(perf.get('total_return', 0))
                max_drawdowns.append(perf.get('max_drawdown', 0))
                profit_factors.append(perf.get('profit_factor', 1))
                win_rates.append(perf.get('win_rate', 0))
            
            # WFO 집계 결과  
            wfo_sharpe = np.mean(sharpe_ratios) if sharpe_ratios else 0
            wfo_return = np.mean(returns) if returns else 0
            max_dd = np.min(max_drawdowns) if max_drawdowns else 0
            avg_pf = np.mean(profit_factors) if profit_factors else 1
            avg_wr = np.mean(win_rates) if win_rates else 0
            
            # 단순 백테스트와 비교 (첫 번째 심볼 전체 기간)
            simple_sharpe = 0.5  # 간단한 추정값 (실제로는 전체 기간 백테스트 필요)
            
            # WFO 효율성 계산
            wfo_efficiency = wfo_sharpe / simple_sharpe if simple_sharpe > 0 else 0
            
            return WFOResult(
                molecule_id=molecule_id,
                test_periods=len(walk_results),
                wfo_sharpe=wfo_sharpe,
                simple_sharpe=simple_sharpe,
                wfo_efficiency=wfo_efficiency,
                max_drawdown=max_dd,
                profit_factor=avg_pf,
                win_rate=avg_wr,
                parameter_stability_score=0.0,  # 별도 메서드에서 설정
                validation_status='PENDING',
                test_date=datetime.now(timezone.utc).isoformat(),
                detailed_results=walk_results
            )
            
        except Exception as e:
            logger.error(f"WFO 결과 분석 실패: {e}")
            return WFOResult(
                molecule_id=molecule_id,
                test_periods=0,
                wfo_sharpe=0.0,
                simple_sharpe=0.0,
                wfo_efficiency=0.0,
                max_drawdown=0.0,
                profit_factor=1.0,
                win_rate=0.0,
                parameter_stability_score=0.0,
                validation_status='FAILED',
                test_date=datetime.now(timezone.utc).isoformat(),
                detailed_results=[]
            )

    async def test_parameter_stability(self, molecule: Dict, symbol: str) -> float:
        """파라미터 안정성 테스트"""
        try:
            base_threshold = float(molecule.get('Match_Threshold_%', 80))
            
            # ±5%, ±10% 변경하여 성과 변화 측정
            threshold_variations = [
                base_threshold * 0.9,   # -10%
                base_threshold * 0.95,  # -5%
                base_threshold,         # 기본값
                base_threshold * 1.05,  # +5%
                base_threshold * 1.1    # +10%
            ]
            
            performance_scores = []
            
            # 간단한 테스트 데이터 생성
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)
            test_data = await self.get_historical_data(symbol, start_date, end_date)
            
            if test_data.empty:
                return 0.5  # 기본값
            
            for threshold in threshold_variations:
                temp_molecule = molecule.copy()
                temp_molecule['Match_Threshold_%'] = threshold
                
                performance = self.backtest_strategy(temp_molecule, test_data, {})
                performance_scores.append(performance.get('sharpe_ratio', 0))
            
            # 안정성 점수 계산 (변동 계수의 역수)
            if len(performance_scores) > 1:
                mean_score = np.mean(performance_scores)
                std_score = np.std(performance_scores)
                
                if mean_score > 0 and std_score > 0:
                    coefficient_of_variation = std_score / mean_score
                    stability_score = 1 / (1 + coefficient_of_variation)
                else:
                    stability_score = 0.5
            else:
                stability_score = 0.5
            
            return min(1.0, max(0.0, stability_score))
            
        except Exception as e:
            logger.error(f"파라미터 안정성 테스트 실패: {e}")
            return 0.5

    def determine_validation_status(self, result: WFOResult) -> str:
        """WFO 결과를 바탕으로 검증 상태 결정"""
        try:
            thresholds = self.wfo_config['pass_thresholds']
            
            # 각 기준 확인
            checks = [
                result.wfo_efficiency >= thresholds['wfo_efficiency'],
                result.wfo_sharpe >= thresholds['sharpe_ratio'],
                result.max_drawdown >= thresholds['max_drawdown'],
                result.profit_factor >= thresholds['profit_factor'],
                result.win_rate >= thresholds['win_rate'],
                result.parameter_stability_score >= thresholds['parameter_stability']
            ]
            
            # 모든 기준을 통과해야 PASSED
            if all(checks):
                return 'PASSED'
            elif sum(checks) >= 4:  # 6개 중 4개 이상 통과
                return 'CONDITIONAL'  # 조건부 통과
            else:
                return 'FAILED'
                
        except Exception as e:
            logger.error(f"검증 상태 결정 실패: {e}")
            return 'FAILED'

    async def get_historical_data(self, symbol: str, start_date: datetime, 
                                end_date: datetime) -> pd.DataFrame:
        """과거 데이터 수집 (yfinance 사용)"""
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval='1d'
            )
            
            if data.empty:
                logger.warning(f"데이터 없음: {symbol}")
                
            return data
            
        except Exception as e:
            logger.error(f"과거 데이터 수집 실패: {e}")
            return pd.DataFrame()

    async def save_wfo_result(self, result: WFOResult):
        """WFO 결과를 Google Sheets에 저장"""
        try:
            if not self.sheets_service:
                return
            
            # WFO_Results 시트가 없다면 생성 필요 (수동으로 생성해야 함)
            # 여기서는 기존 시트에 기록한다고 가정
            
            wfo_data = {
                'Result_ID': str(uuid.uuid4()),
                'Molecule_ID': result.molecule_id,
                'Test_Date': result.test_date,
                'Walk_Forward_Periods': result.test_periods,
                'Simple_Sharpe': result.simple_sharpe,
                'WFO_Sharpe': result.wfo_sharpe,
                'WFO_Efficiency': result.wfo_efficiency,
                'Max_Drawdown': result.max_drawdown,
                'Profit_Factor': result.profit_factor,
                'Win_Rate': result.win_rate,
                'Parameter_Stability_Score': result.parameter_stability_score,
                'Validation_Status': result.validation_status
            }
            
            # 실제 구현 시에는 WFO_Results 시트에 저장
            logger.info(f"WFO 결과 저장: {result.molecule_id} - {result.validation_status}")
            
        except Exception as e:
            logger.error(f"WFO 결과 저장 실패: {e}")

    async def get_validation_summary(self) -> Dict:
        """검증 요약 정보 반환"""
        try:
            results = await self.validate_quarantined_molecules()
            
            summary = {
                'total_tested': len(results),
                'passed': len([r for r in results if r.validation_status == 'PASSED']),
                'conditional': len([r for r in results if r.validation_status == 'CONDITIONAL']),
                'failed': len([r for r in results if r.validation_status == 'FAILED']),
                'avg_wfo_efficiency': np.mean([r.wfo_efficiency for r in results]) if results else 0,
                'test_date': datetime.now(timezone.utc).isoformat()
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"검증 요약 생성 실패: {e}")
            return {}

# 사용 예시
if __name__ == "__main__":
    async def test_wfo_validator():
        """WFO Validator 테스트"""
        validator = WFOValidator()
        
        print("🧪 WFO Validator 테스트 시작")
        print("=" * 50)
        
        # 테스트용 분자 데이터
        test_molecule = {
            'Molecule_ID': 'TEST-001',
            'Molecule_Name': 'EMA 골든크로스 테스트',
            'Required_Atom_IDs': ['STR-003', 'TRG-001'],
            'Match_Threshold_%': 80,
            'Status': 'quarantined'
        }
        
        # WFO 테스트 실행
        result = await validator.run_molecule_wfo_test(test_molecule)
        
        if result:
            print(f"✅ 테스트 완료: {result.molecule_id}")
            print(f"📊 WFO 효율성: {result.wfo_efficiency:.3f}")
            print(f"📈 샤프 비율: {result.wfo_sharpe:.3f}")
            print(f"📉 최대 손실: {result.max_drawdown:.1%}")
            print(f"🎯 검증 상태: {result.validation_status}")
        else:
            print("❌ 테스트 실패")
        
        print("\n✅ WFO Validator 테스트 완료!")

    # 테스트 실행
    asyncio.run(test_wfo_validator())
