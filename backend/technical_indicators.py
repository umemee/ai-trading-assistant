"""
technical_indicators.py - 기술적 지표 계산 및 아톰 탐지 엔진
AI 트레이딩 어시스턴트 V5.1의 핵심 기술적 분석 모듈

주요 기능:
- 기본 기술적 지표 계산 (EMA, RSI, MACD, 볼린저밴드 등)
- VWAP 및 슈퍼트렌드 계산
- 아톰 탐지를 위한 특화 함수들
- 다중 시간대 분석 지원 (1분, 5분, 1시간)
- 컨버전스(겹침) 탐지 및 패턴 인식
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union
import warnings

# 경고 메시지 숨기기
warnings.filterwarnings('ignore')

# 로깅 설정
logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """기술적 지표 계산 및 아톰 탐지 클래스"""
    
    def __init__(self):
        """기술적 지표 계산기 초기화"""
        self.convergence_threshold = 0.01  # 1% 이내 컨버전스 기준
        self.volume_spike_threshold = 5.0  # 거래량 폭발 기준 (5배)
        self.support_resistance_threshold = 0.01  # 지지/저항 기준 (1%)
        
        # 캐시된 지표들 (성능 최적화용)
        self._cached_indicators = {}
        
        logger.info("TechnicalIndicators 모듈 초기화 완료")
    
    # ================== 기본 기술적 지표 계산 ==================
    
    def calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """
        지수이동평균(EMA) 계산
        
        Args:
            data: 가격 데이터 (보통 종가)
            period: 계산 기간
            
        Returns:
            EMA 값들의 시리즈
        """
        try:
            if len(data) < period:
                logger.warning(f"데이터 길이({len(data)})가 EMA 기간({period})보다 짧습니다")
                return pd.Series(index=data.index, dtype=float)
            
            ema = data.ewm(span=period, adjust=False).mean()
            return ema
            
        except Exception as e:
            logger.error(f"EMA 계산 오류: {e}")
            return pd.Series(index=data.index, dtype=float)
    
    def calculate_sma(self, data: pd.Series, period: int) -> pd.Series:
        """
        단순이동평균(SMA) 계산
        
        Args:
            data: 가격 데이터
            period: 계산 기간
            
        Returns:
            SMA 값들의 시리즈
        """
        try:
            if len(data) < period:
                return pd.Series(index=data.index, dtype=float)
            
            sma = data.rolling(window=period).mean()
            return sma
            
        except Exception as e:
            logger.error(f"SMA 계산 오류: {e}")
            return pd.Series(index=data.index, dtype=float)
    
    def calculate_rsi(self, data: pd.Series, period: int = 14) -> pd.Series:
        """
        상대강도지수(RSI) 계산
        
        Args:
            data: 가격 데이터
            period: 계산 기간 (기본 14)
            
        Returns:
            RSI 값들의 시리즈 (0-100)
        """
        try:
            if len(data) < period + 1:
                return pd.Series(index=data.index, dtype=float)
            
            delta = data.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.error(f"RSI 계산 오류: {e}")
            return pd.Series(index=data.index, dtype=float)
    
    def calculate_macd(self, data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """
        MACD 계산
        
        Args:
            data: 가격 데이터
            fast: 빠른 EMA 기간 (기본 12)
            slow: 느린 EMA 기간 (기본 26)
            signal: 신호선 EMA 기간 (기본 9)
            
        Returns:
            Dict with 'macd', 'signal', 'histogram'
        """
        try:
            if len(data) < slow + signal:
                empty_series = pd.Series(index=data.index, dtype=float)
                return {
                    'macd': empty_series,
                    'signal': empty_series,
                    'histogram': empty_series
                }
            
            ema_fast = self.calculate_ema(data, fast)
            ema_slow = self.calculate_ema(data, slow)
            
            macd_line = ema_fast - ema_slow
            signal_line = self.calculate_ema(macd_line, signal)
            histogram = macd_line - signal_line
            
            return {
                'macd': macd_line,
                'signal': signal_line,
                'histogram': histogram
            }
            
        except Exception as e:
            logger.error(f"MACD 계산 오류: {e}")
            empty_series = pd.Series(index=data.index, dtype=float)
            return {
                'macd': empty_series,
                'signal': empty_series,
                'histogram': empty_series
            }
    
    def calculate_bollinger_bands(self, data: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
        """
        볼린저 밴드 계산
        
        Args:
            data: 가격 데이터
            period: 이동평균 기간 (기본 20)
            std_dev: 표준편차 배수 (기본 2.0)
            
        Returns:
            Dict with 'upper', 'middle', 'lower'
        """
        try:
            if len(data) < period:
                empty_series = pd.Series(index=data.index, dtype=float)
                return {
                    'upper': empty_series,
                    'middle': empty_series,
                    'lower': empty_series
                }
            
            sma = self.calculate_sma(data, period)
            std = data.rolling(window=period).std()
            
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            
            return {
                'upper': upper_band,
                'middle': sma,
                'lower': lower_band
            }
            
        except Exception as e:
            logger.error(f"볼린저 밴드 계산 오류: {e}")
            empty_series = pd.Series(index=data.index, dtype=float)
            return {
                'upper': empty_series,
                'middle': empty_series,
                'lower': empty_series
            }
    
    def calculate_vwap(self, ohlcv_data: pd.DataFrame) -> pd.Series:
        """
        거래량 가중 평균 가격(VWAP) 계산
        
        Args:
            ohlcv_data: OHLCV 데이터프레임 (High, Low, Close, Volume 컬럼 필요)
            
        Returns:
            VWAP 값들의 시리즈
        """
        try:
            required_columns = ['High', 'Low', 'Close', 'Volume']
            for col in required_columns:
                if col not in ohlcv_data.columns:
                    logger.error(f"VWAP 계산에 필요한 '{col}' 컬럼이 없습니다")
                    return pd.Series(index=ohlcv_data.index, dtype=float)
            
            # 전형적인 가격 계산 (High + Low + Close) / 3
            typical_price = (ohlcv_data['High'] + ohlcv_data['Low'] + ohlcv_data['Close']) / 3
            
            # 거래량 * 전형적인 가격
            pv = typical_price * ohlcv_data['Volume']
            
            # 누적 합계 계산
            cumulative_pv = pv.cumsum()
            cumulative_volume = ohlcv_data['Volume'].cumsum()
            
            # VWAP = 누적(PV) / 누적(Volume)
            vwap = cumulative_pv / cumulative_volume
            
            return vwap
            
        except Exception as e:
            logger.error(f"VWAP 계산 오류: {e}")
            return pd.Series(index=ohlcv_data.index, dtype=float)
    
    def calculate_supertrend(self, ohlcv_data: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Dict[str, pd.Series]:
        """
        슈퍼트렌드 지표 계산
        
        Args:
            ohlcv_data: OHLCV 데이터프레임
            period: ATR 계산 기간 (기본 10)
            multiplier: ATR 배수 (기본 3.0)
            
        Returns:
            Dict with 'supertrend', 'trend' (1: 상승, -1: 하락)
        """
        try:
            if len(ohlcv_data) < period:
                empty_series = pd.Series(index=ohlcv_data.index, dtype=float)
                return {
                    'supertrend': empty_series,
                    'trend': empty_series
                }
            
            # ATR (Average True Range) 계산
            high = ohlcv_data['High']
            low = ohlcv_data['Low']
            close = ohlcv_data['Close']
            
            tr1 = high - low
            tr2 = np.abs(high - close.shift(1))
            tr3 = np.abs(low - close.shift(1))
            
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = true_range.rolling(window=period).mean()
            
            # 기본 상한선과 하한선 계산
            hl_avg = (high + low) / 2
            upper_basic = hl_avg + (multiplier * atr)
            lower_basic = hl_avg - (multiplier * atr)
            
            # 최종 상한선과 하한선 계산
            upper_final = pd.Series(index=ohlcv_data.index, dtype=float)
            lower_final = pd.Series(index=ohlcv_data.index, dtype=float)
            
            for i in range(len(ohlcv_data)):
                if i == 0:
                    upper_final.iloc[i] = upper_basic.iloc[i]
                    lower_final.iloc[i] = lower_basic.iloc[i]
                else:
                    # 상한선 업데이트
                    if upper_basic.iloc[i] < upper_final.iloc[i-1] or close.iloc[i-1] > upper_final.iloc[i-1]:
                        upper_final.iloc[i] = upper_basic.iloc[i]
                    else:
                        upper_final.iloc[i] = upper_final.iloc[i-1]
                    
                    # 하한선 업데이트
                    if lower_basic.iloc[i] > lower_final.iloc[i-1] or close.iloc[i-1] < lower_final.iloc[i-1]:
                        lower_final.iloc[i] = lower_basic.iloc[i]
                    else:
                        lower_final.iloc[i] = lower_final.iloc[i-1]
            
            # 슈퍼트렌드와 추세 방향 계산
            supertrend = pd.Series(index=ohlcv_data.index, dtype=float)
            trend = pd.Series(index=ohlcv_data.index, dtype=int)
            
            for i in range(len(ohlcv_data)):
                if i == 0:
                    supertrend.iloc[i] = upper_final.iloc[i]
                    trend.iloc[i] = -1
                else:
                    if trend.iloc[i-1] == -1 and close.iloc[i] > upper_final.iloc[i]:
                        trend.iloc[i] = 1
                        supertrend.iloc[i] = lower_final.iloc[i]
                    elif trend.iloc[i-1] == 1 and close.iloc[i] < lower_final.iloc[i]:
                        trend.iloc[i] = -1
                        supertrend.iloc[i] = upper_final.iloc[i]
                    else:
                        trend.iloc[i] = trend.iloc[i-1]
                        if trend.iloc[i] == 1:
                            supertrend.iloc[i] = lower_final.iloc[i]
                        else:
                            supertrend.iloc[i] = upper_final.iloc[i]
            
            return {
                'supertrend': supertrend,
                'trend': trend
            }
            
        except Exception as e:
            logger.error(f"슈퍼트렌드 계산 오류: {e}")
            empty_series = pd.Series(index=ohlcv_data.index, dtype=float)
            return {
                'supertrend': empty_series,
                'trend': empty_series
            }
    
    # ================== 아톰 탐지 특화 함수들 ==================
    
    def calculate_all_indicators(self, ohlcv_data: pd.DataFrame, timeframe: str = '1m') -> pd.DataFrame:
        """
        모든 기술적 지표를 한 번에 계산
        
        Args:
            ohlcv_data: OHLCV 데이터프레임
            timeframe: 시간대 ('1m', '5m', '1h')
            
        Returns:
            모든 지표가 추가된 데이터프레임
        """
        try:
            if ohlcv_data.empty:
                logger.warning("빈 데이터프레임이 입력되었습니다")
                return ohlcv_data.copy()
            
            df = ohlcv_data.copy()
            
            # EMA 계산 (여러 기간)
            ema_periods = [5, 20, 50, 100, 200]
            for period in ema_periods:
                df[f'EMA_{period}'] = self.calculate_ema(df['Close'], period)
            
            # SMA 계산
            df['SMA_20'] = self.calculate_sma(df['Close'], 20)
            df['SMA_50'] = self.calculate_sma(df['Close'], 50)
            
            # RSI 계산
            df['RSI'] = self.calculate_rsi(df['Close'])
            
            # MACD 계산
            macd_data = self.calculate_macd(df['Close'])
            df['MACD'] = macd_data['macd']
            df['MACD_Signal'] = macd_data['signal']
            df['MACD_Histogram'] = macd_data['histogram']
            
            # 볼린저 밴드 계산
            bb_data = self.calculate_bollinger_bands(df['Close'])
            df['BB_Upper'] = bb_data['upper']
            df['BB_Middle'] = bb_data['middle']
            df['BB_Lower'] = bb_data['lower']
            
            # VWAP 계산
            df['VWAP'] = self.calculate_vwap(df)
            
            # 슈퍼트렌드 계산
            st_data = self.calculate_supertrend(df)
            df['SuperTrend'] = st_data['supertrend']
            df['ST_Trend'] = st_data['trend']
            
            # 거래량 이동평균
            df['Volume_MA'] = self.calculate_sma(df['Volume'], 20)
            
            # 상대 거래량 (Volume Ratio)
            df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
            
            logger.info(f"{timeframe} 시간대 모든 지표 계산 완료")
            return df
            
        except Exception as e:
            logger.error(f"전체 지표 계산 오류: {e}")
            return ohlcv_data.copy()
    
    def detect_ema_support(self, df: pd.DataFrame, ema_period: int, current_idx: int = -1) -> bool:
        """
        EMA 지지 감지 (STR-003, STR-004, STR-005 등)
        
        Args:
            df: 지표가 계산된 데이터프레임
            ema_period: EMA 기간 (20, 50, 200 등)
            current_idx: 현재 검사할 인덱스 (-1이면 최신)
            
        Returns:
            EMA 지지 여부
        """
        try:
            if len(df) < 2:
                return False
            
            ema_col = f'EMA_{ema_period}'
            if ema_col not in df.columns:
                return False
            
            idx = current_idx if current_idx >= 0 else -1
            
            # 현재 캔들의 저가가 EMA에 1% 이내로 근접하며 지지받는지 확인
            current_low = df['Low'].iloc[idx]
            current_ema = df[ema_col].iloc[idx]
            current_close = df['Close'].iloc[idx]
            
            if pd.isna(current_ema) or current_ema == 0:
                return False
            
            # 1% 이내 근접도 체크
            proximity = abs(current_low - current_ema) / current_ema
            is_near_ema = proximity <= self.support_resistance_threshold
            
            # 지지 조건: 저가가 EMA 근처에 있고, 종가가 EMA 위에 있음
            is_supported = current_close > current_ema and is_near_ema
            
            return is_supported
            
        except Exception as e:
            logger.error(f"EMA 지지 감지 오류: {e}")
            return False
    
    def detect_vwap_support(self, df: pd.DataFrame, current_idx: int = -1) -> bool:
        """
        VWAP 지지 감지 (STR-007)
        
        Args:
            df: 지표가 계산된 데이터프레임
            current_idx: 현재 검사할 인덱스
            
        Returns:
            VWAP 지지 여부
        """
        try:
            if 'VWAP' not in df.columns or len(df) < 2:
                return False
            
            idx = current_idx if current_idx >= 0 else -1
            
            current_low = df['Low'].iloc[idx]
            current_vwap = df['VWAP'].iloc[idx]
            current_close = df['Close'].iloc[idx]
            
            if pd.isna(current_vwap) or current_vwap == 0:
                return False
            
            # VWAP 근처에서 지지받는지 확인
            proximity = abs(current_low - current_vwap) / current_vwap
            is_near_vwap = proximity <= self.support_resistance_threshold
            
            is_supported = current_close > current_vwap and is_near_vwap
            
            return is_supported
            
        except Exception as e:
            logger.error(f"VWAP 지지 감지 오류: {e}")
            return False
    
    def detect_supertrend_support(self, df: pd.DataFrame, current_idx: int = -1) -> bool:
        """
        슈퍼트렌드 지지 감지 (STR-008, STR-009)
        
        Args:
            df: 지표가 계산된 데이터프레임
            current_idx: 현재 검사할 인덱스
            
        Returns:
            슈퍼트렌드 지지 여부
        """
        try:
            required_cols = ['SuperTrend', 'ST_Trend']
            for col in required_cols:
                if col not in df.columns:
                    return False
            
            if len(df) < 2:
                return False
            
            idx = current_idx if current_idx >= 0 else -1
            
            current_low = df['Low'].iloc[idx]
            current_supertrend = df['SuperTrend'].iloc[idx]
            current_trend = df['ST_Trend'].iloc[idx]
            current_close = df['Close'].iloc[idx]
            
            if pd.isna(current_supertrend) or current_supertrend == 0:
                return False
            
            # 상승 추세에서 슈퍼트렌드 지지선 근처에서 지지받는지 확인
            if current_trend == 1:  # 상승 추세
                proximity = abs(current_low - current_supertrend) / current_supertrend
                is_near_st = proximity <= self.support_resistance_threshold
                is_supported = current_close > current_supertrend and is_near_st
                return is_supported
            
            return False
            
        except Exception as e:
            logger.error(f"슈퍼트렌드 지지 감지 오류: {e}")
            return False
    
    def detect_volume_explosion(self, df: pd.DataFrame, lookback_period: int = 20, current_idx: int = -1) -> Dict[str, Union[bool, float]]:
        """
        거래량 폭발 감지 (TRG-003)
        
        Args:
            df: 데이터프레임
            lookback_period: 평균 계산 기간
            current_idx: 현재 검사할 인덱스
            
        Returns:
            Dict with 'triggered', 'volume_ratio', 'grade'
        """
        try:
            if len(df) < lookback_period + 1:
                return {'triggered': False, 'volume_ratio': 0.0, 'grade': 'C'}
            
            idx = current_idx if current_idx >= 0 else -1
            
            current_volume = df['Volume'].iloc[idx]
            
            # 최근 N일 평균 거래량 계산 (현재 제외)
            if idx == -1:
                avg_volume = df['Volume'].iloc[-lookback_period-1:-1].mean()
            else:
                start_idx = max(0, idx - lookback_period)
                avg_volume = df['Volume'].iloc[start_idx:idx].mean()
            
            if avg_volume == 0 or pd.isna(avg_volume):
                return {'triggered': False, 'volume_ratio': 0.0, 'grade': 'C'}
            
            volume_ratio = current_volume / avg_volume
            
            # 거래량 폭발 기준 (5배 이상)
            triggered = volume_ratio >= self.volume_spike_threshold
            
            # 등급 산정
            if volume_ratio >= 10.0:
                grade = 'A++'
            elif volume_ratio >= 7.0:
                grade = 'A+'
            elif volume_ratio >= 5.0:
                grade = 'A'
            elif volume_ratio >= 3.0:
                grade = 'B+'
            elif volume_ratio >= 2.0:
                grade = 'B'
            else:
                grade = 'C'
            
            return {
                'triggered': triggered,
                'volume_ratio': volume_ratio,
                'grade': grade
            }
            
        except Exception as e:
            logger.error(f"거래량 폭발 감지 오류: {e}")
            return {'triggered': False, 'volume_ratio': 0.0, 'grade': 'C'}
    
    def detect_ema_compression(self, df: pd.DataFrame, ema_periods: List[int] = [5, 20], vwap_included: bool = True, current_idx: int = -1) -> bool:
        """
        EMA 응축 감지 (STR-001)
        
        Args:
            df: 지표가 계산된 데이터프레임
            ema_periods: 확인할 EMA 기간들
            vwap_included: VWAP 포함 여부
            current_idx: 현재 검사할 인덱스
            
        Returns:
            EMA 응축 여부 (1% 이내 수렴)
        """
        try:
            idx = current_idx if current_idx >= 0 else -1
            
            values = []
            
            # EMA 값들 수집
            for period in ema_periods:
                ema_col = f'EMA_{period}'
                if ema_col in df.columns:
                    ema_val = df[ema_col].iloc[idx]
                    if not pd.isna(ema_val):
                        values.append(ema_val)
            
            # VWAP 값 추가
            if vwap_included and 'VWAP' in df.columns:
                vwap_val = df['VWAP'].iloc[idx]
                if not pd.isna(vwap_val):
                    values.append(vwap_val)
            
            if len(values) < 2:
                return False
            
            # 모든 값들이 1% 이내로 수렴하는지 확인
            max_val = max(values)
            min_val = min(values)
            
            if max_val == 0:
                return False
            
            compression_ratio = (max_val - min_val) / max_val
            is_compressed = compression_ratio <= self.convergence_threshold
            
            return is_compressed
            
        except Exception as e:
            logger.error(f"EMA 응축 감지 오류: {e}")
            return False
    
    def detect_uptrend_array(self, df: pd.DataFrame, timeframe: str = '1m', current_idx: int = -1) -> bool:
        """
        정배열 감지 (TRG-008)
        
        Args:
            df: 지표가 계산된 데이터프레임
            timeframe: 시간대
            current_idx: 현재 검사할 인덱스
            
        Returns:
            정배열 여부
        """
        try:
            idx = current_idx if current_idx >= 0 else -1
            
            # 시간대별 EMA 기간 설정
            if timeframe == '1m':
                periods = [5, 20, 50]
            elif timeframe == '5m':
                periods = [20, 50, 100]
            else:  # 1h
                periods = [20, 50, 200]
            
            ema_values = []
            for period in periods:
                ema_col = f'EMA_{period}'
                if ema_col in df.columns:
                    ema_val = df[ema_col].iloc[idx]
                    if not pd.isna(ema_val):
                        ema_values.append(ema_val)
            
            if len(ema_values) < 3:
                return False
            
            # 정배열 확인: 단기 > 중기 > 장기
            is_uptrend = ema_values[0] > ema_values[1] > ema_values[2]
            
            return is_uptrend
            
        except Exception as e:
            logger.error(f"정배열 감지 오류: {e}")
            return False
    
    def detect_vwap_golden_cross(self, df: pd.DataFrame, ema_period: int = 20, lookback: int = 5, current_idx: int = -1) -> bool:
        """
        VWAP 골든크로스 감지 (TRG-001)
        
        Args:
            df: 지표가 계산된 데이터프레임
            ema_period: EMA 기간 (기본 20)
            lookback: 골든크로스 확인 기간 (기본 5분)
            current_idx: 현재 검사할 인덱스
            
        Returns:
            VWAP 골든크로스 발생 여부
        """
        try:
            ema_col = f'EMA_{ema_period}'
            required_cols = [ema_col, 'VWAP']
            
            for col in required_cols:
                if col not in df.columns:
                    return False
            
            if len(df) < lookback + 1:
                return False
            
            idx = current_idx if current_idx >= 0 else -1
            
            # 현재와 과거 값들 확인
            current_ema = df[ema_col].iloc[idx]
            current_vwap = df['VWAP'].iloc[idx]
            
            past_ema = df[ema_col].iloc[idx - lookback]
            past_vwap = df['VWAP'].iloc[idx - lookback]
            
            if any(pd.isna(val) for val in [current_ema, current_vwap, past_ema, past_vwap]):
                return False
            
            # 골든크로스 조건: 과거에는 EMA < VWAP, 현재는 EMA > VWAP
            golden_cross = (past_ema <= past_vwap) and (current_ema > current_vwap)
            
            return golden_cross
            
        except Exception as e:
            logger.error(f"VWAP 골든크로스 감지 오류: {e}")
            return False
    
    def detect_supertrend_breakout(self, df: pd.DataFrame, current_idx: int = -1) -> bool:
        """
        슈퍼트렌드 돌파 감지 (TRG-004)
        
        Args:
            df: 지표가 계산된 데이터프레임
            current_idx: 현재 검사할 인덱스
            
        Returns:
            슈퍼트렌드 상향 돌파 여부
        """
        try:
            required_cols = ['SuperTrend', 'ST_Trend', 'Close']
            for col in required_cols:
                if col not in df.columns:
                    return False
            
            if len(df) < 2:
                return False
            
            idx = current_idx if current_idx >= 0 else -1
            
            current_trend = df['ST_Trend'].iloc[idx]
            prev_trend = df['ST_Trend'].iloc[idx - 1]
            current_close = df['Close'].iloc[idx]
            current_st = df['SuperTrend'].iloc[idx]
            
            if any(pd.isna(val) for val in [current_trend, prev_trend, current_close, current_st]):
                return False
            
            # 돌파 조건: 이전에는 하락 추세(-1), 현재는 상승 추세(1)
            breakout = (prev_trend == -1) and (current_trend == 1) and (current_close > current_st)
            
            return breakout
            
        except Exception as e:
            logger.error(f"슈퍼트렌드 돌파 감지 오류: {e}")
            return False
    
    def detect_vwap_reclaim(self, df: pd.DataFrame, lookback: int = 10, current_idx: int = -1) -> bool:
        """
        VWAP 재탈환 감지 (TRG-006)
        
        Args:
            df: 지표가 계산된 데이터프레임
            lookback: 확인할 과거 기간
            current_idx: 현재 검사할 인덱스
            
        Returns:
            VWAP 재탈환 여부
        """
        try:
            if 'VWAP' not in df.columns or len(df) < lookback + 1:
                return False
            
            idx = current_idx if current_idx >= 0 else -1
            
            current_close = df['Close'].iloc[idx]
            current_vwap = df['VWAP'].iloc[idx]
            
            if pd.isna(current_vwap) or pd.isna(current_close):
                return False
            
            # 현재는 VWAP 위에 있어야 함
            if current_close <= current_vwap:
                return False
            
            # 과거 lookback 기간 중에 VWAP 아래로 떨어진 적이 있는지 확인
            was_below_vwap = False
            for i in range(1, min(lookback + 1, len(df))):
                past_close = df['Close'].iloc[idx - i]
                past_vwap = df['VWAP'].iloc[idx - i]
                
                if not pd.isna(past_close) and not pd.isna(past_vwap):
                    if past_close < past_vwap:
                        was_below_vwap = True
                        break
            
            return was_below_vwap
            
        except Exception as e:
            logger.error(f"VWAP 재탈환 감지 오류: {e}")
            return False
    
    def detect_vwap_breakdown(self, df: pd.DataFrame, current_idx: int = -1) -> bool:
        """
        VWAP 붕괴 감지 (TRG-007)
        
        Args:
            df: 지표가 계산된 데이터프레임
            current_idx: 현재 검사할 인덱스
            
        Returns:
            VWAP 하향 이탈 여부
        """
        try:
            if 'VWAP' not in df.columns or len(df) < 2:
                return False
            
            idx = current_idx if current_idx >= 0 else -1
            
            current_close = df['Close'].iloc[idx]
            current_vwap = df['VWAP'].iloc[idx]
            prev_close = df['Close'].iloc[idx - 1]
            prev_vwap = df['VWAP'].iloc[idx - 1]
            
            if any(pd.isna(val) for val in [current_close, current_vwap, prev_close, prev_vwap]):
                return False
            
            # 붕괴 조건: 이전에는 VWAP 위, 현재는 VWAP 아래
            breakdown = (prev_close >= prev_vwap) and (current_close < current_vwap)
            
            return breakdown
            
        except Exception as e:
            logger.error(f"VWAP 붕괴 감지 오류: {e}")
            return False
    
    # ================== 컨버전스(겹침) 탐지 함수들 ==================
    
    def detect_convergence_1m20_5m100(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame, current_time: Optional[datetime] = None) -> bool:
        """
        1분 20EMA와 5분 100EMA 컨버전스 탐지 (DRV-001)
        
        Args:
            df_1m: 1분봉 데이터
            df_5m: 5분봉 데이터
            current_time: 현재 시간 (None이면 최신 데이터 사용)
            
        Returns:
            컨버전스 여부
        """
        try:
            if 'EMA_20' not in df_1m.columns or 'EMA_100' not in df_5m.columns:
                return False
            
            # 시간 동기화
            if current_time is None:
                idx_1m = -1
                idx_5m = -1
            else:
                # 가장 가까운 시간 인덱스 찾기
                idx_1m = df_1m.index.get_indexer([current_time], method='nearest')[0]
                idx_5m = df_5m.index.get_indexer([current_time], method='nearest')[0]
                
                if idx_1m == -1 or idx_5m == -1:
                    return False
            
            ema_1m_20 = df_1m['EMA_20'].iloc[idx_1m]
            ema_5m_100 = df_5m['EMA_100'].iloc[idx_5m]
            
            if pd.isna(ema_1m_20) or pd.isna(ema_5m_100) or ema_1m_20 == 0:
                return False
            
            # 1% 이내 근접도 확인
            convergence_ratio = abs(ema_1m_20 - ema_5m_100) / ema_1m_20
            is_converged = convergence_ratio <= self.convergence_threshold
            
            return is_converged
            
        except Exception as e:
            logger.error(f"1m20-5m100 컨버전스 감지 오류: {e}")
            return False
    
    def detect_convergence_1m20_supertrend(self, df: pd.DataFrame, current_idx: int = -1) -> bool:
        """
        1분 20EMA와 슈퍼트렌드 컨버전스 탐지 (DRV-002)
        
        Args:
            df: 지표가 계산된 데이터프레임
            current_idx: 현재 검사할 인덱스
            
        Returns:
            컨버전스 여부
        """
        try:
            required_cols = ['EMA_20', 'SuperTrend']
            for col in required_cols:
                if col not in df.columns:
                    return False
            
            idx = current_idx if current_idx >= 0 else -1
            
            ema_20 = df['EMA_20'].iloc[idx]
            supertrend = df['SuperTrend'].iloc[idx]
            
            if pd.isna(ema_20) or pd.isna(supertrend) or ema_20 == 0:
                return False
            
            convergence_ratio = abs(ema_20 - supertrend) / ema_20
            is_converged = convergence_ratio <= self.convergence_threshold
            
            return is_converged
            
        except Exception as e:
            logger.error(f"1m20-슈퍼트렌드 컨버전스 감지 오류: {e}")
            return False
    
    def detect_convergence_1m50_vwap_supertrend(self, df: pd.DataFrame, current_idx: int = -1) -> bool:
        """
        1분 50EMA, VWAP, 슈퍼트렌드 3중 컨버전스 탐지 (DRV-005)
        
        Args:
            df: 지표가 계산된 데이터프레임
            current_idx: 현재 검사할 인덱스
            
        Returns:
            3중 컨버전스 여부
        """
        try:
            required_cols = ['EMA_50', 'VWAP', 'SuperTrend']
            for col in required_cols:
                if col not in df.columns:
                    return False
            
            idx = current_idx if current_idx >= 0 else -1
            
            ema_50 = df['EMA_50'].iloc[idx]
            vwap = df['VWAP'].iloc[idx] 
            supertrend = df['SuperTrend'].iloc[idx]
            
            if any(pd.isna(val) or val == 0 for val in [ema_50, vwap, supertrend]):
                return False
            
            values = [ema_50, vwap, supertrend]
            max_val = max(values)
            min_val = min(values)
            
            convergence_ratio = (max_val - min_val) / max_val
            is_converged = convergence_ratio <= self.convergence_threshold
            
            return is_converged
            
        except Exception as e:
            logger.error(f"3중 컨버전스 감지 오류: {e}")
            return False
    
    # ================== 유틸리티 함수들 ==================
    
    def get_price_distance_ratio(self, price1: float, price2: float) -> float:
        """
        두 가격 간의 거리 비율 계산
        
        Args:
            price1: 첫 번째 가격
            price2: 두 번째 가격
            
        Returns:
            거리 비율 (0.01 = 1%)
        """
        try:
            if price1 == 0 or price2 == 0:
                return float('inf')
            
            return abs(price1 - price2) / max(price1, price2)
            
        except Exception as e:
            logger.error(f"가격 거리 계산 오류: {e}")
            return float('inf')
    
    def is_market_hours(self, timestamp: datetime, start_hour: int = 21, end_hour: int = 0, end_minute: int = 30) -> bool:
        """
        핵심 매매 시간대 확인 (한국 시간 기준 21:00-00:30)
        
        Args:
            timestamp: 확인할 시간
            start_hour: 시작 시간 (기본 21)
            end_hour: 종료 시간 (기본 0, 다음날)
            end_minute: 종료 분 (기본 30)
            
        Returns:
            핵심 매매 시간대 여부
        """
        try:
            hour = timestamp.hour
            minute = timestamp.minute
            
            # 21:00부터 23:59까지
            if hour >= start_hour:
                return True
            
            # 00:00부터 00:30까지
            if hour == end_hour and minute <= end_minute:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"시장 시간 확인 오류: {e}")
            return False
    
    def filter_market_hours_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        핵심 매매 시간대 데이터만 필터링
        
        Args:
            df: 원본 데이터프레임
            
        Returns:
            필터링된 데이터프레임
        """
        try:
            if df.empty:
                return df
            
            # 시간 정보 추출
            if hasattr(df.index, 'hour'):
                df_filtered = df[
                    (df.index.hour >= 21) | 
                    ((df.index.hour == 0) & (df.index.minute <= 30))
                ].copy()
            else:
                # 시간 정보가 없으면 원본 반환
                df_filtered = df.copy()
            
            return df_filtered
            
        except Exception as e:
            logger.error(f"시장 시간 필터링 오류: {e}")
            return df.copy()
    
    def calculate_signal_grade(self, strength_ratio: float) -> str:
        """
        신호 강도에 따른 등급 산정
        
        Args:
            strength_ratio: 강도 비율 (예: 거래량 비율, 가격 변화율 등)
            
        Returns:
            등급 문자열 ('A++', 'A+', 'A', 'B+', 'B', 'C')
        """
        try:
            if strength_ratio >= 10.0:
                return 'A++'
            elif strength_ratio >= 7.0:
                return 'A+'
            elif strength_ratio >= 5.0:
                return 'A'
            elif strength_ratio >= 3.0:
                return 'B+'
            elif strength_ratio >= 2.0:
                return 'B'
            else:
                return 'C'
                
        except Exception as e:
            logger.error(f"신호 등급 산정 오류: {e}")
            return 'C'
    
    async def batch_calculate_indicators(self, ohlcv_data_dict: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        여러 시간대 데이터에 대해 배치로 지표 계산
        
        Args:
            ohlcv_data_dict: 시간대별 OHLCV 데이터 딕셔너리
            
        Returns:
            시간대별 지표가 계산된 데이터 딕셔너리
        """
        try:
            results = {}
            
            for timeframe, data in ohlcv_data_dict.items():
                if not data.empty:
                    results[timeframe] = self.calculate_all_indicators(data, timeframe)
                else:
                    results[timeframe] = data.copy()
            
            return results
            
        except Exception as e:
            logger.error(f"배치 지표 계산 오류: {e}")
            return ohlcv_data_dict.copy()
    
    def get_latest_signals(self, df: pd.DataFrame) -> Dict[str, Union[bool, float, str]]:
        """
        최신 시점의 모든 아톰 신호 상태 확인
        
        Args:
            df: 지표가 계산된 데이터프레임
            
        Returns:
            모든 아톰 신호 상태 딕셔너리
        """
        try:
            if df.empty:
                return {}
            
            signals = {}
            
            # EMA 지지 신호들
            for period in [5, 20, 50, 200]:
                signals[f'ema_{period}_support'] = self.detect_ema_support(df, period)
            
            # VWAP 관련 신호들
            signals['vwap_support'] = self.detect_vwap_support(df)
            signals['vwap_golden_cross'] = self.detect_vwap_golden_cross(df)
            signals['vwap_reclaim'] = self.detect_vwap_reclaim(df)
            signals['vwap_breakdown'] = self.detect_vwap_breakdown(df)
            
            # 슈퍼트렌드 신호들
            signals['supertrend_support'] = self.detect_supertrend_support(df)
            signals['supertrend_breakout'] = self.detect_supertrend_breakout(df)
            
            # 패턴 신호들
            signals['ema_compression'] = self.detect_ema_compression(df)
            signals['uptrend_array'] = self.detect_uptrend_array(df)
            
            # 거래량 신호
            volume_data = self.detect_volume_explosion(df)
            signals['volume_explosion'] = volume_data['triggered']
            signals['volume_ratio'] = volume_data['volume_ratio']
            signals['volume_grade'] = volume_data['grade']
            
            # 컨버전스 신호들
            signals['convergence_1m20_supertrend'] = self.detect_convergence_1m20_supertrend(df)
            signals['convergence_3way'] = self.detect_convergence_1m50_vwap_supertrend(df)
            
            return signals
            
        except Exception as e:
            logger.error(f"최신 신호 확인 오류: {e}")
            return {}

# 사용 예시 및 테스트 코드
if __name__ == "__main__":
    async def test_technical_indicators():
        """기술적 지표 모듈 테스트"""
        
        # 테스트용 더미 데이터 생성
        import numpy as np
        from datetime import datetime, timedelta
        
        # 100개 캔들 데이터 생성
        dates = pd.date_range(start='2025-07-30 09:30:00', periods=100, freq='1min')
        np.random.seed(42)
        
        # 랜덤 워크로 가격 데이터 생성
        returns = np.random.normal(0, 0.01, 100)
        prices = 100 * np.exp(np.cumsum(returns))
        
        # OHLCV 데이터 생성
        test_data = pd.DataFrame({
            'Open': prices * (1 + np.random.normal(0, 0.002, 100)),
            'High': prices * (1 + np.abs(np.random.normal(0, 0.005, 100))),
            'Low': prices * (1 - np.abs(np.random.normal(0, 0.005, 100))),
            'Close': prices,
            'Volume': np.random.randint(10000, 1000000, 100)
        }, index=dates)
        
        # 기술적 지표 계산기 초기화
        ti = TechnicalIndicators()
        
        print("🔧 기술적 지표 모듈 테스트 시작")
        print("=" * 50)
        
        # 1. 모든 지표 계산 테스트
        print("1️⃣ 모든 지표 계산 테스트")
        df_with_indicators = ti.calculate_all_indicators(test_data, '1m')
        print(f"   - 원본 컬럼 수: {len(test_data.columns)}")
        print(f"   - 지표 추가 후 컬럼 수: {len(df_with_indicators.columns)}")
        print(f"   - 추가된 지표들: {list(set(df_with_indicators.columns) - set(test_data.columns))}")
        
        # 2. 개별 지표 테스트
        print("\n2️⃣ 개별 지표 계산 테스트")
        
        # EMA 테스트
        ema_20 = ti.calculate_ema(test_data['Close'], 20)
        print(f"   - EMA(20) 마지막 값: {ema_20.iloc[-1]:.2f}")
        
        # RSI 테스트
        rsi = ti.calculate_rsi(test_data['Close'])
        print(f"   - RSI 마지막 값: {rsi.iloc[-1]:.2f}")
        
        # VWAP 테스트
        vwap = ti.calculate_vwap(test_data)
        print(f"   - VWAP 마지막 값: {vwap.iloc[-1]:.2f}")
        
        # 3. 아톰 탐지 테스트
        print("\n3️⃣ 아톰 탐지 기능 테스트")
        
        # EMA 지지 테스트
        ema_support = ti.detect_ema_support(df_with_indicators, 20)
        print(f"   - EMA(20) 지지: {ema_support}")
        
        # 거래량 폭발 테스트
        volume_explosion = ti.detect_volume_explosion(df_with_indicators)
        print(f"   - 거래량 폭발: {volume_explosion}")
        
        # VWAP 골든크로스 테스트
        vwap_gc = ti.detect_vwap_golden_cross(df_with_indicators)
        print(f"   - VWAP 골든크로스: {vwap_gc}")
        
        # 4. 종합 신호 상태 테스트
        print("\n4️⃣ 종합 신호 상태 테스트")
        all_signals = ti.get_latest_signals(df_with_indicators)
        print(f"   - 총 {len(all_signals)}개 신호 확인")
        
        # 활성화된 신호들만 출력
        active_signals = {k: v for k, v in all_signals.items() if v is True}
        if active_signals:
            print(f"   - 활성화된 신호들: {list(active_signals.keys())}")
        else:
            print("   - 현재 활성화된 신호 없음")
        
        # 5. 성능 테스트
        print("\n5️⃣ 성능 테스트")
        import time
        
        start_time = time.time()
        for _ in range(10):
            ti.calculate_all_indicators(test_data, '1m')
        elapsed_time = time.time() - start_time
        
        print(f"   - 100개 캔들 데이터 지표 계산 x10회: {elapsed_time:.3f}초")
        print(f"   - 평균 처리 시간: {elapsed_time/10:.3f}초")
        
        print("\n✅ 모든 테스트 완료!")
        print("=" * 50)
        
        return df_with_indicators
    
    # 테스트 실행
    test_result = asyncio.run(test_technical_indicators())
