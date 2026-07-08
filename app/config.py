"""전역 설정"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Bitget API
    bitget_api_key: str = ""
    bitget_api_secret: str = ""
    bitget_passphrase: str = ""
    bitget_base_url: str = "https://api.bitget.com"

    # 심볼 / 차트 (초단타 스켈핑: 실행 3분봉, 추세 필터 15분봉 단일)
    symbol: str = "SOLUSDT"
    product_type: str = "USDT-FUTURES"
    main_tf: str = "3m"
    htf_1: str = "15m"
    htf_2: str = "15m"
    ltf_ref: str = "1m"

    # 스켈핑 신호 조건 파라미터
    rsi_fast_period: int = 7
    rsi_entry_low: float = 40.0
    rsi_entry_high: float = 50.0
    volume_multiplier: float = 1.5
    swing_lookback: int = 10

    # 리스크 관리
    risk_per_trade: float = 0.01       # 계좌 위험도 1% (레거시 고정 사이징, 백업용)
    min_score: int = 80                # 5개 조건 중 4개 이상 충족 (4/5=80)
    min_risk_reward: float = 1.5

    # 켈리 포지션 사이징
    kelly_fraction: float = 0.5        # 하프 켈리
    max_risk_per_trade: float = 0.02   # 켈리 결과 상한 (계좌의 2%)
    max_leverage: int = 10             # 레버리지 상한
    margin_use_ratio: float = 0.2      # 증거금으로 쓸 계좌 비율 (레버리지 역산 기준)

    # 백그라운드 스케줄러 (대시보드를 안 열어도 서버가 알아서 주기적으로 신호 체크)
    scheduler_interval_seconds: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
