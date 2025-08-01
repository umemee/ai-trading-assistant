"""
gemini_service.py - Google Gemini AI 분석 서비스 (V6.0 강화 버전)
AI 트레이딩 어시_assistants V6.0의 AI 분석 엔진

주요 기능:
- LogicDiscoverer: 인간의 통찰을 심층 분석하여 신규 분자를 제안하고 '검역(quarantined)' 상태로 시스템에 등록
- MetaLearner: 예측 실패의 근본 원인을 분석하고, 필요한 경우 신규 '회피(AVD)' 분자를 생성하여 시스템을 진화시킴
- V6.0 기획서의 요구사항을 반영한 고도로 구조화된 프롬프트 엔지니어링
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
            genai.configure(api_key=self.api_key)

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
            response = await self.model.generate_content_async("Hello, this is a connection test.")
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
                            chart_data: pd.DataFrame = None, sidb_records: List[Dict] = None) -> Dict:
        """
        패턴 분석 및 신규 분자 제안 (LogicDiscoverer 엔진)
        """
        try:
            prompt = self._generate_pattern_analysis_prompt(
                ticker, date, user_insight, chart_data, sidb_records
            )
            response = await self.model.generate_content_async(prompt)

            if not response or not response.text:
                raise ValueError("Gemini AI로부터 응답을 받지 못했습니다")

            result = self._parse_json_response(response.text)
            logger.info(f"패턴 분석 완료: {ticker} ({date})")
            return result

        except Exception as e:
            logger.error(f"패턴 분석 실패: {e}")
            return {'success': False, 'error': str(e), 'ticker': ticker, 'date': date}

    def _generate_pattern_analysis_prompt(self, ticker: str, date: str,
                                        user_insight: str, chart_data: pd.DataFrame = None,
                                        sidb_records: List[Dict] = None) -> str:
        """LogicDiscoverer를 위한 강화된 프롬프트 생성 (기획서 5.1장)"""
        chart_summary = self._generate_chart_summary(chart_data)
        sidb_summary = self._generate_sidb_summary(sidb_records)

        return f"""
당신은 AI 트레이딩 시스템의 핵심 전략 연구원입니다. 인간 트레이더의 창의적인 통찰을 시스템이 이해할 수 있는 '분자(Molecule)'로 변환하는 임무를 맡았습니다.

**분석 대상:**
- 종목: {ticker}
- 날짜: {date}
- 인간 트레이더의 핵심 통찰: "{user_insight}"

**정량적 데이터:**
- 당시 아톰 발생 기록 (SIDB): {sidb_summary}
- 차트 데이터 요약: {chart_summary}

**분석 요청사항 (기획서 5.1장):**
1.  **통찰 번역:** 인간의 언어로 된 통찰을 시스템의 언어인 '아톰'의 조합으로 번역하세요.
2.  **아톰 제안:** 필요하다면, 기존에 없는 새로운 아톰을 제안하세요. 아톰은 반드시 객관적이고 기계가 측정 가능해야 합니다.
3.  **분자 구조화:** 분석 결과를 바탕으로, 아래 JSON 형식에 맞는 완전한 '분자' 객체를 생성하세요. 이 분자는 즉시 시스템에 등록될 수 있어야 합니다.

**매우 중요한 규칙:**
- 새로 생성된 분자의 `Status` 필드는 반드시 **"quarantined"** (검역) 상태여야 합니다. 이는 모든 신규 전략이 안전성 검증(WFO 백테스팅)을 거치도록 하는 핵심 안전장치입니다.
- 모든 필드를 포함한 완전한 JSON 객체 하나만 반환해야 합니다. 설명이나 추가 텍스트는 JSON 외부에 작성하지 마세요.

**응답 형식 (JSON):**
{{
    "analysis": "인간의 통찰과 데이터를 종합한 상세 분석 내용. 왜 이 패턴이 유효했는지에 대한 해석을 포함해야 합니다.",
    "suggested_atoms": [
        {{
            "atom_id": "STR-021",
            "atom_name": "신규 아톰 이름",
            "description": "정량적 조건",
            "output_column_name": "is_new_atom_detected",
            "category": "Structural",
            "timeframe": "1m"
        }}
    ],
    "suggested_molecule": {{
        "Molecule_ID": "LOGIC-EXP-028",
        "Molecule_Name": "인간의 통찰을 요약한 분자 이름",
        "Category": "반등/진입",
        "Required_Atom_IDs": ["CTX-010", "STR-001", "TRG-003", "STR-021"],
        "Match_Threshold_%": 100,
        "Translation_Notes": "이 전략의 핵심 뉘앙스와 주의사항. 인간의 지혜를 AI에게 전달하는 내용입니다.",
        "Status": "quarantined",
        "Created_Date": "{datetime.now(timezone.utc).isoformat()}",
        "WFO_Score": 0.0,
        "Approved_Date": "",
        "Approved_By": ""
    }}
}}

