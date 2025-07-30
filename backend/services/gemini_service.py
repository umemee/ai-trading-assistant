"""
gemini_service.py - Google Gemini AI 분석 서비스
AI 트레이딩 어시스턴트 V5.1의 AI 분석 엔진

주요 기능:
- LogicDiscoverer: 패턴 분석 및 신규 아톰/분자 제안
- MetaLearner: 예측 복기 및 성장 분석
- 구조화된 프롬프트 생성 및 응답 파싱
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
import traceback

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd

# 로깅 설정
logger = logging.getLogger(__name__)

class GeminiService:
    """Google Gemini AI 서비스 클래스"""
    
    def __init__(self, api_key: str = None):
        """
        Gemini AI 서비스 초기화
        
        Args:
            api_key: Google Gemini API 키
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.model = None
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")
        
        self._initialize_service()
    
    def _initialize_service(self):
        """Gemini AI 서비스 초기화"""
        try:
            # API 키 설정
            genai.configure(api_key=self.api_key)
            
            # 모델 설정
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 4096,
            }
            
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
            
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-pro-latest",
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            logger.info("Gemini AI 서비스 초기화 완료")
            
        except Exception as e:
            logger.error(f"Gemini AI 초기화 실패: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            response = self.model.generate_content("Hello, this is a connection test.")
            
            if response and response.text:
                logger.info("Gemini AI 연결 성공")
                return True
            else:
                logger.error("Gemini AI 응답이 비어있습니다")
                return False
                
        except Exception as e:
            logger.error(f"Gemini AI 연결 테스트 실패: {e}")
            return False
    
    # ================== LogicDiscoverer 기능 ==================
    
    async def analyze_pattern(self, ticker: str, date: str, user_insight: str, 
                            chart_data: pd.DataFrame = None) -> Dict:
        """
        패턴 분석 및 신규 아톰/분자 제안 (LogicDiscoverer 엔진)
        
        Args:
            ticker: 종목 심볼
            date: 분석 날짜 (YYYY-MM-DD)
            user_insight: 사용자의 자연어 통찰
            chart_data: OHLCV 차트 데이터 (선택사항)
            
        Returns:
            Dict: 분석 결과 및 신규 아톰/분자 제안
        """
        try:
            # 프롬프트 생성
            prompt = self._generate_pattern_analysis_prompt(
                ticker, date, user_insight, chart_data
            )
            
            # Gemini AI 호출
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                raise ValueError("Gemini AI로부터 응답을 받지 못했습니다")
            
            # 응답 파싱
            result = self._parse_pattern_analysis_response(response.text)
            
            logger.info(f"패턴 분석 완료: {ticker} ({date})")
            return result
            
        except Exception as e:
            logger.error(f"패턴 분석 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'ticker': ticker,
                'date': date
            }
    
    def _generate_pattern_analysis_prompt(self, ticker: str, date: str, 
                                        user_insight: str, chart_data: pd.DataFrame = None) -> str:
        """패턴 분석을 위한 프롬프트 생성"""
        
        # 차트 데이터 요약 생성
        chart_summary = ""
        if chart_data is not None and not chart_data.empty:
            # 핵심 매매 시간대 필터링 (21:00-00:30 KST)
            filtered_data = self._filter_core_trading_hours(chart_data)
            chart_summary = self._generate_chart_summary(filtered_data)
        else:
            chart_summary = "차트 데이터가 제공되지 않았습니다."
        
        prompt = f"""당신은 전문 트레이딩 시스템 개발자입니다. 다음 정보를 분석하여 새로운 '아톰(Atom)'과 '분자(Molecule)'를 제안해주세요.

**분석 대상:**
- 종목: {ticker}
- 날짜: {date}
- 사용자 통찰: "{user_insight}"

**차트 데이터 요약:**
{chart_summary}

**아톰-분자 시스템 설명:**
- 아톰: 시장의 객관적 현상을 정의하는 최소 단위 (예: "1분_20EMA_지지", "거래량_폭발")
- 분자: 여러 아톰의 조합으로 구성되는 완성된 매매 전략

**기존 아톰 카테고리:**
- Context: 시장 환경 (CTX-XXX)
- Structural: 기술적 구조 (STR-XXX)  
- Trigger: 진입 신호 (TRG-XXX)
- Derived: 파생/컨버전스 (DRV-XXX)

**응답 형식:**
반드시 다음 JSON 형식으로만 응답하세요:
{{
"analysis": "상세한 기술적 분석 내용 (한국어)",
"suggested_atoms": [
{{
"atom_id": "새로운_아톰_ID (예: STR-020)",
"atom_name": "직관적인 아톰 이름",
"description": "아톰의 정량적 조건 및 사용 시간대",
"output_column_name": "코드용_변수명",
"category": "Context/Structural/Trigger/Derived 중 하나",
"source_reference": "{ticker}",
"timeframe": "1m/5m/1h 등"
}}
],
"suggested_molecule": {{
"molecule_id": "새로운_분자_ID (예: LOGIC-EXP-026)",
"molecule_name": "전략의 직관적 이름",
"category": "진입/반등/회피/위험관리 중 하나",
"required_atom_ids": ["필요한_아톰_ID들"],
"match_threshold": 90,
"translation_notes": "전략의 핵심 뉘앙스와 사용법 (한국어)"
}}
}}

**중요 지침:**
1. 사용자의 통찰을 기반으로 구체적이고 실용적인 아톰을 제안하세요
2. 아톰 ID는 기존 체계를 따라 생성하세요 (CTX-021, STR-020 등)
3. 분자는 실제 매매에 사용할 수 있는 완성된 전략이어야 합니다
4. 모든 설명은 한국어로 작성하세요
5. JSON 형식을 정확히 지켜주세요

지금 분석을 시작하세요:"""

        return prompt
    
    def _filter_core_trading_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """핵심 매매 시간대 (21:00-00:30 KST) 필터링"""
        try:
            # 시간 정보가 있는 경우만 필터링
            if 'datetime' in df.columns or df.index.name == 'datetime':
                if 'datetime' in df.columns:
                    df['hour'] = pd.to_datetime(df['datetime']).dt.hour
                else:
                    df['hour'] = df.index.hour
                
                # 21:00-23:59, 00:00-00:30 필터링
                filtered_df = df[
                    (df['hour'] >= 21) | (df['hour'] == 0)
                ].copy()
                
                return filtered_df
            else:
                # 시간 정보가 없으면 전체 데이터 반환
                return df
                
        except Exception as e:
            logger.warning(f"시간대 필터링 실패: {e}")
            return df
    
    def _generate_chart_summary(self, df: pd.DataFrame) -> str:
        """차트 데이터 요약 생성"""
        try:
            if df.empty:
                return "필터링된 데이터가 없습니다."
            
            # 기본 통계
            summary = f"""
**차트 데이터 요약 (핵심 매매 시간대):**
- 데이터 포인트: {len(df)}개
- 시간 범위: {df.index[0]} ~ {df.index[-1]}
- 시가: ${df['Open'].iloc[0]:.2f}
- 종가: ${df['Close'].iloc[-1]:.2f}
- 변동률: {((df['Close'].iloc[-1] / df['Open'].iloc[0]) - 1) * 100:.2f}%
- 최고가: ${df['High'].max():.2f}
- 최저가: ${df['Low'].min():.2f}
- 총 거래량: {df['Volume'].sum():,}
- 평균 거래량: {df['Volume'].mean():,.0f}
- 최대 거래량: {df['Volume'].max():,}
"""
            
            # 기술적 지표 추가 (EMA가 있는 경우)
            if 'EMA_20' in df.columns:
                summary += f"- 20EMA 종료: ${df['EMA_20'].iloc[-1]:.2f}\n"
            
            if 'VWAP' in df.columns:
                summary += f"- VWAP: ${df['VWAP'].iloc[-1]:.2f}\n"
            
            return summary
            
        except Exception as e:
            logger.error(f"차트 요약 생성 실패: {e}")
            return "차트 데이터 요약 생성 중 오류가 발생했습니다."
    
    def _parse_pattern_analysis_response(self, response_text: str) -> Dict:
        """패턴 분석 응답 파싱"""
        try:
            # JSON 부분 추출
            json_match = re.search(r'``````', response_text, re.DOTALL)
            if not json_match:
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                result = json.loads(json_str)
                
                # 결과 검증
                if not self._validate_pattern_analysis_result(result):
                    raise ValueError("응답 형식이 올바르지 않습니다")
                
                result['success'] = True
                result['raw_response'] = response_text
                return result
            else:
                # JSON이 없는 경우 텍스트 분석 결과로 반환
                return {
                    'success': True,
                    'analysis': response_text,
                    'suggested_atoms': [],
                    'suggested_molecule': None,
                    'raw_response': response_text
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return {
                'success': False,
                'error': f"JSON 파싱 오류: {str(e)}",
                'raw_response': response_text
            }
        except Exception as e:
            logger.error(f"응답 파싱 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'raw_response': response_text
            }
    
    def _validate_pattern_analysis_result(self, result: Dict) -> bool:
        """패턴 분석 결과 검증"""
        try:
            # 필수 필드 확인
            required_fields = ['analysis']
            for field in required_fields:
                if field not in result:
                    return False
            
            # 아톰 구조 검증
            if 'suggested_atoms' in result and isinstance(result['suggested_atoms'], list):
                for atom in result['suggested_atoms']:
                    required_atom_fields = ['atom_id', 'atom_name', 'category']
                    for field in required_atom_fields:
                        if field not in atom:
                            return False
            
            # 분자 구조 검증
            if 'suggested_molecule' in result and result['suggested_molecule']:
                molecule = result['suggested_molecule']
                required_molecule_fields = ['molecule_id', 'molecule_name', 'category']
                for field in required_molecule_fields:
                    if field not in molecule:
                        return False
            
            return True
            
        except Exception:
            return False
    
    # ================== MetaLearner 기능 ==================
    
    async def analyze_prediction_review(self, prediction_data: Dict, 
                                      actual_outcome: str, 
                                      sidb_records: List[Dict] = None,
                                      chart_data: pd.DataFrame = None) -> Dict:
        """
        예측 복기 분석 (MetaLearner 엔진)
        
        Args:
            prediction_data: 원본 예측 데이터
            actual_outcome: 실제 결과
            sidb_records: 해당 시점의 SIDB 기록들
            chart_data: 실제 차트 데이터
            
        Returns:
            Dict: 복기 분석 결과 및 개선 제안
        """
        try:
            # 프롬프트 생성
            prompt = self._generate_review_analysis_prompt(
                prediction_data, actual_outcome, sidb_records, chart_data
            )
            
            # Gemini AI 호출
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                raise ValueError("Gemini AI로부터 응답을 받지 못했습니다")
            
            # 응답 파싱
            result = self._parse_review_analysis_response(response.text)
            
            logger.info(f"예측 복기 분석 완료: {prediction_data.get('Ticker')} - {prediction_data.get('Triggered_Molecule_ID')}")
            return result
            
        except Exception as e:
            logger.error(f"예측 복기 분석 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'prediction_id': prediction_data.get('Prediction_ID')
            }
    
    def _generate_review_analysis_prompt(self, prediction_data: Dict, 
                                       actual_outcome: str,
                                       sidb_records: List[Dict] = None,
                                       chart_data: pd.DataFrame = None) -> str:
        """복기 분석을 위한 프롬프트 생성"""
        
        # SIDB 기록 요약
        sidb_summary = ""
        if sidb_records:
            sidb_summary = self._generate_sidb_summary(sidb_records)
        else:
            sidb_summary = "SIDB 기록이 제공되지 않았습니다."
        
        # 차트 데이터 요약
        chart_summary = ""
        if chart_data is not None and not chart_data.empty:
            filtered_data = self._filter_core_trading_hours(chart_data)
            chart_summary = self._generate_chart_summary(filtered_data)
        else:
            chart_summary = "차트 데이터가 제공되지 않았습니다."
        
        prompt = f"""당신은 전문 트레이딩 시스템 분석가입니다. 다음 예측에 대한 심층적인 복기 분석을 수행해주세요.

**원본 예측 정보:**
- 종목: {prediction_data.get('Ticker')}
- 예측 시간: {prediction_data.get('Timestamp_UTC')}
- 사용된 분자: {prediction_data.get('Triggered_Molecule_ID')}
- 예측 요약: {prediction_data.get('Prediction_Summary')}
- 핵심 아톰: {prediction_data.get('Key_Atoms_Found')}

**실제 결과:**
{actual_outcome}

**당시 발생한 아톰 기록 (SIDB):**
{sidb_summary}

**실제 차트 데이터:**
{chart_summary}

**분석 요청사항:**
1. 예측의 정확도 평가
2. 성공/실패 원인 분석
3. 놓친 신호나 잘못 해석한 부분
4. 시스템 개선 제안
5. 해당 분자 전략의 신뢰도 평가

**응답 형식:**
반드시 다음 JSON 형식으로만 응답하세요:
{{
"review_summary": "복기 분석 요약 (한국어)",
"accuracy_assessment": {{
"prediction_accuracy": "정확/부정확/부분적",
"confidence_score": 0.85,
"key_factors": ["성공/실패에 영향을 준 주요 요소들"]
}},
"detailed_analysis": {{
"what_worked": "잘 작동한 부분 (한국어)",
"what_failed": "실패한 부분 (한국어)",
"missed_signals": "놓친 신호들 (한국어)",
"timing_analysis": "타이밍 분석 (한국어)"
}},
"improvement_suggestions": {{
"molecule_adjustments": "분자 전략 수정 제안 (한국어)",
"threshold_changes": "임계값 변경 제안",
"new_filters": "추가 필터 제안 (한국어)",
"risk_management": "리스크 관리 개선안 (한국어)"
}},
"system_learning": {{
"pattern_insights": "새로 발견한 패턴 (한국어)",
"market_conditions": "시장 환경 고려사항 (한국어)",
"behavioral_notes": "투자심리/행동 관련 노트 (한국어)"
}},
"confidence_adjustment": {{
"new_confidence_score": 0.75,
"reasoning": "신뢰도 조정 이유 (한국어)"
}}
}}

**중요 지침:**
1. 객관적이고 균형잡힌 분석을 제공하세요
2. 구체적인 개선안을 제시하세요
3. 모든 내용은 한국어로 작성하세요
4. JSON 형식을 정확히 지켜주세요
5. 수치적 평가도 포함하세요

지금 분석을 시작하세요:"""

        return prompt
    
    def _generate_sidb_summary(self, sidb_records: List[Dict]) -> str:
        """SIDB 기록 요약 생성"""
        try:
            if not sidb_records:
                return "SIDB 기록이 없습니다."
            
            # 시간순 정렬
            sorted_records = sorted(
                sidb_records, 
                key=lambda x: x.get('Timestamp_UTC', '')
            )
            
            summary = f"**SIDB 기록 ({len(sorted_records)}개):**\n"
            
            for record in sorted_records[:10]:  # 최대 10개만 표시
                timestamp = record.get('Timestamp_UTC', 'Unknown')
                ticker = record.get('Ticker', 'Unknown')
                atom_id = record.get('Atom_ID', 'Unknown')
                price = record.get('Price_At_Signal', 0)
                volume = record.get('Volume_At_Signal', 0)
                
                try:
                    # 시간 형식 변환
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M:%S')
                except:
                    time_str = timestamp
                
                summary += f"- [{time_str}] {ticker}: {atom_id} | ${price:.2f} | Vol: {volume:,}\n"
            
            if len(sorted_records) > 10:
                summary += f"... (총 {len(sorted_records)}개 중 10개만 표시)\n"
            
            return summary
            
        except Exception as e:
            logger.error(f"SIDB 요약 생성 실패: {e}")
            return "SIDB 기록 요약 생성 중 오류가 발생했습니다."
    
    def _parse_review_analysis_response(self, response_text: str) -> Dict:
        """복기 분석 응답 파싱"""
        try:
            # JSON 부분 추출
            json_match = re.search(r'``````', response_text, re.DOTALL)
            if not json_match:
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                result = json.loads(json_str)
                
                result['success'] = True
                result['raw_response'] = response_text
                return result
            else:
                # JSON이 없는 경우 텍스트 리포트로 반환
                return {
                    'success': True,
                    'review_summary': response_text,
                    'raw_response': response_text
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return {
                'success': False,
                'error': f"JSON 파싱 오류: {str(e)}",
                'raw_response': response_text
            }
        except Exception as e:
            logger.error(f"응답 파싱 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'raw_response': response_text
            }
    
    # ================== 일반 분석 기능 ==================
    
    async def general_market_analysis(self, query: str, context_data: Dict = None) -> Dict:
        """일반적인 시장 분석"""
        try:
            prompt = f"""당신은 전문 시장 분석가입니다. 다음 질문에 대해 상세하고 실용적인 분석을 제공해주세요.

**질문:** {query}

**컨텍스트 데이터:**
{json.dumps(context_data, indent=2, ensure_ascii=False) if context_data else "추가 데이터 없음"}

**응답 지침:**
1. 전문적이고 객관적인 분석을 제공하세요
2. 구체적인 데이터나 근거를 포함하세요
3. 실용적인 조언이나 전략을 제시하세요
4. 리스크 요소도 함께 언급하세요
5. 한국어로 작성하세요

분석을 시작하세요:"""
            
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                raise ValueError("Gemini AI로부터 응답을 받지 못했습니다")
            
            return {
                'success': True,
                'analysis': response.text,
                'query': query,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"일반 시장 분석 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'query': query
            }
    
    # ================== 유틸리티 메서드 ==================
    
    def validate_api_key(self) -> bool:
        """API 키 유효성 검증"""
        try:
            return bool(self.api_key and len(self.api_key) > 20)
        except:
            return False
    
    def get_model_info(self) -> Dict:
        """모델 정보 조회"""
        try:
            return {
                'model_name': self.model.model_name if self.model else 'Not initialized',
                'api_key_valid': self.validate_api_key(),
                'service_status': 'Active' if self.model else 'Inactive'
            }
        except Exception as e:
            return {
                'error': str(e),
                'service_status': 'Error'
            }

# 사용 예시
if __name__ == "__main__":
    async def test_gemini_service():
        # 환경 변수에서 API 키 로드
        api_key = os.getenv('GEMINI_API_KEY')
        
        if not api_key:
            print("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
            return
        
        # 서비스 초기화
        gemini_service = GeminiService(api_key=api_key)
        
        # 연결 테스트
        if await gemini_service.test_connection():
            print("✅ Gemini AI 연결 성공")
            
            # 패턴 분석 테스트
            result = await gemini_service.analyze_pattern(
                ticker="TSLA",
                date="2025-07-30",
                user_insight="20EMA 지지 후 거래량이 급증하며 상승했습니다"
            )
            
            if result['success']:
                print("🧠 패턴 분석 성공")
                print(f"분석 결과: {result['analysis'][:100]}...")
            else:
                print(f"❌ 패턴 분석 실패: {result['error']}")
                
        else:
            print("❌ Gemini AI 연결 실패")
    
    # 테스트 실행
    asyncio.run(test_gemini_service())
