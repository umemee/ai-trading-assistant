"""
environment_manager.py - 환경 관리 시스템

Staging과 Production 환경을 완전히 분리하여 안전한 개발/테스트 환경 제공
- 환경별 Google Sheets ID 관리
- 환경별 API 키 및 설정 분리
- 자동 환경 감지 및 전환
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class EnvironmentConfig:
    """환경 설정 데이터 클래스"""
    name: str
    sheets_id: str
    alpaca_paper_trading: bool
    alpaca_api_key: str
    alpaca_secret_key: str
    gemini_api_key: str
    risk_limits: Dict[str, Any]
    monitoring_enabled: bool
    debug_mode: bool

class EnvironmentManager:
    """환경 관리 시스템"""
    
    def __init__(self, config_path: str = "config"):
        self.config_path = Path(config_path)
        self.current_env = None
        self.environments = {}
        
        # 환경 설정 로드
        self._load_environments()
        
        # 현재 환경 감지
        self._detect_current_environment()
        
        logger.info(f"환경 관리자 초기화 완료: {self.current_env.name}")

    def _load_environments(self):
        """환경 설정 파일들 로드"""
        try:
            # config 디렉토리가 없으면 생성
            self.config_path.mkdir(exist_ok=True)
            
            # Staging 환경 설정
            staging_config_path = self.config_path / "staging.json"
            if staging_config_path.exists():
                with open(staging_config_path, 'r', encoding='utf-8') as f:
                    staging_data = json.load(f)
            else:
                # 기본 Staging 설정 생성
                staging_data = self._create_default_staging_config()
                with open(staging_config_path, 'w', encoding='utf-8') as f:
                    json.dump(staging_data, f, indent=2, ensure_ascii=False)
            
            self.environments['staging'] = EnvironmentConfig(
                name='staging',
                sheets_id=staging_data.get('sheets_id', ''),
                alpaca_paper_trading=True,
                alpaca_api_key=staging_data.get('alpaca_api_key', ''),
                alpaca_secret_key=staging_data.get('alpaca_secret_key', ''),
                gemini_api_key=staging_data.get('gemini_api_key', ''),
                risk_limits=staging_data.get('risk_limits', {}),
                monitoring_enabled=staging_data.get('monitoring_enabled', True),
                debug_mode=staging_data.get('debug_mode', True)
            )
            
            # Production 환경 설정
            production_config_path = self.config_path / "production.json"
            if production_config_path.exists():
                with open(production_config_path, 'r', encoding='utf-8') as f:
                    production_data = json.load(f)
            else:
                # 기본 Production 설정 생성
                production_data = self._create_default_production_config()
                with open(production_config_path, 'w', encoding='utf-8') as f:
                    json.dump(production_data, f, indent=2, ensure_ascii=False)
            
            self.environments['production'] = EnvironmentConfig(
                name='production',
                sheets_id=production_data.get('sheets_id', ''),
                alpaca_paper_trading=False,
                alpaca_api_key=production_data.get('alpaca_api_key', ''),
                alpaca_secret_key=production_data.get('alpaca_secret_key', ''),
                gemini_api_key=production_data.get('gemini_api_key', ''),
                risk_limits=production_data.get('risk_limits', {}),
                monitoring_enabled=production_data.get('monitoring_enabled', True),
                debug_mode=production_data.get('debug_mode', False)
            )
            
            logger.info("환경 설정 로드 완료")
            
        except Exception as e:
            logger.error(f"환경 설정 로드 실패: {e}")
            raise

    def _create_default_staging_config(self) -> Dict:
        """기본 Staging 환경 설정 생성"""
        return {
            "sheets_id": "여기에_STAGING_구글시트_ID_입력",
            "alpaca_api_key": "여기에_ALPACA_PAPER_API_KEY_입력",
            "alpaca_secret_key": "여기에_ALPACA_PAPER_SECRET_KEY_입력",
            "gemini_api_key": "여기에_GEMINI_API_KEY_입력",
            "risk_limits": {
                "max_position_size": 1000,
                "max_daily_trades": 50,
                "max_daily_loss": -500,
                "max_drawdown": -0.10
            },
            "monitoring_enabled": True,
            "debug_mode": True,
            "_instructions": {
                "sheets_id": "운영용 구글시트를 복사하여 'AI Trading Assistant (Staging)' 이름으로 생성 후 ID 입력",
                "alpaca_keys": "Alpaca Paper Trading API 키 입력",
                "risk_limits": "테스트 환경용 보수적 리스크 한도"
            }
        }

    def _create_default_production_config(self) -> Dict:
        """기본 Production 환경 설정 생성"""
        return {
            "sheets_id": "여기에_PRODUCTION_구글시트_ID_입력",
            "alpaca_api_key": "여기에_ALPACA_LIVE_API_KEY_입력",
            "alpaca_secret_key": "여기에_ALPACA_LIVE_SECRET_KEY_입력",
            "gemini_api_key": "여기에_GEMINI_API_KEY_입력",
            "risk_limits": {
                "max_position_size": 10000,
                "max_daily_trades": 100,
                "max_daily_loss": -2000,
                "max_drawdown": -0.15
            },
            "monitoring_enabled": True,
            "debug_mode": False,
            "_instructions": {
                "sheets_id": "운영용 구글시트 ID 입력",
                "alpaca_keys": "Alpaca Live Trading API 키 입력 (실제 자본 주의!)",
                "risk_limits": "운영 환경용 리스크 한도"
            }
        }

    def _detect_current_environment(self):
        """현재 환경 감지"""
        try:
            # 환경 변수로 환경 결정
            env_name = os.getenv('TRADING_ENV', 'staging').lower()
            
            if env_name in self.environments:
                self.current_env = self.environments[env_name]
            else:
                # 기본값은 staging
                self.current_env = self.environments['staging']
                logger.warning(f"알 수 없는 환경: {env_name}, staging으로 설정")
            
            logger.info(f"현재 환경: {self.current_env.name}")
            
        except Exception as e:
            logger.error(f"환경 감지 실패: {e}")
            self.current_env = self.environments['staging']

    def get_current_config(self) -> EnvironmentConfig:
        """현재 환경 설정 반환"""
        return self.current_env

    def switch_environment(self, env_name: str) -> bool:
        """환경 전환"""
        try:
            if env_name.lower() in self.environments:
                self.current_env = self.environments[env_name.lower()]
                logger.info(f"환경 전환 완료: {env_name}")
                return True
            else:
                logger.error(f"존재하지 않는 환경: {env_name}")
                return False
                
        except Exception as e:
            logger.error(f"환경 전환 실패: {e}")
            return False

    def is_production(self) -> bool:
        """Production 환경 여부 확인"""
        return self.current_env.name == 'production'

    def is_staging(self) -> bool:
        """Staging 환경 여부 확인"""
        return self.current_env.name == 'staging'

    def get_sheets_id(self) -> str:
        """현재 환경의 Google Sheets ID 반환"""
        return self.current_env.sheets_id

    def get_alpaca_config(self) -> Dict[str, Any]:
        """현재 환경의 Alpaca 설정 반환"""
        return {
            'api_key': self.current_env.alpaca_api_key,
            'secret_key': self.current_env.alpaca_secret_key,
            'paper_trading': self.current_env.alpaca_paper_trading,
            'base_url': 'https://paper-api.alpaca.markets' if self.current_env.alpaca_paper_trading else 'https://api.alpaca.markets'
        }

    def get_risk_limits(self) -> Dict[str, Any]:
        """현재 환경의 리스크 한도 반환"""
        return self.current_env.risk_limits.copy()

    def validate_environment(self) -> Dict[str, Any]:
        """현재 환경 설정 검증"""
        try:
            validation_result = {
                'environment': self.current_env.name,
                'valid': True,
                'issues': [],
                'warnings': []
            }
            
            # 필수 설정 확인
            if not self.current_env.sheets_id or '여기에' in self.current_env.sheets_id:
                validation_result['issues'].append('Google Sheets ID가 설정되지 않음')
                validation_result['valid'] = False
            
            if not self.current_env.alpaca_api_key or '여기에' in self.current_env.alpaca_api_key:
                validation_result['issues'].append('Alpaca API Key가 설정되지 않음')
                validation_result['valid'] = False
            
            if not self.current_env.gemini_api_key or '여기에' in self.current_env.gemini_api_key:
                validation_result['issues'].append('Gemini API Key가 설정되지 않음')
                validation_result['valid'] = False
            
            # 경고 사항 확인
            if self.current_env.name == 'production' and self.current_env.debug_mode:
                validation_result['warnings'].append('Production 환경에서 Debug 모드가 활성화됨')
            
            if self.current_env.name == 'production' and self.current_env.alpaca_paper_trading:
                validation_result['warnings'].append('Production 환경에서 Paper Trading이 활성화됨')
            
            return validation_result
            
        except Exception as e:
            logger.error(f"환경 검증 실패: {e}")
            return {
                'environment': self.current_env.name,
                'valid': False,
                'issues': [f'검증 실패: {str(e)}'],
                'warnings': []
            }

    def create_staging_copy(self, source_sheets_id: str) -> str:
        """Production 시트를 복사하여 Staging 환경 생성 (수동 작업 안내)"""
        instructions = f"""
        🏗️ Staging 환경 설정 안내
        
        1. Google Sheets 복사:
           - 현재 운영용 시트 ID: {source_sheets_id}
           - Google Sheets에서 해당 시트를 열고 '파일 > 사본 만들기' 클릭
           - 이름을 'AI Trading Assistant (Staging)'으로 변경
           - 새로 생성된 시트의 ID를 복사 (URL에서 /d/ 다음 부분)
        
        2. 설정 파일 업데이트:
           - config/staging.json 파일의 sheets_id를 새 시트 ID로 변경
           - API 키들을 Paper Trading용으로 설정
        
        3. 환경 변수 설정:
           - TRADING_ENV=staging 설정하여 Staging 모드로 실행
        
        4. 테스트 실행:
           - python main.py 로 시스템 시작
           - Staging 환경에서 안전하게 테스트
        """
        
        return instructions

# 전역 환경 관리자 인스턴스
_env_manager = None

def get_env_manager() -> EnvironmentManager:
    """전역 환경 관리자 인스턴스 반환"""
    global _env_manager
    if _env_manager is None:
        _env_manager = EnvironmentManager()
    return _env_manager

def get_current_env() -> EnvironmentConfig:
    """현재 환경 설정 반환 (편의 함수)"""
    return get_env_manager().get_current_config()

# 사용 예시
if __name__ == "__main__":
    # 환경 관리자 테스트
    env_manager = EnvironmentManager()
    
    print("🏗️ 환경 관리자 테스트")
    print("=" * 50)
    
    # 현재 환경 확인
    current = env_manager.get_current_config()
    print(f"현재 환경: {current.name}")
    print(f"Paper Trading: {current.alpaca_paper_trading}")
    print(f"Debug 모드: {current.debug_mode}")
    
    # 환경 검증
    validation = env_manager.validate_environment()
    print(f"\n환경 검증: {'✅ 통과' if validation['valid'] else '❌ 실패'}")
    
    if validation['issues']:
        print("문제점:")
        for issue in validation['issues']:
            print(f"  - {issue}")
    
    if validation['warnings']:
        print("경고사항:")
        for warning in validation['warnings']:
            print(f"  - {warning}")
    
    # Staging 환경 생성 안내
    if not validation['valid']:
        print("\n" + env_manager.create_staging_copy("현재_운영용_시트_ID"))