지금 분석을 시작하고, 위의 형식에 맞는 JSON 응답만 생성하세요.
"""

    # ================== MetaLearner 기능 ==================

    async def analyze_prediction_review(self, prediction_data: Dict,
                                      actual_outcome: str,
                                      sidb_records: List[Dict] = None,
                                      chart_data: pd.DataFrame = None) -> Dict:
        """
        예측 복기 분석 및 시스템 개선 제안 (MetaLearner 엔진)
        """
        try:
            prompt = self._generate_review_analysis_prompt(
                prediction_data, actual_outcome, sidb_records, chart_data
            )
            response = await self.model.generate_content_async(prompt)

            if not response or not response.text:
                raise ValueError("Gemini AI로부터 응답을 받지 못했습니다")

            result = self._parse_json_response(response.text)
            logger.info(f"예측 복기 분석 완료: {prediction_data.get('Ticker')}")
            return result

        except Exception as e:
            logger.error(f"예측 복기 분석 실패: {e}")
            return {'success': False, 'error': str(e), 'prediction_id': prediction_data.get('Prediction_ID')}

    def _generate_review_analysis_prompt(self, prediction_data: Dict,
                                       actual_outcome: str,
                                       sidb_records: List[Dict] = None,
                                       chart_data: pd.DataFrame = None) -> str:
        """MetaLearner를 위한 강화된 프롬프트 생성 (기획서 5.2장)"""
        chart_summary = self._generate_chart_summary(chart_data)
        sidb_summary = self._generate_sidb_summary(sidb_records)

        return f"""
당신은 AI 트레이딩 시스템의 MetaLearner 엔진입니다. 과거 예측의 성공/실패 사례를 깊이 있게 분석하여 시스템을 스스로 학습하고 진화시키는 임무를 맡았습니다.

**복기 대상 예측:**
- 예측 ID: {prediction_data.get('Prediction_ID')}
- 종목: {prediction_data.get('Ticker')}
- 사용된 분자: {prediction_data.get('Triggered_Molecule_ID')}
- 예측 요약: "{prediction_data.get('Prediction_Summary')}"
- 예측 근거 아톰: {prediction_data.get('Key_Atoms_Found')}
- 예측 시간: {prediction_data.get('Timestamp_UTC')}

**실제 결과:** {actual_outcome}

**정량적 데이터:**
- 예측 전후 아톰 발생 기록 (SIDB): {sidb_summary}
- 실제 차트 데이터 요약: {chart_summary}

**분석 요청사항 (기획서 5.2장):**
1.  **근본 원인 분석 (Root Cause Analysis):** 예측과 실제 결과 사이의 간극(Gap)이 발생한 근본 원인을 진단하세요. (예: 놓친 아톰, 잘못된 컨텍스트 해석, 시장의 예상 밖 변화 등)
2.  **시스템 개선 제안:** 분석 결과를 바탕으로 시스템이 향후 더 나은 예측을 하도록 구체적인 개선안을 제시하세요.
3.  **신규 회피 분자 제안:** 만약 예측 실패가 특정 위험 패턴을 무시했기 때문이라면, 이 실패를 막기 위한 **새로운 '회피/위험관리(LOGIC-AVD)' 분자를 반드시 제안**해야 합니다. 이는 시스템이 실패로부터 배우는 핵심 과정입니다.

**매우 중요한 규칙:**
- 제안하는 모든 신규 분자의 `Status`는 **"quarantined"** (검역) 상태여야 합니다.
- 모든 필드를 포함한 완전한 JSON 객체 하나만 반환해야 합니다.

**응답 형식 (JSON):**
{{
    "ai_review_summary": "실패/성공의 근본 원인에 대한 AI의 최종 진단 리포트입니다.",
    "improvement_suggestions": {{
        "existing_molecule_adjustment": "기존 분자 '{prediction_data.get('Triggered_Molecule_ID')}'의 Translation_Notes 수정 제안. (예: '단, TRG-007 발생 시에는 이 신호를 무시해야 함')",
        "new_avoidance_molecule": {{
            "Molecule_ID": "LOGIC-AVD-012",
            "Molecule_Name": "이번 실패 사례를 막기 위한 새로운 회피 전략 이름",
            "Category": "회피/위험관리",
            "Required_Atom_IDs": ["실패의 원인이 된 핵심 아톰 조합"],
            "Match_Threshold_%": 100,
            "Translation_Notes": "이 위험 패턴에 대한 상세 설명 및 주의사항.",
            "Status": "quarantined",
            "Created_Date": "{datetime.now(timezone.utc).isoformat()}",
            "WFO_Score": 0.0,
            "Approved_Date": "",
            "Approved_By": ""
        }}
    }},
    "confidence_adjustment": {{
        "new_confidence_score": 0.70,
        "reasoning": "이번 복기 결과를 바탕으로 기존 분자의 신뢰도를 조정하는 이유."
    }}
}}

