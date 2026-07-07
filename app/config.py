"""전역 설정"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Bitget API
    bitget_api_key: str = ""
    bitget_api_secret: str = ""
    bitget_passphrase: str = ""
    bitget_base_url: str = "https://api.bitget.com"

    # 심볼 / 차트
    symbol: str = "SOLUSDT"
    product_type: str = "USDT-FUTURES"
    main_tf: str = "15m"
    htf_1: str = "1h"
    htf_2: str = "4h"
    ltf_ref: str = "5m"

    # 리스크 관리
    risk_per_trade: float = 0.01       # 계좌 위험도 1%
    min_score: int = 80                # 최소 진입 점수
    min_risk_reward: float = 2.0       # 최소 손익비

    class Config:
        env_file = ".env"


settings = Settings()