지금 복기 분석을 시작하고, 위의 형식에 맞는 JSON 응답만 생성하세요. 만약 실패를 막을 회피 분자 제안이 불필요하다면 "new_avoidance_molecule" 필드는 null로 설정하세요.
"""

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
            
            response = await self.model.generate_content_async(prompt)
            
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

    # ================== 유틸리티 메서드들 ==================

    def _parse_json_response(self, response_text: str) -> Dict:
        """AI 응답에서 JSON을 파싱하고 검증"""
        try:
            # 마크다운 코드 블록(```json ... ```)에서 JSON 추출
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if not json_match:
                # 코드 블록이 없는 경우, 전체 텍스트에서 JSON 객체를 찾으려는 시도
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)

            if json_match:
                json_str = json_match.group(1)
                result = json.loads(json_str)
                result['success'] = True
                result['raw_response'] = response_text
                return result
            else:
                raise ValueError("응답에서 유효한 JSON 객체를 찾을 수 없습니다.")
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return {'success': False, 'error': f"JSON 파싱 오류: {str(e)}", 'raw_response': response_text}
        except Exception as e:
            logger.error(f"응답 파싱 실패: {e}")
            return {'success': False, 'error': str(e), 'raw_response': response_text}

    def _generate_chart_summary(self, df: pd.DataFrame) -> str:
        """차트 데이터 요약 생성"""
        if df is None or df.empty:
            return "차트 데이터가 제공되지 않았습니다."
        try:
            summary = (
                f"- 데이터 기간: {df.index.min()} ~ {df.index.max()}\\n"
                f"- 시가/종가: ${df['Open'].iloc[0]:.2f} / ${df['Close'].iloc[-1]:.2f}\\n"
                f"- 최고가/최저가: ${df['High'].max():.2f} / ${df['Low'].min():.2f}\\n"
                f"- 총 거래량: {df['Volume'].sum():,}"
            )
            return summary
        except Exception as e:
            logger.error(f"차트 요약 생성 실패: {e}")
            return "차트 요약 생성 중 오류 발생"

    def _generate_sidb_summary(self, sidb_records: List[Dict]) -> str:
        """SIDB 기록 요약 생성"""
        if not sidb_records:
            return "관련 아톰 발생 기록이 없습니다."
        try:
            summary_list = [f"{rec.get('Atom_ID')} ({rec.get('Timestamp_UTC')})" for rec in sidb_records[:10]]
            summary = ", ".join(summary_list)
            if len(sidb_records) > 10:
                summary += f" 등 총 {len(sidb_records)}개"
            return summary
        except Exception as e:
            logger.error(f"SIDB 요약 생성 실패: {e}")
            return "SIDB 요약 생성 중 오류 발생"

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
        # .env 파일에서 API 키 로드
        from dotenv import load_dotenv
        load_dotenv()

        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
            return

        gemini_service = GeminiService(api_key=api_key)

        # 연결 테스트
        if await gemini_service.test_connection():
            print("✅ Gemini AI 연결 성공")

            # 1. LogicDiscoverer 테스트
            print("\\n--- 🧠 LogicDiscoverer 테스트 시작 ---")
            logic_result = await gemini_service.analyze_pattern(
                ticker="TSLA",
                date="2025-07-30",
                user_insight="장 초반 강력한 거래량과 함께 VWAP을 돌파한 후, 첫 20EMA 눌림목에서 강하게 반등했습니다. 이는 전형적인 주도주의 움직임으로 보입니다."
            )
            print(json.dumps(logic_result, indent=2, ensure_ascii=False))

            # 2. MetaLearner 테스트
            print("\\n--- 🔥 MetaLearner 테스트 시작 ---")
            prediction_data_example = {
                'Prediction_ID': 'pred_12345',
                'Ticker': 'LIDR',
                'Triggered_Molecule_ID': 'LOGIC-EXP-004',
                'Prediction_Summary': '주도주 첫 눌림목 반등 예측',
                'Key_Atoms_Found': ['CTX-010', 'TRG-008', 'STR-003'],
                'Timestamp_UTC': '2025-07-29T14:35:00Z'
            }
            sidb_records_example = [
                {'Atom_ID': 'CTX-010', 'Timestamp_UTC': '2025-07-29T14:30:00Z'},
                {'Atom_ID': 'TRG-008', 'Timestamp_UTC': '2025-07-29T14:32:00Z'},
                {'Atom_ID': 'STR-003', 'Timestamp_UTC': '2025-07-29T14:35:00Z'},
                # 결정적인 놓친 신호
                {'Atom_ID': 'TRG-007', 'Timestamp_UTC': '2025-07-29T14:36:00Z'}
            ]
            meta_result = await gemini_service.analyze_prediction_review(
                prediction_data=prediction_data_example,
                actual_outcome="실패 - 예측 직후 VWAP이 붕괴되며 급락하여 손절.",
                sidb_records=sidb_records_example
            )
            print(json.dumps(meta_result, indent=2, ensure_ascii=False))
        else:
            print("❌ Gemini AI 연결 실패")

    asyncio.run(test_gemini_service())
